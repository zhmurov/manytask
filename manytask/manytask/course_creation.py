"""Shared course-creation policy, independent of request and response handling."""

import logging
from dataclasses import dataclass
from http import HTTPStatus
from typing import Protocol

from sqlalchemy.exc import NoResultFound

from manytask.abstract import StorageApi

logger = logging.getLogger(__name__)


class CourseNamespace(Protocol):
    @property
    def slug(self) -> str: ...

    @property
    def name(self) -> str: ...

    @property
    def gitlab_group_id(self) -> int: ...


@dataclass(frozen=True)
class CourseCreationPermission:
    namespace: CourseNamespace | None = None
    role: str | None = None
    error: str | None = None
    status: HTTPStatus | None = None


def check_course_creation_namespace_permission(
    storage_api: StorageApi,
    namespace_id: int,
    username: str,
    is_instance_admin: bool,
) -> CourseCreationPermission:
    namespace = None
    role = None
    if namespace_id == 0:
        if not is_instance_admin:
            logger.warning("User %s attempted to create course without namespace", username)
            return CourseCreationPermission(
                error="Only Instance Admin can create courses without namespace", status=HTTPStatus.FORBIDDEN
            )
    else:
        try:
            namespace, role = storage_api.get_namespace_by_id(namespace_id, username)
        except (PermissionError, NoResultFound):
            logger.warning("User %s attempted to create course in inaccessible namespace id=%s", username, namespace_id)
            return CourseCreationPermission(error="Namespace not found or access denied", status=HTTPStatus.NOT_FOUND)

        if not is_instance_admin and role != "namespace_admin":
            logger.warning(
                "User %s with role %s attempted to create course in namespace id=%s",
                username,
                role,
                namespace_id,
            )
            return CourseCreationPermission(
                error="Only Instance Admin or Namespace Admin can create courses",
                status=HTTPStatus.FORBIDDEN,
            )

    return CourseCreationPermission(namespace=namespace, role=role)
