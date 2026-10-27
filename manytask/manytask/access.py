"""Access policies and course selection with explicit storage and user context."""

from manytask.abstract import StorageApi
from manytask.course import CourseStatus


def can_edit_course(
    *, debug: bool, is_instance_admin: bool, namespace_id: int | None, namespace_role: str | None
) -> bool:
    """Course administrators alone cannot edit namespace-managed settings."""
    return debug or is_instance_admin or (bool(namespace_id) and namespace_role == "namespace_admin")


def can_create_courses(storage_api: StorageApi, username: str) -> bool:
    return bool(storage_api.get_namespace_admin_namespaces(username)) or storage_api.check_if_instance_admin(username)


def get_visible_courses(
    storage_api: StorageApi, username: str, *, is_instance_admin: bool
) -> list[tuple[str, CourseStatus]]:
    """Preserve course visibility and ordering independently of Flask presentation."""
    if is_instance_admin:
        return storage_api.get_all_courses_names_with_statuses()
    namespaces = storage_api.get_namespace_admin_namespaces(username)
    if namespaces:
        courses = dict(storage_api.get_courses_by_namespace_ids(namespaces))
        for name, status in storage_api.get_courses_where_course_admin(username):
            courses.setdefault(name, status)
        return list(courses.items())
    return storage_api.get_user_courses_names_with_statuses(username)


def has_role(
    username: str,
    required_roles: list[str] | str,
    storage_api: StorageApi,
    course_name: str | None = None,
    namespace_id: int | None = None,
) -> bool:
    """Resolve the requested user's roles, without reading session or application state."""
    required = {required_roles} if isinstance(required_roles, str) else set(required_roles)

    if course_name:
        access_user = next(
            (user for user in storage_api.get_course_access_users(course_name) if user.username == username),
            None,
        )
        if "student" in required or (access_user is not None and required.intersection(access_user.access_levels)):
            return True
    elif "instance_admin" in required and storage_api.check_if_instance_admin(username):
        return True

    if namespace_id is not None and "namespace_admin" in required:
        try:
            _, namespace_role = storage_api.get_namespace_by_id(namespace_id, username)
        except PermissionError:
            namespace_role = None
        return namespace_role == "namespace_admin"

    return False
