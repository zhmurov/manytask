from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import httpx
import pytest
import requests
from flask import Flask, Response, abort, jsonify
from gitlab.exceptions import GitlabAuthenticationError, GitlabConnectionError, GitlabGetError
from sqlalchemy.exc import OperationalError

from manytask.error_pages import ERROR_ASSETS, ERROR_PAGES
from manytask.main import create_app
from manytask.utils.generic import check_oauth_authenticated


@pytest.fixture
def error_app() -> Flask:
    with (
        patch("manytask.main._database_storage_setup"),
        patch("manytask.main.logging.config.dictConfig"),
    ):
        app = create_app(test=True)
    app.config.update(PROPAGATE_EXCEPTIONS=False, WTF_CSRF_ENABLED=False)
    app.app_config.gitlab_url = "https://gitlab.example"
    app.app_config.gitlab_oauth_url = "https://gitlab.example"
    app.app_config.sourcecraft_api_url = "https://sourcecraft.example"

    @app.route("/failure", methods=["GET", "POST"])
    @app.route("/api/_failure", methods=["GET", "POST"])
    @app.route("/api", methods=["GET", "POST"])
    def failure() -> str:
        raise app.extensions.get("test_failure", RuntimeError("private backend details"))

    @app.get("/status/<int:status>")
    def status_error(status: int) -> str:
        abort(status)

    @app.get("/api/_explicit")
    def explicit_error() -> tuple[Response, int]:
        return jsonify(error="An existing API error"), 503

    @app.context_processor
    def broken_context() -> dict[str, str]:
        raise RuntimeError("The fallback must not call context processors")

    return app


def test_unhandled_failure_uses_standalone_page(error_app: Flask) -> None:
    response = error_app.test_client().get("/failure")
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.mimetype == "text/html"
    assert response.data == (ERROR_ASSETS / "internal.html").read_bytes()
    assert b"private backend details" not in response.data
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_server_errors_keep_status(error_app: Flask, status: int) -> None:
    response = error_app.test_client().get(f"/status/{status}")
    assert response.status_code == status
    assert response.mimetype == "text/html"
    assert b"@@" not in response.data


@pytest.mark.parametrize(
    ("path", "headers"),
    [
        ("/api/_failure", {}),
        ("/api", {"Accept": "text/html"}),
        ("/failure", {"Accept": "application/json"}),
        ("/failure", {"Content-Type": "application/json"}),
    ],
)
def test_api_failures_are_json(error_app: Flask, path: str, headers: dict[str, str]) -> None:
    response = error_app.test_client().post(path, headers=headers)
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.is_json
    page = ERROR_PAGES["internal"]
    assert response.json == {"error": f"{page['title']}. {page['description']}"}
    assert response.headers["Cache-Control"] == "no-store"


def test_existing_api_response_is_preserved(error_app: Flask) -> None:
    response = error_app.test_client().get("/api/_explicit")
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json == {"error": "An existing API error"}


@pytest.mark.parametrize("status", [403, 404])
def test_client_errors_are_not_replaced(error_app: Flask, status: int) -> None:
    response = error_app.test_client().get(f"/status/{status}")
    assert response.status_code == status
    assert b"Try again" not in response.data


def test_browser_accepting_any_type_gets_html(error_app: Flask) -> None:
    response = error_app.test_client().get("/failure", headers={"Accept": "*/*"})
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.mimetype == "text/html"


@pytest.mark.parametrize(
    ("error", "page", "status"),
    [
        (GitlabConnectionError("private backend details"), "gitlab", HTTPStatus.SERVICE_UNAVAILABLE),
        (GitlabGetError("private backend details", response_code=503), "gitlab", HTTPStatus.SERVICE_UNAVAILABLE),
        (GitlabAuthenticationError("private backend details"), "gitlab-access", HTTPStatus.BAD_GATEWAY),
        (
            httpx.ConnectError(
                "private backend details", request=httpx.Request("GET", "https://sourcecraft.example/repos")
            ),
            "sourcecraft",
            HTTPStatus.SERVICE_UNAVAILABLE,
        ),
        (
            httpx.ReadTimeout(
                "private backend details", request=httpx.Request("GET", "https://sourcecraft.example/repos")
            ),
            "sourcecraft-timeout",
            HTTPStatus.GATEWAY_TIMEOUT,
        ),
        (
            requests.ConnectionError(
                "private backend details", request=requests.Request("GET", "https://login.yandex.ru/info").prepare()
            ),
            "yandex-id",
            HTTPStatus.SERVICE_UNAVAILABLE,
        ),
        (
            OperationalError("private SQL", None, Exception("private backend details")),
            "database",
            HTTPStatus.SERVICE_UNAVAILABLE,
        ),
    ],
)
def test_dependency_failures_use_specific_copy(
    error_app: Flask, error: Exception, page: str, status: HTTPStatus
) -> None:
    error_app.extensions["test_failure"] = error
    client = error_app.test_client()
    response = client.get("/failure")
    assert response.status_code == status
    assert response.data == (ERROR_ASSETS / f"{page}.html").read_bytes()
    assert b"private backend details" not in response.data
    assert b"private SQL" not in response.data
    api = client.get("/api/_failure")
    assert api.status_code == status
    assert api.is_json
    assert ERROR_PAGES[page]["title"] in api.json["error"]
    assert "private backend details" not in api.json["error"]


def test_wrapped_timeout_keeps_provider_and_reason(error_app: Flask) -> None:
    error = GitlabConnectionError("private backend details")
    error.__cause__ = requests.ReadTimeout("secret URL")
    error_app.extensions["test_failure"] = error
    response = error_app.test_client().get("/failure")
    assert response.status_code == HTTPStatus.GATEWAY_TIMEOUT
    assert response.data == (ERROR_ASSETS / "gitlab-timeout.html").read_bytes()


@pytest.mark.parametrize(
    "error",
    [
        RuntimeError("GitLab is unavailable: private backend details"),
        GitlabGetError("private backend details", response_code=404),
        httpx.ConnectError("private backend details"),
        httpx.ConnectError(
            "private backend details", request=httpx.Request("GET", "https://gitlab.example.attacker.test/api")
        ),
    ],
)
def test_unknown_failures_do_not_guess_a_provider(error_app: Flask, error: Exception) -> None:
    error_app.extensions["test_failure"] = error
    response = error_app.test_client().get("/failure")
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.data == (ERROR_ASSETS / "internal.html").read_bytes()


def test_suppressed_context_does_not_blame_a_previous_failure(error_app: Flask) -> None:
    error = RuntimeError("private backend details")
    error.__context__ = GitlabConnectionError("a previous, handled failure")
    error.__suppress_context__ = True
    error_app.extensions["test_failure"] = error
    response = error_app.test_client().get("/failure")
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.data == (ERROR_ASSETS / "internal.html").read_bytes()


def test_auth_service_outage_is_not_an_expired_session(error_app: Flask) -> None:
    response = requests.Response()
    response.status_code = HTTPStatus.SERVICE_UNAVAILABLE
    response.request = requests.Request("GET", "https://gitlab.example/api/v4/user").prepare()
    response.url = response.request.url

    @error_app.get("/auth-check")
    def auth_check() -> str:
        def get_user(_token: str) -> requests.Response:
            return response

        def refresh() -> dict[str, Any] | None:
            pytest.fail("A backend outage must not refresh or discard the session")

        check_oauth_authenticated(get_user, refresh, "test-token", "test-refresh")
        return "OK"

    result = error_app.test_client().get("/auth-check")
    assert result.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert result.data == (ERROR_ASSETS / "gitlab.html").read_bytes()
