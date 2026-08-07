# `checker` CLI reference

The `checker` command-line tool runs the course pipelines: it validates the repository,
tests the reference solutions, grades student submissions and exports tasks to the public
repository.

```bash
checker --help
checker --version
```

All commands take directory arguments:

| Argument | Meaning |
|---|---|
| `ROOT` | The repository being processed — the student checkout for `grade`, the private repo for `check`. |
| `REFERENCE_ROOT` | The private reference (gold solutions, hidden tests, configs). Defaults to `.`, and is `/opt/course` in the testenv image. |

Both `.checker.yml` and `.manytask.yml` are read from `REFERENCE_ROOT` for `grade` and from
`ROOT` for `check`/`validate`.

## `checker validate`

```bash
checker validate [ROOT]
```

Validates the configuration files, the mentioned plugins, and that every task in
`.manytask.yml` exists in the repository. Runs no tests.

| Option | Default | Description |
|---|---|---|
| `-v/-s`, `--verbose/--silent` | `-v` | Verbose output. |

## `checker check`

```bash
checker check [ROOT] [REFERENCE_ROOT]
```

Checks the **private** repository: runs `validate`, exports the tasks to a temporary
directory and runs the global and task pipelines against the reference solutions. The report
pipeline is always executed in dry-run, so `check` never reports scores.

| Option | Default | Description |
|---|---|---|
| `-t`, `--task` | — | Task name to check. Repeatable. |
| `-g`, `--group` | — | Group name to check; selects all of its tasks. Repeatable. |
| `-p`, `--parallelize` | on | Check tasks in parallel. |
| `-n`, `--num-processes` | CPU count | Number of parallel processes. |
| `--no-clean` | off | Keep the temporary directories. |
| `-v/-s`, `--verbose/--silent` | `-v` | Verbose test output. |
| `--dry-run` | off | Log the actions without executing them. |

With no `-t`/`-g` the whole course is checked.

## `checker grade`

```bash
checker grade [ROOT] [REFERENCE_ROOT]
```

Grades a **student** repository and reports the scores to the Manytask web app. This is the
command the `grade` job in the student `.gitlab-ci.yml` runs:

```yaml
grade:
  image: "$TESTENV_IMAGE"
  script:
    - checker grade . /opt/course
```

