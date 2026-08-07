from __future__ import annotations

import os
from pathlib import Path
from typing import Optional, Union

from checker.exceptions import PluginExecutionFailed

from .base import PluginOutput
from .scripts import PluginABC, RunScriptPlugin

HOME_PATH = str(Path.home())

# Process-local kill switch for the sandbox, set only by the `--no-firejail` CLI flag.
#
# Deliberately NOT an environment variable: the environment is attacker-controlled in the
# threat model this sandbox exists for. Students own the `.gitlab-ci.yml` of their repository
# and can define arbitrary CI variables, so an env-var switch could be flipped by the very
# code being sandboxed, and would silently propagate into every subprocess. A module global
# can only be set by an explicit CLI argument in this process.
_firejail_disabled = False


def disable_firejail() -> None:
    """Disable firejail sandboxing for this process (`--no-firejail`).

    Must only be called from CLI argument handling, never from config or the environment.
    """
    global _firejail_disabled
    _firejail_disabled = True


def is_firejail_disabled() -> bool:
    """Whatever firejail sandboxing is disabled for this process."""
    return _firejail_disabled


class SafeRunScriptPlugin(PluginABC):
    """Wrapper over RunScriptPlugin to run students scripts safety.
    Plugin uses Firejail tool to create sandbox for the running process.
    It allows hide environment variables and control access to network and file system.
    If `allow_fallback=True` then if Firejail is not installed, it will fallback to RunScriptPlugin.
    """

    name = "safe_run_script"

    class Args(PluginABC.Args):
        origin: str
        script: Union[
            str, list[str]
        ]  # as pydantic does not support | in older python versions
        timeout: Union[float, None] = (
            None  # as pydantic does not support | in older python versions
        )
        input: Optional[Path] = None

        env_additional: dict[str, str] = dict()
        env_whitelist: list[str] = list()
        paths_whitelist: list[str] = list()
        lock_network: bool = True
        allow_fallback: bool = False
        paths_blacklist: list[str] = list()

    def _check_firejail_available(self) -> tuple[bool, str]:
        """Check if firejail is available.

        Returns:
            tuple: (is_available, error_output)
        """
        import subprocess

        result = subprocess.run(["firejail", "--version"], capture_output=True)
        return result.returncode == 0, result.stderr.decode("utf-8")

    def _fallback_to_run_script(
        self, args: Args, verbose: bool, reason: str = "Firejail is not installed"
    ) -> PluginOutput:
        """Fallback to RunScriptPlugin when firejail is not available or disabled."""
        run_args = RunScriptPlugin.Args(
            origin=args.origin,
            script=args.script,
            timeout=args.timeout,
            env_additional=args.env_additional,
            env_whitelist=args.env_whitelist,
        )
        output = RunScriptPlugin()._run(args=run_args, verbose=verbose)
        if verbose:
            output.output = f"{reason}. Fallback to RunScriptPlugin.\n{output.output}"
        return output

    def _build_whitelist_paths(self, args: Args) -> set[str]:
        """Build the set of paths to whitelist.

        Collect all allow paths.
        """
        allow_paths = {*args.paths_whitelist, args.origin}
        # a bit tricky but if paths is only /tmp add ~/tmp instead of it
        if "/tmp" in allow_paths and len(allow_paths) == 1:
            allow_paths.add("~/tmp")
        # remove /tmp from paths as it causes error inside Firejail
        allow_paths.discard("/tmp")
        return allow_paths

    def _expand_path(self, path: str) -> str:
        """Expand ~ to full home path.

        Replace ~ by the full home path.
        """
        return path if not path.startswith("~") else HOME_PATH + path[1:]

    def _build_firejail_command(self, args: Args) -> list[str]:
        """Build the firejail command with all options.

        Construct firejail command.
        """
        command: list[str] = [
            "firejail",
            "--quiet",
            "--noprofile",
            "--deterministic-exit-code",
        ]

        # lock network access
        if args.lock_network:
            command.append("--net=none")

        # Add whitelist paths
        # allow access to origin dir
        for path in self._build_whitelist_paths(args):
            command.append(f"--whitelist={self._expand_path(path)}")

        # Add blacklist paths
        for path in args.paths_blacklist:
            command.append(f"--blacklist={self._expand_path(path)}")

        # Hide all environment variables except allowed
        command += ["env", "-i"]
        env: dict[str, str] = {e: os.environ.get(e, "") for e in args.env_whitelist}
        env.update(args.env_additional)
        for e, v in env.items():
            command.append(f"{e}={v}")

        # create actual command
        if isinstance(args.script, str):
            command.append(args.script)
        elif isinstance(args.script, list):
            command += args.script
        else:
            assert False, "Not Reachable"

        return command

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        # sandboxing explicitly disabled from the CLI (`--no-firejail`)
        if is_firejail_disabled():
            return self._fallback_to_run_script(
                args, verbose, reason="Firejail disabled by --no-firejail"
            )

        # test if firejail script is available
        # TODO: test fallback
        is_available, error_output = self._check_firejail_available()
        if not is_available:
            if args.allow_fallback:
                return self._fallback_to_run_script(args, verbose)
            raise PluginExecutionFailed(
                "Firejail is not installed", output=error_output
            )

        command = self._build_firejail_command(args)

        # Will use RunScriptPlugin to run Firejail+command
        run_args = RunScriptPlugin.Args(
            origin=args.origin,
            script=command,
            timeout=args.timeout,
            env_additional={},
            env_whitelist=None,
            input=args.input,
        )
        return RunScriptPlugin()._run(args=run_args, verbose=verbose)
