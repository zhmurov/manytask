from flask import session, url_for

from manytask import access
from manytask.main import CustomFlask


def get_courses(app: CustomFlask) -> list[dict[str, str | bool]]:
    username = "guest" if app.debug else session["manytask"]["username"]
    is_instance_admin = app.debug or app.storage_api.check_if_instance_admin(username)
    courses_names = access.get_visible_courses(app.storage_api, username, is_instance_admin=is_instance_admin)

    courses_list = []
    for course_name, status in courses_names:
        course_obj = app.storage_api.get_course(course_name)
        namespace_slug = ""
        namespace_url = ""
        namespace_role: str | None = None
        namespace_id = course_obj.namespace_id if course_obj else None
        if namespace_id:
            try:
                namespace, namespace_role = app.storage_api.get_namespace_by_id(namespace_id, username)
                namespace_slug = namespace.slug
                if is_instance_admin or namespace_role == "namespace_admin":
                    namespace_url = url_for("instance_admin.namespace_panel", namespace_id=namespace_id)
            except Exception:
                pass  # Namespace not found or no access

        courses_list.append(
            {
                "name": course_name,
                "status": status.value,
                "url": url_for("course.course_page", course_name=course_name),
                "namespace_slug": namespace_slug,
                "namespace_url": namespace_url,
                "can_edit": can_edit_course(
                    app,
                    is_instance_admin=is_instance_admin,
                    namespace_id=namespace_id,
                    namespace_role=namespace_role,
                ),
                "edit_url": url_for("instance_admin.edit_course", course_name=course_name),
            }
        )

    return courses_list


def can_edit_course(
    app: CustomFlask,
    *,
    is_instance_admin: bool,
    namespace_id: int | None,
    namespace_role: str | None,
) -> bool:
    """Adapt the explicit course-edit policy to the current Flask application."""
    return access.can_edit_course(
        debug=app.debug,
        is_instance_admin=is_instance_admin,
        namespace_id=namespace_id,
        namespace_role=namespace_role,
    )


def check_if_current_user_is_instance_admin(app: CustomFlask) -> bool:
    """Check whether the current session user is an instance admin.

    Session-aware Flask helper: resolves the username from the session (and
    returns ``True`` in debug mode), then delegates to the storage primitive
    :meth:`StorageApi.check_if_instance_admin`. Do not confuse it with that
    storage method, which takes an explicit ``username`` argument.

    :param app: Flask application instance
    :return: True if the current user is an instance admin
    """
    if app.debug:
        return True
    else:
        username = session.get("manytask", {}).get("username")
        if username is None:
            return False
        return app.storage_api.check_if_instance_admin(username)


def check_if_user_has_namespaces_to_admin(app: CustomFlask) -> bool:
    """The user can create course only if:
    - They are instance admin
    - There is a nemespace they are admin of.

    :param app: Flask application instance
    :return: True if user is a namespace admin
    """
    if app.debug:
        return True
    else:
        username = session["manytask"]["username"]
        return access.can_create_courses(app.storage_api, username)


def has_role(
    username: str,
    required_roles: list[str] | str,
    app: CustomFlask,
    course_name: str | None = None,
    namespace_id: int | None = None,
) -> bool:
    """Check if user has at least one of the required roles.

    :param username: manytask username
    :param required_roles: Single role string or list of role strings
    :param app: Flask application instance
    :param course_name: Optional course name for course-specific roles
    :param namespace_id: Optional namespace id for namespace-specific roles
    :return: True if user has at least one of the required roles
    """
    return access.has_role(username, required_roles, app.storage_api, course_name, namespace_id)
