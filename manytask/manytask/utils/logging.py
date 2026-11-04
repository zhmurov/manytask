"""Shared log context for the web app and work it schedules.

Messages describe the action and outcome, followed by named target fields
(user, course, task, namespace_id, etc.). The context identifies the actor
separately from the user affected by the action. Never log tokens, request
bodies, database URLs, comments, or full user objects.
"""

import logging
from collections.abc import Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from copy import copy
from typing import Iterator
from uuid import uuid4

from flask import g, has_request_context, request, session

_background_context: ContextVar[dict[str, str]] = ContextVar("log_context", default={})


def model_log_identifiers(values: Mapping[str, object]) -> dict[str, object]:
    """Keep lookup identifiers while omitting configuration and profile values."""
    return {
        key: value
        for key, value in values.items()
        if key in {"id", "name", "slug", "username", "course_name", "task_name"} or key.endswith("_id")
    }


def get_log_context() -> dict[str, str]:
    """Read identifiers only; do not inspect request bodies, headers, or query strings."""
    context = {
        "source": "system",
        "actor": "system",
        "actor_id": "-",
        "auth_method": "none",
        "request_id": "-",
        "method": "-",
        "endpoint": "-",
        "course": "-",
        "namespace_id": "-",
    }
    context.update(_background_context.get())
    if not has_request_context():
        return context

    manytask_user = session.get("manytask", {})
    auth_user = session.get("auth", {})
    auth_method = getattr(g, "log_auth_method", "session" if auth_user or manytask_user else "none")
    actor = manytask_user.get("username") or auth_user.get("username") or "anonymous"
    actor_id = manytask_user.get("user_id", "-")
    if auth_method == "course_token":
        actor, actor_id = "course_token", "-"

    route = request.view_args or {}
    if not hasattr(g, "log_request_id"):
        g.log_request_id = uuid4().hex
    context.update(
        source="api" if request.blueprint in ("api", "namespace_api") else "ui",
        actor=str(actor),
        actor_id=str(actor_id),
        auth_method=auth_method,
        request_id=g.log_request_id,
        method=request.method,
        endpoint=request.endpoint or "-",
        course=str(route.get("course_name", getattr(g, "log_course", "-"))),
        namespace_id=str(route.get("namespace_id", getattr(g, "log_namespace_id", "-"))),
    )
    return context


@contextmanager
def log_context(context: dict[str, str]) -> Iterator[None]:
    """Carry a snapshot of the initiating actor into background work."""
    token = _background_context.set(context)
    try:
        yield
    finally:
        _background_context.reset(token)


class ContextFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        # Copy the record so other handlers (including access logs) are unaffected.
        contextual_record = copy(record)
        contextual_record.request_context = " ".join(f"{key}={value!r}" for key, value in get_log_context().items())
        # Prevent user-controlled values from introducing fake log entries.
        contextual_record.msg = record.getMessage().replace("\r", r"\r").replace("\n", r"\n")
        contextual_record.args = ()
        return super().format(contextual_record)
