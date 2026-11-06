from unittest.mock import MagicMock

import pytest
from gitlab.exceptions import GitlabGetError

from manytask.glab import GitLabApi


@pytest.mark.parametrize("operation", ["add_user_to_namespace_group", "remove_user_from_namespace_group"])
@pytest.mark.parametrize("status", [403, 500, 503])
def test_membership_lookup_errors_are_not_treated_as_absent(operation: str, status: int) -> None:
    api = object.__new__(GitLabApi)
    api._gitlab = MagicMock()
    members = api._gitlab.groups.get.return_value.members
    members.get.side_effect = GitlabGetError("synthetic failure", response_code=status)
    with pytest.raises(RuntimeError):
        getattr(api, operation)(1, "2")
    members.create.assert_not_called()
    members.delete.assert_not_called()


def test_absent_membership_is_safe_to_revoke_again() -> None:
    api = object.__new__(GitLabApi)
    api._gitlab = MagicMock()
    members = api._gitlab.groups.get.return_value.members
    members.get.side_effect = GitlabGetError("not found", response_code=404)
    api.remove_user_from_namespace_group(1, "2")
    members.delete.assert_not_called()
