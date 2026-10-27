from types import SimpleNamespace
from unittest.mock import Mock, call

import pytest
from sqlalchemy.exc import IntegrityError, NoResultFound

from manytask.namespace_membership import (
    AssignmentFailure,
    NamespaceRoleAssignment,
    NamespaceRoleError,
    add_namespace_role,
)

ASSIGNMENT = NamespaceRoleAssignment(1, 12, "student", "program_manager", "admin")


def test_assignment_stores_role_before_adding_rms_membership() -> None:
    operations = Mock()
    operations.storage.get_stored_user_by_username.return_value = SimpleNamespace(rms_id="rms-student")
    membership = add_namespace_role(operations.storage, operations.rms, ASSIGNMENT)
    assert membership is operations.storage.add_user_to_namespace.return_value
    assert operations.mock_calls == [
        call.storage.add_user_to_namespace(
            namespace_id=1, username="student", role="program_manager", assigned_by_username="admin"
        ),
        call.storage.get_stored_user_by_username("student"),
        call.rms.add_user_to_namespace_group(gitlab_group_id=12, rms_id="rms-student"),
    ]


@pytest.mark.parametrize(
    "error, kind",
    [
        (NoResultFound(), AssignmentFailure.NOT_FOUND),
        (IntegrityError("insert", {}, Exception()), AssignmentFailure.CONFLICT),
        (ValueError("invalid role"), AssignmentFailure.INVALID_ROLE),
    ],
)
def test_storage_rejection_does_not_touch_rms(error: Exception, kind: AssignmentFailure) -> None:
    storage, rms = Mock(), Mock()
    storage.add_user_to_namespace.side_effect = error
    with pytest.raises(NamespaceRoleError) as caught:
        add_namespace_role(storage, rms, ASSIGNMENT)
    assert caught.value.kind == kind
    assert not rms.mock_calls


def test_rms_failure_preserves_stored_role() -> None:
    storage, rms = Mock(), Mock()
    rms.add_user_to_namespace_group.side_effect = RuntimeError("unavailable")
    with pytest.raises(NamespaceRoleError) as caught:
        add_namespace_role(storage, rms, ASSIGNMENT)
    assert caught.value.kind == AssignmentFailure.RMS_FAILED
    storage.add_user_to_namespace.assert_called_once()
    storage.remove_user_from_namespace.assert_not_called()
