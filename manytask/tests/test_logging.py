import io
import logging
import sys
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from flask import Blueprint, Flask, g, session
from pydantic import BaseModel

from manytask.api import requires_token, validate_json_request
from manytask.main import CustomFlask, _logging_config
from manytask.utils import rms_settings
from manytask.utils.logging import ContextFormatter, get_log_context, log_context, model_log_identifiers
from manytask.web import root_bp


@pytest.fixture
def logging_app() -> Flask:
    app = Flask(__name__)
    app.secret_key = "logging-test-key"
    ui = Blueprint("course", __name__)
    ui.add_url_rule("/<course_name>/", endpoint="page", view_func=lambda course_name: "OK", methods=["GET", "POST"])
    app.register_blueprint(ui)
    return app


def test_context_identifies_actor_separately_from_target(logging_app: Flask) -> None:
    formatter = ContextFormatter("%(message)s | %(request_context)s")
    record = logging.LogRecord(
        "manytask.database", logging.INFO, __file__, 1, "Score stored user=%s", ("student",), None
    )
    with logging_app.test_request_context("/python/?token=query-secret", method="POST"):
        session["auth"] = {"username": "provider-login", "access_token": "access-secret"}
        session["manytask"] = {"username": "teacher", "user_id": 42}
        output = formatter.format(record)
        assert "Score stored user=student" in output
        assert "actor='teacher'" in output
        assert "actor_id='42'" in output
        assert "auth_method='session'" in output
        assert "source='ui'" in output
        assert "method='POST'" in output
        assert "endpoint='course.page'" in output
        assert "course='python'" in output
        assert "secret" not in output
        request_id = get_log_context()["request_id"]
        assert request_id != "-"
        assert get_log_context()["request_id"] == request_id
    with logging_app.test_request_context("/python/"):
        assert get_log_context()["actor"] == "anonymous"
        assert get_log_context()["request_id"] != request_id


def test_context_uses_provider_login_before_signup(logging_app: Flask) -> None:
    with logging_app.test_request_context("/python/"):
        session["auth"] = {"username": "new-user"}
        assert get_log_context()["actor"] == "new-user"
        assert get_log_context()["actor_id"] == "-"


def test_context_identifies_resources_during_creation(logging_app: Flask) -> None:
    with logging_app.test_request_context("/new", method="POST"):
        g.log_course = "new-course"
        g.log_namespace_id = 7
        context = get_log_context()
    assert context["course"] == "new-course"
    assert context["namespace_id"] == "7"


def test_validation_logs_omit_submitted_values(logging_app: Flask, caplog: pytest.LogCaptureFixture) -> None:
    class Payload(BaseModel):
        score: int

    with logging_app.test_request_context("/new", method="POST", json={"score": "private-value"}):
        payload, error = validate_json_request(Payload)
    assert payload is None
    assert error is not None
    assert "Request validation failed" in caplog.text
    assert "private-value" not in caplog.text
    assert "score" in caplog.text


def test_course_token_does_not_attribute_action_to_session_user() -> None:
    app = CustomFlask(__name__)
    app.secret_key = "logging-test-key"
    app.storage_api = MagicMock()
    app.storage_api.get_course.return_value = SimpleNamespace(token="course-secret")
    api = Blueprint("api", __name__)

    @api.post("/api/<course_name>/score")
    @requires_token
    def report(course_name: str) -> dict[str, str]:
        return get_log_context()

    app.register_blueprint(api)
    with app.test_client() as client:
        with client.session_transaction() as user_session:
            user_session["manytask"] = {"username": "teacher", "user_id": 42}
        response = client.post("/api/python/score", headers={"Authorization": "Bearer course-secret"})
    assert response.status_code == 200  # noqa: PLR2004
    assert response.json["actor"] == "course_token"
    assert response.json["actor_id"] == "-"
    assert response.json["auth_method"] == "course_token"
    assert response.json["source"] == "api"
    assert "course-secret" not in response.get_data(as_text=True)


