from __future__ import annotations

import pytest

from checker.exceptions import PluginExecutionFailed
from checker.plugins.base import PluginABC
from checker.plugins.gitlab import (
    CheckGitlabMergeRequestPlugin,
    CollectScoreGitlabMergeRequestPlugin,
)


@pytest.mark.parametrize(
    "plugin_class",
    [CheckGitlabMergeRequestPlugin, CollectScoreGitlabMergeRequestPlugin],
)
@pytest.mark.parametrize("require_approval", [True, False])
def test_unimplemented_gitlab_plugins_fail_closed(
    plugin_class: type[PluginABC], require_approval: bool
) -> None:
    with pytest.raises(PluginExecutionFailed, match="not implemented") as error:
        plugin_class().run(
            {
                "token": "synthetic-token",
                "task_dir": "task",
                "repo_url": "https://gitlab.example/course/student",
                "require_approval": require_approval,
                "search_for_score": True,
            }
        )
    assert error.value.percentage == 0
    assert error.value.output is not None
    assert "no score was awarded" in error.value.output
