from __future__ import annotations

import asyncio
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.checklist.container_runner import DockerCommandRunner, SandboxExecutionError


async def test_container_is_isolated_and_removed(tmp_path: Path) -> None:
    runner = DockerCommandRunner("approved@sha256:synthetic")
    with patch.object(runner, "_docker", new_callable=AsyncMock) as docker:
        async with runner.command(tmp_path, "echo ok", {"COURSE_NAME": "course"}) as command:
            create = docker.call_args_list[0].args
            assert create[create.index("--network") + 1] == "none"
            assert create[create.index("--user") + 1] == "65534:65534"
            assert create[create.index("--cap-drop") + 1] == "ALL"
            assert create[create.index("--pull") + 1] == "never"
            assert create[create.index("--memory") + 1] == "256m"
            assert "--read-only" in create
            assert "no-new-privileges" in create
            assert create[create.index("--volume") + 1] == "/input"
            assert "--mount" not in create
            assert "approved@sha256:synthetic" in create
            name = create[create.index("--name") + 1]
            assert command.argv == ("docker", "start", "--attach", name)
            assert docker.call_args_list[1].args == ("cp", f"{tmp_path}/.", f"{name}:/input")
        assert docker.call_args.args == ("rm", "--force", "--volumes", name)


@pytest.mark.parametrize("failure", [RuntimeError, asyncio.CancelledError])
async def test_runner_cleanup_on_execution_failure(tmp_path: Path, failure: type[BaseException]) -> None:
    runner = DockerCommandRunner()
    with patch.object(runner, "_docker", new_callable=AsyncMock) as docker:
        with pytest.raises(failure):
            async with runner.command(tmp_path, "sleep 60", {}):
                raise failure()
        assert docker.call_args.args[0:2] == ("rm", "--force")


async def test_copy_failure_removes_created_container(tmp_path: Path) -> None:
    runner = DockerCommandRunner()
    with patch.object(runner, "_docker", new_callable=AsyncMock) as docker:
        docker.side_effect = [None, SandboxExecutionError("copy failed"), None]
        with pytest.raises(SandboxExecutionError, match="copy failed"):
            async with runner.command(tmp_path, "true", {}):
                pytest.fail("must not execute after copy failure")
        assert docker.call_args.args[0:2] == ("rm", "--force")


async def test_missing_docker_fails_closed() -> None:
    with patch("asyncio.create_subprocess_exec", side_effect=FileNotFoundError):
        with pytest.raises(SandboxExecutionError, match="unavailable"):
            await DockerCommandRunner._docker("create")


async def test_docker_nonzero_is_a_runner_failure() -> None:
    process = MagicMock()
    process.wait = AsyncMock()
    process.returncode = 1
    with patch("asyncio.create_subprocess_exec", return_value=process):
        with pytest.raises(SandboxExecutionError, match="create failed"):
            await DockerCommandRunner._docker("create")


async def test_docker_setup_cancellation_reaps_cli() -> None:
    process = MagicMock()
    process.wait = AsyncMock()
    process.returncode = None
    process.wait.side_effect = [asyncio.CancelledError(), 0]
    with patch("asyncio.create_subprocess_exec", return_value=process):
        with pytest.raises(asyncio.CancelledError):
            await DockerCommandRunner._docker("create")
    process.kill.assert_called_once()
    assert process.wait.await_count == 2
