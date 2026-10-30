"""Backend error responses that do not depend on templates, sessions, or storage."""

from pathlib import Path

from flask import Flask, Response, jsonify, request, send_file
from werkzeug.exceptions import HTTPException

ERROR_PAGE = Path(__file__).parent / "static" / "errors" / "50x.html"


def register_error_handlers(app: Flask) -> None:
    for status in (500, 502, 503, 504):
        app.register_error_handler(status, backend_error)


def backend_error(error: HTTPException) -> Response:
    accepts = request.accept_mimetypes
    if (
        request.path == "/api"
        or request.path.startswith("/api/")
        or request.is_json
        or accepts["application/json"] > accepts["text/html"]
    ):
        response = jsonify(error="Manytask is temporarily unavailable. Please try again later.")
    else:
        # Sending a static document also avoids application context processors,
        # which may themselves be affected by the backend failure.
        response = send_file(ERROR_PAGE, conditional=False, max_age=0)
    response.status_code = error.code or 500
    response.headers["Cache-Control"] = "no-store"
    return response
