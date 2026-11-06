"""Opt-in tests of the real Docker isolation boundary; no GitLab/network needed."""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from app.checklist.container_runner import SandboxExecutionError
from app.checklist.sandbox import RunSandbox
from app.checklist.step import CheckContext
from app.hosting import FileChange, MergeRequest
from tests._fakes import FakeHostingAdapter
from tests.test_checklist_sandbox import bare_remote as bare_remote
from tests.test_checklist_sandbox import sample_mr_for_sandbox as sample_mr_for_sandbox

pytestmark = pytest.mark.skipif(os.getenv("RUN_DOCKER_TESTS") != "1", reason="opt-in real Docker runner tests")


@pytest.fixture
def docker_sandbox(bare_remote: Path) -> RunSandbox:
    hosting = FakeHostingAdapter()
    hosting.changes = [FileChange("tasks/task-1/main.py", "tasks/task-1/main.py", False, False, False, "")]
    return RunSandbox(
        hosting=hosting,
        gitlab_base_url="file://",
        gitlab_token="synthetic-gitlab",
        manytask_base_url="https://example.invalid",
        timeout_sec=20,
        clone_url_builder=lambda mr: f"file://{bare_remote}",
    )


async def test_real_container_has_no_credentials_network_or_host_access(
    docker_sandbox: RunSandbox,
    sample_mr_for_sandbox: MergeRequest,
    sample_ctx: CheckContext,
) -> None:
    command = """python3 - <<'CHECK'
import os
import socket
from pathlib import Path
assert os.getuid() == 65534
assert 'MANYTASK_COURSE_TOKEN' not in os.environ
assert 'GITLAB_TOKEN' not in os.environ
assert not Path('/var/run/docker.sock').exists()
assert not Path('/app').exists()
assert not Path('.git').exists()
assert not os.access('/input', os.W_OK)
assert Path('tasks/task-1/main.py').read_text() == "print('task-1')\\n"
Path('output.txt').write_text('works')
try:
    Path('/forbidden').write_text('must fail')
except OSError:
    pass
else:
    raise AssertionError('root filesystem is writable')
try:
    socket.create_connection(('1.1.1.1', 53), timeout=0.2)
except OSError:
    pass
else:
    raise AssertionError('network access is enabled')
print('isolated')
CHECK"""
    result = await docker_sandbox.run(mr=sample_mr_for_sandbox, command=command, ctx=sample_ctx)
    assert result.exit_code == 0, result.stderr
    assert result.stdout.strip() == b"isolated"


@pytest.mark.parametrize("cancel", [False, True])
async def test_real_runner_removes_container_on_timeout_or_cancellation(
    docker_sandbox: RunSandbox,
    sample_mr_for_sandbox: MergeRequest,
    sample_ctx: CheckContext,
    cancel: bool,
) -> None:
    docker_sandbox._timeout_sec = 0.2 if not cancel else 60
    started = asyncio.Event()
    create = asyncio.create_subprocess_exec

    async def observe(*args: str, **kwargs: Any) -> asyncio.subprocess.Process:
        process = await create(*args, **kwargs)
        if args[:2] == ("docker", "start"):
            started.set()
        return process

    with (
        patch.object(docker_sandbox._runner, "_docker", wraps=docker_sandbox._runner._docker) as docker,
        patch("asyncio.create_subprocess_exec", side_effect=observe),
    ):
        task = asyncio.create_task(docker_sandbox.run(mr=sample_mr_for_sandbox, command="sleep 60", ctx=sample_ctx))
        await asyncio.wait_for(started.wait(), timeout=30)
        if cancel:
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            result = await task
            assert result.timed_out
        create_args = docker.call_args_list[0].args
        name = create_args[create_args.index("--name") + 1]
    with pytest.raises(SandboxExecutionError):
        await docker_sandbox._runner._docker("inspect", name)


async def test_missing_image_never_runs_on_host(
    docker_sandbox: RunSandbox,
    sample_mr_for_sandbox: MergeRequest,
    sample_ctx: CheckContext,
    tmp_path: Path,
) -> None:
    docker_sandbox._runner._image = "manytask-deliberately-missing:synthetic"
    marker = tmp_path / "host-marker"
    with pytest.raises(SandboxExecutionError):
        await docker_sandbox.run(mr=sample_mr_for_sandbox, command=f"touch {marker}", ctx=sample_ctx)
    assert not marker.exists()
