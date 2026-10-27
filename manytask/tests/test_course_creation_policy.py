from http import HTTPStatus
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from sqlalchemy.exc import NoResultFound

from manytask.course_creation import check_course_creation_namespace_permission


@pytest.mark.parametrize("is_admin, expected", [(True, None), (False, HTTPStatus.FORBIDDEN)])
def test_creation_without_namespace(is_admin: bool, expected: HTTPStatus | None) -> None:
    storage = Mock()
    result = check_course_creation_namespace_permission(storage, 0, "user", is_admin)
    assert result.status == expected
    assert result.namespace is None
    storage.get_namespace_by_id.assert_not_called()


@pytest.mark.parametrize(
    "role, is_admin, expected",
    [("namespace_admin", False, None), ("program_manager", False, HTTPStatus.FORBIDDEN), (None, True, None)],
)
def test_namespace_creation_permission(role: str | None, is_admin: bool, expected: HTTPStatus | None) -> None:
    namespace = SimpleNamespace(slug="course", name="Course", gitlab_group_id=12)
    storage = Mock()
    storage.get_namespace_by_id.return_value = namespace, role
    result = check_course_creation_namespace_permission(storage, 1, "user", is_admin)
    assert result.status == expected
    assert (result.namespace is namespace) == (expected is None)


@pytest.mark.parametrize("error", [PermissionError, NoResultFound])
def test_missing_or_inaccessible_namespace(error: type[Exception]) -> None:
    storage = Mock()
    storage.get_namespace_by_id.side_effect = error
    result = check_course_creation_namespace_permission(storage, 1, "user", True)
    assert result.status == HTTPStatus.NOT_FOUND
    assert result.namespace is None
