"""Backend error responses that do not depend on templates, sessions, or storage."""

from http import HTTPStatus
from urllib.parse import urlsplit

import httpx
import requests
from flask import Flask, Response, current_app, jsonify, request, send_file
from gitlab.exceptions import GitlabAuthenticationError, GitlabConnectionError, GitlabError
from sqlalchemy.exc import InterfaceError, OperationalError
from sqlalchemy.exc import TimeoutError as DatabaseTimeoutError
from werkzeug.exceptions import HTTPException

from .error_pages import ERROR_ASSETS, ERROR_PAGES

ERROR_PAGE = ERROR_ASSETS / "50x.html"
_TIMEOUTS = (requests.Timeout, httpx.TimeoutException, DatabaseTimeoutError)
_SERVICE_SETTINGS = {
    "gitlab": ("gitlab_url", "gitlab_oauth_url"),
    "sourcecraft": ("sourcecraft_url", "sourcecraft_api_url"),
    "yandex-id": ("yandex_id_oauth_base",),
}


def _exception_chain(error: BaseException) -> list[BaseException]:
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        current = current.__cause__ or (None if current.__suppress_context__ else current.__context__)
    return chain


def _service_for_url(url: str) -> str | None:
    config = getattr(current_app, "app_config", None)
    try:
        hostname = urlsplit(url).hostname
        if hostname == "login.yandex.ru":
            return "yandex-id"
        for service, settings in _SERVICE_SETTINGS.items():
            for setting in settings:
                configured_url = getattr(config, setting, None)
                if isinstance(configured_url, str) and hostname and hostname == urlsplit(configured_url).hostname:
                    return service
    except ValueError:
        pass
    return None


def _http_service(error: BaseException) -> tuple[str, bool] | None:
    if not isinstance(error, (requests.RequestException, httpx.HTTPError)):
        return None
    try:
        failed_request = error.request
    except RuntimeError:  # httpx exceptions may not have an attached request.
        return None
    if failed_request is None:
        return None
    service = _service_for_url(str(failed_request.url))
    if service is None:
        return None
    response = getattr(error, "response", None)
    status = response.status_code if response is not None else None
    denied = status in (HTTPStatus.UNAUTHORIZED, HTTPStatus.FORBIDDEN)
    transport_failure = isinstance(error, (requests.ConnectionError, requests.Timeout, httpx.TransportError))
    if denied or transport_failure or (status is not None and status >= HTTPStatus.INTERNAL_SERVER_ERROR):
        return service, denied
    return None


def _service_failure(error: BaseException) -> tuple[str, bool] | None:
    if isinstance(error, GitlabError):
        denied = isinstance(error, GitlabAuthenticationError) or error.response_code in (
            HTTPStatus.UNAUTHORIZED,
            HTTPStatus.FORBIDDEN,
        )
        if (
            denied
            or isinstance(error, GitlabConnectionError)
            or (error.response_code or 0) >= HTTPStatus.INTERNAL_SERVER_ERROR
        ):
            return "gitlab", denied
    return _http_service(error)


def _error_details(error: HTTPException) -> tuple[str, int]:
    original = getattr(error, "original_exception", None)
    chain = _exception_chain(original or error)
    timed_out = any(isinstance(item, _TIMEOUTS) for item in chain)
    for item in chain:
        if isinstance(item, (OperationalError, InterfaceError)):
            return "database", HTTPStatus.SERVICE_UNAVAILABLE
        failure = _service_failure(item)
        if failure is not None:
            service, denied = failure
            if denied:
                return f"{service}-access", HTTPStatus.BAD_GATEWAY
            if timed_out:
                return f"{service}-timeout", HTTPStatus.GATEWAY_TIMEOUT
            return service, HTTPStatus.SERVICE_UNAVAILABLE
    if timed_out:
        return "timeout", HTTPStatus.GATEWAY_TIMEOUT
    status = error.code or HTTPStatus.INTERNAL_SERVER_ERROR
    pages = {500: "internal", 502: "unavailable", 503: "unavailable", 504: "timeout"}
    return pages.get(status, "50x"), status


def register_error_handlers(app: Flask) -> None:
    for status in (500, 502, 503, 504):
        app.register_error_handler(status, backend_error)


def backend_error(error: HTTPException) -> Response:
    page_name, status = _error_details(error)
    page = ERROR_PAGES[page_name]
    accepts = request.accept_mimetypes
    if (
        request.path == "/api"
        or request.path.startswith("/api/")
        or request.is_json
        or accepts["application/json"] > accepts["text/html"]
    ):
        response = jsonify(error=f"{page['title']}. {page['description']}")
    else:
        # Sending a static document also avoids application context processors,
        # which may themselves be affected by the backend failure.
        response = send_file(ERROR_ASSETS / f"{page_name}.html", conditional=False, max_age=0)
    response.status_code = status
    response.headers["Cache-Control"] = "no-store"
    return response
