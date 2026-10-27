"""Namespace role assignment across storage and RMS, independent of HTTP."""

import logging
from dataclasses import dataclass
from enum import Enum
from typing import Protocol

from sqlalchemy.exc import IntegrityError, NoResultFound

from manytask.abstract import RmsApi, StorageApi
from manytask.utils.generic import sanitize_log_data

logger = logging.getLogger(__name__)


class NamespaceGroup(Protocol):
    @property
    def gitlab_group_id(self) -> int: ...


class NamespaceMembership(Protocol):
    @property
    def id(self) -> int: ...

    @property
    def user_id(self) -> int: ...

    @property
    def namespace_id(self) -> int: ...


class AssignmentFailure(Enum):
    NOT_FOUND = "not_found"
    CONFLICT = "conflict"
    INVALID_ROLE = "invalid_role"
    RMS_FAILED = "rms_failed"


class NamespaceRoleError(Exception):
    def __init__(self, kind: AssignmentFailure, message: str) -> None:
        super().__init__(message)
        self.kind = kind


@dataclass(frozen=True)
class NamespaceRoleAssignment:
    namespace_id: int
    gitlab_group_id: int
    username: str
    role: str
    assigned_by_username: str


def add_namespace_role(
    storage_api: StorageApi, rms_api: RmsApi, assignment: NamespaceRoleAssignment
) -> NamespaceMembership:
    """Store the role before adding RMS membership; preserve existing failure semantics.

    RMS failure leaves the stored role intact. Compensation is a separate lifecycle change.
    """
    try:
        membership = storage_api.add_user_to_namespace(
            namespace_id=assignment.namespace_id,
            username=assignment.username,
            role=assignment.role,
            assigned_by_username=assignment.assigned_by_username,
        )
    except NoResultFound as error:
        raise NamespaceRoleError(
            AssignmentFailure.NOT_FOUND,
            f"User {assignment.username} is not registered in manytask. The user must log in at least once.",
        ) from error
    except IntegrityError as error:
        raise NamespaceRoleError(AssignmentFailure.CONFLICT, "User already has a role in this namespace") from error
    except ValueError as error:
        raise NamespaceRoleError(AssignmentFailure.INVALID_ROLE, str(error)) from error

    try:
        stored_user = storage_api.get_stored_user_by_username(assignment.username)
        rms_api.add_user_to_namespace_group(gitlab_group_id=assignment.gitlab_group_id, rms_id=stored_user.rms_id)
    except Exception as error:
        logger.exception("Failed to add user %s to RMS group", sanitize_log_data(assignment.username))
        raise NamespaceRoleError(AssignmentFailure.RMS_FAILED, "Failed to add user to GitLab group") from error

    logger.info("Added RMS user id=%s to group id=%s", stored_user.rms_id, assignment.gitlab_group_id)
    return membership
