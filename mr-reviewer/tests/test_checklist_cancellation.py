from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Any
from unittest.mock import patch

import pytest

from app.checklist.sandbox import RunSandbox
from app.checklist.step import CheckContext
from app.hosting import MergeRequest
from tests._fakes import FakeHostingAdapter


@pytest.mark.parametrize("outer_timeout", [False, True])
async def test_cancellation_reaps_command_and_removes_workspace(
    outer_timeout: bool,
) -> None:
    sandbox = RunSandbox(
        hosting=FakeHostingAdapter(),
        gitlab_base_url="https://example.invalid",
        gitlab_token="synthetic",
        manytask_base_url="https://example.invalid",
        timeout_sec=60,
    )
    mr = MergeRequest(1, 1, "sha", "url", "task", "main", "student", (), "task", "group/repo")
    started = asyncio.Event()
    processes: list[asyncio.subprocess.Process] = []
    workspaces: list[Path] = []
    create_process = asyncio.create_subprocess_exec

    async def capture_process(*args: str, **kwargs: Any) -> asyncio.subprocess.Process:
        process = await create_process(*args, **kwargs)
        processes.append(process)
        workspaces.append(Path(kwargs["cwd"]))
        started.set()
        return process

    with (
        patch.object(sandbox, "_sparse_clone_blocking"),
        patch("app.checklist.sandbox.asyncio.create_subprocess_exec", side_effect=capture_process),
        patch.object(sandbox, "_kill_process_group", wraps=sandbox._kill_process_group) as kill,
    ):
        task = asyncio.create_task(sandbox.run(mr=mr, command="sleep 60", ctx=CheckContext("course", "synthetic")))
        try:
            await asyncio.wait_for(started.wait(), timeout=5)
            if outer_timeout:
                with pytest.raises(TimeoutError):
                    await asyncio.wait_for(task, timeout=0.05)
            else:
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            kill.assert_called_once_with(processes[0])
            assert processes[0].returncode is not None
            assert not workspaces[0].exists()
        finally:
            # Avoid leaving a sleeper behind if this regression ever fails.
            for process in processes:
                if process.returncode is None:
                    sandbox._kill_process_group(process)
                    await process.communicate()
            if not task.done():
                task.cancel()
                await asyncio.gather(task, return_exceptions=True)
