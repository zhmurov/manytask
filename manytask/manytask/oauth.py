"""Shared OAuth request validation and Flask session refresh handling."""

import logging
from http import HTTPStatus
from typing import Any, Callable

from authlib.integrations.base_client import OAuthError
from flask import session
from requests import Response
from requests.exceptions import HTTPError

logger = logging.getLogger(__name__)


def check_oauth_authenticated(
    make_auth_request: Callable[[str], Response],
    refresh_token_fn: Callable[[], dict[str, Any] | None],
    oauth_access_token: str,
    oauth_refresh_token: str,
    log_prefix: str = "",
) -> bool:
    response = make_auth_request(oauth_access_token)

    try:
        response.raise_for_status()
        return True
    except HTTPError as e:
        if e.response.status_code == HTTPStatus.UNAUTHORIZED:
            try:
                logger.info("%sAccess token expired. Trying to refresh token.", log_prefix)

                new_tokens = refresh_token_fn()
                if not new_tokens:
                    return False

                new_access = new_tokens.get("access_token", "")
                new_refresh = new_tokens.get("refresh_token", oauth_refresh_token)

                response = make_auth_request(new_access)
                response.raise_for_status()

                session["auth"].update({"access_token": new_access, "refresh_token": new_refresh})
                logger.info("%sToken refreshed successfully.", log_prefix)

                return True
            except (HTTPError, OAuthError):
                logger.error("Failed to refresh %stoken", log_prefix, exc_info=True)
                return False

        logger.info("User is not logged in: %s", e, exc_info=True)
        return False