By default the tasks to grade are **detected from git** according to
[`changes_detection`](./checker_yml_reference.md#changes_detection) in `.checker.yml` — the
branch name, the last commit message, or the files changed in the last commit. This requires
`ROOT` to be a git repository.

| Option | Default | Description |
|---|---|---|
| `--all-tasks` | off | Grade **every enabled task**, ignoring changes detection. |
| `-t`, `--task` | — | Grade this task, ignoring changes detection. Repeatable. |
| `-g`, `--group` | — | Grade every task of this group, ignoring changes detection. Repeatable. |
| `--submit-score` | off | Report the scores to Manytask when the task selection is overridden. |
| `--no-firejail` | off | Run the tested code without the firejail sandbox (firejail is Linux-only). |
| `--timestamp` | now, `Europe/Moscow` | Submission timestamp (ISO 8601), used to compute the deadline penalty. |
| `--username` | — | Username to submit for. |
| `--branch` | — | Branch name to use when the checkout is in a detached HEAD state. |
| `--no-clean` | off | Keep the temporary directories. |
| `-v/-s`, `--verbose/--silent` | `-s` | Verbose test output. |
| `--dry-run` | off | Log the actions without executing them. |

### Overriding task detection

`--all-tasks`, `--task` and `--group` **skip changes detection entirely**. Since detection is
the only thing that needs git, an overridden run also works in a directory that is not a git
repository at all.

`--all-tasks` cannot be combined with `-t`/`-g`; `-t` and `-g` can be combined and their
results are merged.

> **Overridden runs do not report scores.** The report pipeline is executed in dry-run and
> the output says `->Reporting disabled (dry-run)`. Add `--submit-score` to actually submit.
> Runs without an override (i.e. normal CI runs) report as before.

Only **enabled** tasks are graded — a task must exist both in the filesystem and in
`.manytask.yml` under a group with `enabled: true`. Tasks of disabled groups are silently
skipped by `--all-tasks` and rejected by `-t`/`-g`.

### Running without firejail

The `safe_run_script` plugin sandboxes student code with
[firejail](https://firejail.wordpress.com/), which is **Linux-only**. On macOS, or any host
without it, every such stage fails with `[Errno 2] No such file or directory: 'firejail'`.
`--no-firejail` skips the sandbox and runs the script directly:

```bash
checker grade student-solution /path/to/private-repo --all-tasks --no-firejail
```

Failing scripts still fail — the flag removes the sandbox, not the verdict.

> **This executes untrusted student code unsandboxed**, with your user's full network and
> filesystem access. Use it only on code you are willing to run directly, and never in CI —
> install firejail on the Linux runner instead.

The same switch exists per stage: `allow_fallback: true` on a `safe_run_script` stage in
`.checker.yml` falls back automatically whenever firejail is missing.

`--no-firejail` is also available on `checker check`.

### Local grading can write into your private repository

A task pipeline may copy the student's files into the reference tree, for example:

```yaml
- name: Copy files
  run: copy_files
  args:
    target_dir: ${{ global.ref_dir + '/' + task.task_sub_path }}
```

In CI `ref_dir` is a throwaway copy inside the container, so this is harmless. Locally it is
**your real clone of the private repository**, and grading will overwrite the reference
solutions with the student's ones — `--all-tasks` does it for every task at once.

Before grading locally, make sure the private repo is committed and clean, then check
`git status` afterwards and `git checkout --` anything the run modified. Alternatively point
`REFERENCE_ROOT` at a disposable copy:

```bash
cp -R private-repo /tmp/ref && checker grade student-solution /tmp/ref --all-tasks --no-firejail
```

### Grading a student repository locally

To grade every task in a student's checkout on your own machine, without touching the
scores stored in Manytask:

```bash
git clone <student-repo> student-solution
checker grade student-solution /path/to/private-repo --all-tasks -v
```

Or, using the testenv image that already carries the private reference at `/opt/course`:

```bash
docker run --rm -v "$PWD/student-solution:/solution" "$TESTENV_IMAGE" \
  checker grade /solution /opt/course --all-tasks
```

Grade a single task or a single group:

```bash
checker grade student-solution /path/to/private-repo -t add_cpp
checker grade student-solution /path/to/private-repo -g cpp
```

Grade everything **and** submit the resulting scores:

```bash
checker grade student-solution /path/to/private-repo --all-tasks --submit-score \
  --username <student-login>
```

Reporting additionally requires the `report_pipeline` to be configured in `.checker.yml` and
a valid `MANYTASK_TOKEN` in the environment — see
[`report_score_manytask`](./checker_plugins.md).

## `checker export`

```bash
checker export [REFERENCE_ROOT] [EXPORT_ROOT]
```

Exports the public files from the private repository into `EXPORT_ROOT` (default `./export`),
applying the template strategy and the public/private patterns from `.checker.yml`. Everything
in `EXPORT_ROOT` except `.git` is deleted first.

| Option | Default | Description |
|---|---|---|
| `--commit` | off | Commit and push the result to the export destination. |
| `--dry-run` | off | Log the actions without executing them. |

## `checker export-private`

```bash
checker export-private [REFERENCE_ROOT] [EXPORT_ROOT]
```

Exports the **full private** reference — gold solutions, filled templates, public and private
tests — into `EXPORT_ROOT`. Used when building the testenv image to bake the reference into
`/opt/course`.

| Option | Default | Description |
|---|---|---|
| `--dry-run` | off | Log the actions without executing them. |

## See also

- [`.checker.yml` reference](./checker_yml_reference.md)
- [`.manytask.yml` reference](./manytask_yml_reference.md)
- [Checker built-in plugins](./checker_plugins.md)
