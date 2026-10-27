from unittest.mock import Mock

import pytest

from manytask.abstract import CourseAccessUser
from manytask.access import can_edit_course, get_visible_courses, has_role
from manytask.course import CourseStatus


@pytest.mark.parametrize("role, expected", [("namespace_admin", True), ("program_manager", False), (None, False)])
def test_edit_policy_without_flask(role: str | None, expected: bool) -> None:
    assert can_edit_course(debug=False, is_instance_admin=False, namespace_id=1, namespace_role=role) is expected


def test_course_visibility_merges_without_changing_precedence_or_order() -> None:
    storage = Mock()
    storage.get_namespace_admin_namespaces.return_value = [1]
    storage.get_courses_by_namespace_ids.return_value = [("shared", CourseStatus.IN_PROGRESS)]
    storage.get_courses_where_course_admin.return_value = [
        ("shared", CourseStatus.FINISHED),
        ("owned", CourseStatus.CREATED),
    ]
    assert get_visible_courses(storage, "admin", is_instance_admin=False) == [
        ("shared", CourseStatus.IN_PROGRESS),
        ("owned", CourseStatus.CREATED),
    ]
    storage.get_user_courses_names_with_statuses.assert_not_called()


def test_course_role_checks_requested_user_without_request_context() -> None:
    storage = Mock()
    storage.get_course_access_users.return_value = [
        CourseAccessUser("alice", "A", "User", ["course_admin"]),
        CourseAccessUser("bob", "B", "User", ["namespace_admin"]),
    ]
    assert has_role("alice", "course_admin", storage, course_name="course")
    assert not has_role("alice", "namespace_admin", storage, course_name="course")
