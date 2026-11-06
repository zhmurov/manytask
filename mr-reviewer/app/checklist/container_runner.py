"""Disposable Docker execution without host mounts, network, or credentials."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from loguru import logger


class SandboxExecutionError(RuntimeError):
    """Runner infrastructure failed; never fall back to executing on the host."""


@dataclass(frozen=True)
class RunnerCommand:
    argv: tuple[str, ...]
    env: dict[str, str] | None = None


class DockerCommandRunner:
    def __init__(self, image: str = "python:3.14-slim") -> None:
        self._image = image

    @staticmethod
    async def _docker(*args: str) -> None:
        try:
            proc = await asyncio.create_subprocess_exec(
                "docker",
                *args,
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.DEVNULL,
            )
        except OSError as error:
            raise SandboxExecutionError("Docker runner is unavailable") from error
        try:
            await asyncio.wait_for(proc.wait(), timeout=30)
        except TimeoutError, asyncio.CancelledError:
            if proc.returncode is None:
                proc.kill()
            await proc.wait()
            raise
        if proc.returncode:
            raise SandboxExecutionError(f"Docker runner {args[0]} failed (exit {proc.returncode})")

    @asynccontextmanager
    async def command(self, workdir: Path, command: str, env: dict[str, str]) -> AsyncIterator[RunnerCommand]:
        name = f"manytask-run-{uuid4().hex}"
        # cp transfers a snapshot; no host bind mounts or Docker socket enter
        # the container. Root-owned input is copied to writable tmpfs by
        # the unprivileged process, so compilers/tests can create their outputs.
        env_args = [arg for key, value in env.items() for arg in ("--env", f"{key}={value}")]
        created = False
        try:
            await self._docker(
                "create",
                "--name",
                name,
                "--label",
                "manytask.runner=true",
                "--pull",
                "never",
                "--network",
                "none",
                "--read-only",
                "--cap-drop",
                "ALL",
                "--security-opt",
                "no-new-privileges",
                "--pids-limit",
                "64",
                "--memory",
                "256m",
                "--memory-swap",
                "256m",
                "--cpus",
                "1",
                "--user",
                "65534:65534",
                "--log-driver",
                "none",
                "--tmpfs",
                "/tmp:rw,nosuid,nodev,size=128m,mode=1777",
                "--volume",
                "/input",
                "--workdir",
                "/tmp",
                "--entrypoint",
                "/bin/bash",
                *env_args,
                self._image,
                "-c",
                'mkdir /tmp/work && cp -R /input/. /tmp/work/ && cd /tmp/work && exec bash -c "$1"',
                "--",
                command,
            )
            created = True
            await self._docker("cp", f"{workdir}/.", f"{name}:/input")
            # Docker CLI inherits its connection settings; only env_args above
            # are passed through to the command container.
            yield RunnerCommand(("docker", "start", "--attach", name))
        finally:
            try:
                await self._docker("rm", "--force", "--volumes", name)
            except SandboxExecutionError:
                logger.error("Cannot remove runner container {}; check the runner daemon", name)
                if created:
                    raise