def test_failed_login_with_existing_session_does_not_log_success(caplog: pytest.LogCaptureFixture) -> None:
    app = CustomFlask(__name__)
    app.secret_key = "logging-test-key"
    app.oauth = MagicMock()
    app.oauth.auth_provider.authorize_access_token.side_effect = RuntimeError("OAuth unavailable")
    app.register_blueprint(root_bp)
    with app.test_client() as client, caplog.at_level(logging.INFO):
        with client.session_transaction() as user_session:
            user_session["auth"] = {"username": "previous-user"}
        response = client.get("/login_finish")
    assert response.status_code == 302  # noqa: PLR2004
    assert "OAuth authorization failed" in caplog.text
    assert "Login completed" not in caplog.text


def test_formatter_preserves_other_handlers_and_exception_details(logging_app: Flask) -> None:
    formatter = ContextFormatter("%(message)s | %(request_context)s")
    try:
        raise RuntimeError("test failure")
    except RuntimeError:
        record = logging.LogRecord(
            "manytask.api",
            logging.ERROR,
            __file__,
            1,
            "Failed to update user=%s",
            ("bad\r\nforged entry",),
            sys.exc_info(),
        )
    with logging_app.test_request_context("/python/"):
        session["manytask"] = {"username": "bad\nactor"}
        output = formatter.format(record)
    assert r"user=bad\r\nforged entry" in output
    assert "\nforged entry" not in output
    assert "\nactor" not in output
    assert "RuntimeError: test failure" in output
    assert "Traceback" in output
    assert record.msg == "Failed to update user=%s"
    assert record.args == ("bad\r\nforged entry",)
    assert record.exc_text is None
    assert not hasattr(record, "request_context")


def test_background_context_is_isolated_and_reset(logging_app: Flask) -> None:
    with logging_app.test_request_context("/python/"):
        session["manytask"] = {"username": "teacher", "user_id": 42}
        initiating_context = get_log_context()

    def background() -> dict[str, str]:
        with log_context(initiating_context | {"source": "background"}):
            return get_log_context()

    with ThreadPoolExecutor(max_workers=1) as executor:
        context = executor.submit(background).result(timeout=5)
        reset_context = executor.submit(get_log_context).result(timeout=5)
    assert context["actor"] == "teacher"
    assert context["request_id"] == initiating_context["request_id"]
    assert context["source"] == "background"
    assert reset_context["actor"] == "system"
    assert reset_context["request_id"] == "-"


def test_reconcile_failure_logs_initiating_actor_and_cleans_up(
    logging_app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    output = io.StringIO()
    handler = logging.StreamHandler(output)
    handler.setFormatter(ContextFormatter("%(message)s | %(request_context)s"))
    monkeypatch.setattr(rms_settings.logger, "handlers", [handler])
    monkeypatch.setattr(rms_settings.logger, "propagate", False)
    thread_factory = MagicMock()
    monkeypatch.setattr(rms_settings.threading, "Thread", thread_factory)
    storage = MagicMock()
    storage.get_course.side_effect = RuntimeError("test failure")
    with logging_app.test_request_context("/python/"):
        session["manytask"] = {"username": "teacher", "user_id": 42}
        assert rms_settings.schedule_rms_settings_reconcile(storage, MagicMock(), "python")
    # Execute the queued work after the request context has gone away.
    thread_factory.call_args.kwargs["target"]()
    assert "Failed to reconcile RMS settings course=python" in output.getvalue()
    assert "actor='teacher'" in output.getvalue()
    assert "source='background'" in output.getvalue()
    assert "python" not in rms_settings._courses_in_progress
    assert get_log_context()["actor"] == "system"


def test_generic_database_logs_omit_configuration_and_profile_values() -> None:
    assert model_log_identifiers(
        {"username": "student", "course_id": 5, "token": "secret", "comment": "private", "first_name": "private"}
    ) == {"username": "student", "course_id": 5}


def test_application_logging_configuration_uses_context_formatter() -> None:
    config = _logging_config(CustomFlask(__name__))
    assert config["formatters"]["default"]["()"] == "manytask.utils.logging.ContextFormatter"
    assert "%(request_context)s" in config["formatters"]["default"]["format"]
