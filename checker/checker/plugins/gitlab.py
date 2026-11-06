from __future__ import annotations

from pydantic import AnyUrl

from checker.exceptions import PluginExecutionFailed

from .base import PluginABC, PluginOutput


class CheckGitlabMergeRequestPlugin(PluginABC):
    """Plugin for checking gitlab merge request."""

    name = "check_gitlab_merge_request"

    class Args(PluginABC.Args):
        token: str
        task_dir: str
        repo_url: AnyUrl
        require_approval: bool = False
        search_for_score: bool = False

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        raise PluginExecutionFailed(
            "GitLab merge request checks are not implemented",
            output="GitLab merge request checks are unavailable; no score was awarded.",
        )


class CollectScoreGitlabMergeRequestPlugin(PluginABC):
    """Plugin for collecting score from gitlab merge request."""

    name = "collect_score_gitlab_merge_request"

    class Args(PluginABC.Args):
        token: str
        task_dir: str
        repo_url: AnyUrl
        require_approval: bool = False
        search_for_score: bool = False

    def _run(self, args: Args, *, verbose: bool = False) -> PluginOutput:  # type: ignore[override]
        raise PluginExecutionFailed(
            "GitLab merge request score collection is not implemented",
            output="GitLab merge request score collection is unavailable; no score was awarded.",
        )
