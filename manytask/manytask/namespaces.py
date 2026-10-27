"""Read-only namespace contracts shared by storage and application code."""

from typing import Protocol


class Namespace(Protocol):
    @property
    def id(self) -> int: ...

    @property
    def name(self) -> str: ...

    @property
    def slug(self) -> str: ...

    @property
    def description(self) -> str | None: ...

    @property
    def gitlab_group_id(self) -> int: ...


class NamespaceMembership(Protocol):
    @property
    def id(self) -> int: ...

    @property
    def user_id(self) -> int: ...

    @property
    def namespace_id(self) -> int: ...


class NamespaceLookup(Protocol):
    def get_namespace_by_id(self, namespace_id: int, username: str) -> tuple[Namespace, str | None]: ...
