from http import HTTPStatus
from unittest.mock import patch

import pytest
from flask import Flask, Response, abort, jsonify

from manytask.errors import ERROR_PAGE
from manytask.main import create_app


@pytest.fixture
def error_app() -> Flask:
    with (
        patch("manytask.main._database_storage_setup"),
        patch("manytask.main.logging.config.dictConfig"),
    ):
        app = create_app(test=True)
    app.config.update(PROPAGATE_EXCEPTIONS=False, WTF_CSRF_ENABLED=False)

    @app.route("/failure", methods=["GET", "POST"])
    @app.route("/api/_failure", methods=["GET", "POST"])
    @app.route("/api", methods=["GET", "POST"])
    def failure() -> str:
        raise RuntimeError("private backend details")

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
    assert response.data == ERROR_PAGE.read_bytes()
    assert b"private backend details" not in response.data
    assert response.headers["Cache-Control"] == "no-store"


@pytest.mark.parametrize("status", [500, 502, 503, 504])
def test_server_errors_keep_status(error_app: Flask, status: int) -> None:
    response = error_app.test_client().get(f"/status/{status}")
    assert response.status_code == status
    assert b"Manytask is taking" in response.data


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
    assert response.json == {"error": "Manytask is temporarily unavailable. Please try again later."}
    assert response.headers["Cache-Control"] == "no-store"


def test_existing_api_response_is_preserved(error_app: Flask) -> None:
    response = error_app.test_client().get("/api/_explicit")
    assert response.status_code == HTTPStatus.SERVICE_UNAVAILABLE
    assert response.json == {"error": "An existing API error"}


@pytest.mark.parametrize("status", [403, 404])
def test_client_errors_are_not_replaced(error_app: Flask, status: int) -> None:
    response = error_app.test_client().get(f"/status/{status}")
    assert response.status_code == status
    assert b"Manytask is taking" not in response.data


def test_browser_accepting_any_type_gets_html(error_app: Flask) -> None:
    response = error_app.test_client().get("/failure", headers={"Accept": "*/*"})
    assert response.status_code == HTTPStatus.INTERNAL_SERVER_ERROR
    assert response.mimetype == "text/html"
