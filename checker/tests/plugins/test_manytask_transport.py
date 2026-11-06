from __future__ import annotations

from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from unittest.mock import patch

import pytest
import requests
from pydantic import AnyUrl

from checker.exceptions import PluginExecutionFailed
from checker.plugins.manytask import ManytaskPlugin


@pytest.fixture
def report_server() -> Iterator[tuple[AnyUrl, list[int], list[bytes]]]:
    statuses: list[int] = []
    bodies: list[bytes] = []

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            bodies.append(self.rfile.read(int(self.headers["Content-Length"])))
            status = statuses.pop(0) if statuses else 200
            self.send_response(status)
            self.end_headers()
            self.wfile.write(b'{"score": 1}')

        def log_message(self, format: str, *args: object) -> None:
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), Handler) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield (
                AnyUrl(f"http://127.0.0.1:{server.server_port}/report"),
                statuses,
                bodies,
            )
        finally:
            server.shutdown()
            thread.join()


def test_transient_post_is_retried_with_identical_body(
    report_server: tuple[AnyUrl, list[int], list[bytes]],
) -> None:
    url, statuses, bodies = report_server
    statuses.extend([503, 502, 200])
    with patch("urllib3.util.retry.Retry.sleep"):
        response = ManytaskPlugin._post_with_retries(
            url, {"score": 1, "allow_reduction": False}, None
        )
    assert response.status_code == 200
    assert len(bodies) == 3
    assert len(set(bodies)) == 1


@pytest.mark.parametrize(
    "status,allow_reduction,attempts",
    [(503, True, 1), (403, False, 1), (503, False, 4)],
)
def test_retries_are_bounded_and_do_not_replay_lowering_writes(
    report_server: tuple[AnyUrl, list[int], list[bytes]],
    status: int,
    allow_reduction: bool,
    attempts: int,
) -> None:
    url, statuses, bodies = report_server
    statuses.extend([status] * 5)
    with (
        patch("urllib3.util.retry.Retry.sleep"),
        pytest.raises(PluginExecutionFailed) as error,
    ):
        ManytaskPlugin._post_with_retries(
            url, {"allow_reduction": allow_reduction}, None
        )
    assert len(bodies) == attempts
    assert str(status) in str(error.value)
    assert error.value.output is not None
    assert '{"score": 1}' in error.value.output


def test_transport_sets_timeout_and_closes_session_on_failure() -> None:
    with patch("requests.Session") as session:
        client = session.return_value.__enter__.return_value
        client.post.side_effect = requests.ReadTimeout("synthetic timeout")
        with pytest.raises(PluginExecutionFailed, match="Unable to send score"):
            ManytaskPlugin._post_with_retries(
                AnyUrl("https://example.invalid"), {}, None
            )
        assert client.post.call_args.kwargs["timeout"] == (5, 30)
        session.return_value.__exit__.assert_called_once()
