# Setting up `.releaser-ci.yml`

`.releaser-ci.yml` is the CI pipeline of the **private (teacher) repository**. It is the release
mechanism of a *Course as Code* course: everything a teacher pushes to `main` becomes visible to
students only after this pipeline runs.

It does four things, in order:

1. **validate** — sanity-check `.checker.yml`, `.manytask.yml` and every task,
2. **build** — build the course *testenv* Docker image and push it to the container registry,
3. **test** — run the reference solution through public **and** private tests inside that image,
4. **deploy** — export public files to the student repository, push the schedule to the Manytask
   web app, and (optionally) deliver the review-bot config.

This page walks through the file section by section. The working version it is based on lives at
[`course-template/.releaser-ci.yml`](https://github.com/manytask/manytask/blob/main/course-template/.releaser-ci.yml)
— copy it and change the handful of values listed in [What you must change](#what-you-must-change).

> **Two CI files, two repositories.** `.releaser-ci.yml` runs in the **private** repo and is *never*
> exported. `.gitlab-ci.yml` runs in the **public/student** repo and grades submissions. They are
> separate files with separate jobs; see [Course template](./course_template.md) for the whole picture.

## Prerequisites

Before the pipeline can go green you need:

- a private project (this repo) and a public project (`export.destination` in `.checker.yml`),
- the **Container Registry enabled** on the private project,
- a **deploy token** named exactly `gitlab-deploy-token` on the private project,
- CI/CD variables `GITLAB_API_TOKEN` and `MANYTASK_TOKEN`,
- a `testenv.docker` in the repo root.

All of these are explained below.

## The pipeline skeleton

```yaml
stages:
  - validate
  - build
  - test
  - deploy

variables:
  PIP_CACHE_DIR: "${CI_PROJECT_DIR}/.cache/pip"
  CHECKER_PIP_SPEC: "git+https://github.com/manytask/manytask.git@<commit-sha>#subdirectory=checker"
```

### `CHECKER_PIP_SPEC`

Every job that needs the checker installs it from this single variable, so there is exactly one
place to bump the checker version — the CI jobs *and*
[`testenv.docker`](./course_template.md#how-grading-works-testenv-image), which receives it as a
build argument.

The checker is installed **from the monorepo at a pinned commit, not from PyPI**: the published
PyPI release predates the monorepo checker and lacks the `validate` / `export` / `export-private`
commands this pipeline relies on. Pin a commit SHA rather than a branch so a pipeline re-run months
later still builds the same course.

The jobs install `pytest` alongside it (`pip install "$CHECKER_PIP_SPEC" pytest`): the checker is
runner-agnostic and does not bundle a test runner, so the course supplies its own.

## Stage 1 — `validate`

```yaml
validate:
  image: python:3.12-slim
  stage: validate
  before_script:
    - apt-get update -qq && apt-get install -y --no-install-recommends git && rm -rf /var/lib/apt/lists/*
    - python -m pip install --upgrade pip
    - pip install "$CHECKER_PIP_SPEC" pytest
  script:
    - checker validate
```

`checker validate` checks the configuration files, the plugins they reference, the course structure,
the exporter and the tester — without running any tests. It is cheap and catches the most common
mistakes (a task on disk that is missing from `.manytask.yml`, a typo in a pipeline plugin name, an
unresolvable template), so keep it as the first stage: a broken config never reaches the registry or
the students.

`git` is installed explicitly — `python:3.12-slim` ships without it and the checker shells out to git.

## Stage 2 — `build-testenv`

```yaml
build-testenv:
  stage: build
  image:
    name: gcr.io/kaniko-project/executor:debug
    entrypoint: [""]
  before_script:
    - mkdir -p /kaniko/.docker
    - printf '{"auths":{"%s":{"username":"%s","password":"%s"}}}' "$CI_REGISTRY" "$CI_DEPLOY_USER" "$CI_DEPLOY_PASSWORD" > /kaniko/.docker/config.json
  script:
    - >-
      /kaniko/executor
      --context "$CI_PROJECT_DIR"
      --dockerfile "$CI_PROJECT_DIR/testenv.docker"
      --build-arg "CHECKER_PIP_SPEC=$CHECKER_PIP_SPEC"
      --destination "$CI_REGISTRY_IMAGE/testenv:$CI_COMMIT_SHORT_SHA"
      --destination "$CI_REGISTRY_IMAGE/testenv:latest"
```

This job builds the image that grades student submissions. `testenv.docker` bakes the full private
reference — gold solutions, filled templates, public **and** private tests — at `/opt/course` via
`checker export-private`, which is how the student `grade` job later reaches the hidden tests.

Four things are worth understanding here.

**Why kaniko.** Building an image from inside CI normally needs Docker-in-Docker and a privileged
runner. [kaniko](https://github.com/GoogleContainerTools/kaniko) builds the image in userspace, so
the pipeline works on shared/unprivileged runners. The `:debug` tag is used because it contains a
shell, needed for `before_script`; `entrypoint: [""]` overrides the image entrypoint so GitLab can
run its own script.

**Why a deploy token instead of the job token.** Authentication uses `CI_DEPLOY_USER` /
`CI_DEPLOY_PASSWORD`, not `CI_JOB_TOKEN`. On self-managed GitLab the job token is frequently not
permitted to push to the registry and the build dies with `UNAUTHORIZED: HTTP Basic: Access denied`.
Create a project (or group) deploy token named **exactly** `gitlab-deploy-token` with
`read_registry` + `write_registry` scopes — GitLab then auto-exposes it to every job as
`CI_DEPLOY_USER` / `CI_DEPLOY_PASSWORD`, with no variable definition on your side.

**Why `printf` and not a base64 `auth` blob.** kaniko silently falls back to *anonymous* access if
it cannot parse the `auth` field, and the failure surfaces much later as a confusing 401 from the
registry's auth endpoint. Writing `username`/`password` verbatim avoids that class of bug; deploy
token secrets are alphanumeric, so the JSON stays valid.

**Why two tags.** `:$CI_COMMIT_SHORT_SHA` is immutable and is what the `check` job consumes, so the
test always runs against the image built by *this* commit. `:latest` is the moving tag students
pull. For a single-`main` repo pushing `:latest` unconditionally is fine; if you build feature
branches, restrict the `:latest` destination to the default branch so they do not clobber it:

```yaml
    - >-
      /kaniko/executor
      ...
      --destination "$CI_REGISTRY_IMAGE/testenv:$CI_COMMIT_SHORT_SHA"
      $([ "$CI_COMMIT_BRANCH" = "$CI_DEFAULT_BRANCH" ] && echo "--destination $CI_REGISTRY_IMAGE/testenv:latest")
```

`CI_REGISTRY` and `CI_REGISTRY_IMAGE` are GitLab predefined variables — they are populated
automatically once the project's Container Registry is enabled, so there is nothing to configure.

## Stage 3 — `check`

```yaml
check:
  image: "$CI_REGISTRY_IMAGE/testenv:$CI_COMMIT_SHORT_SHA"
  stage: test
  needs: ["build-testenv"]
  script:
    - checker check . /opt/course
```

This is the **dress rehearsal for student grading**. The job runs *inside the image just built* and
executes `checker check . /opt/course`: the reference solution comes from the checkout (`.`), the
baked private tests come from `/opt/course` — exactly the overlay the student `grade` job performs,
with the student's code in place of the reference.

Two design points:

- **No `before_script`.** Every tool is already baked into the image. If a toolchain is missing from
  `testenv.docker`, this job fails *before* students ever see it.
- **No tokens.** The job talks to nothing external, so it proves the image build and the baked
  reference end to end without depending on any secret.

`needs: ["build-testenv"]` makes it start as soon as the build finishes instead of waiting for the
whole stage.

Because it grades the *gold* solutions, a failure here means either a broken reference solution, a
broken private test, or a toolchain missing from the image — never a student's mistake.

## Stage 4 — `deploy-public`

```yaml
deploy-public:
  image: python:3.12-slim
  stage: deploy
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      when: on_success
    - when: never
  variables:
    PUBLIC_REPO_URL: "https://oauth2:${GITLAB_API_TOKEN}@gitlab.example.org/<course>/public.git"
  before_script:
    - apt-get update -qq && apt-get install -y --no-install-recommends git curl && rm -rf /var/lib/apt/lists/*
    - python -m pip install --upgrade pip
    - pip install "$CHECKER_PIP_SPEC" pytest
    - git config --global user.email "ci@manytask.org"
    - git config --global user.name "Manytask CI"
    - |
      if ! git clone "$PUBLIC_REPO_URL" ./export; then
        mkdir -p ./export
        cd ./export
        git init
        git remote add origin "$PUBLIC_REPO_URL"
        cd ..
      fi
      cd ./export
      git checkout -B main
      cd ..
  script:
    - checker export --commit
```

**The `rules` block is the safety net.** Only the default branch publishes; every other branch runs
validate/build/check and stops. Without it, a feature branch would overwrite the student repository.
The explicit `- when: never` fallback makes that intent unambiguous.

**Why the public repo is pre-cloned.** `checker export --commit` writes into `./export`, runs git
*inside that directory* and pushes through whatever remote it finds there. If `./export` is not a
git repository, git walks up and finds the private repo's CI checkout — which is in detached HEAD —
and the push either fails or targets the wrong remote. Cloning first (or `git init` + `git remote add`
when the public repo is still empty) pins the operation to the right repository, and `git checkout -B main`
guarantees a branch exists to commit onto.

**Authentication.** `GITLAB_API_TOKEN` is a group or project access token with role `Maintainer` and
scope `write_repository`, embedded in the clone URL as `oauth2:<token>`. Define it as a **masked,
protected** CI/CD variable so it does not leak into job logs.

Which files end up in the public repo is decided entirely by `structure.public_patterns` /
`structure.private_patterns` in `.checker.yml`, not by this job — see the
[.checker.yml reference](./checker_yml_reference.md). Never widen `public_patterns` to `"*"`: it
matches dotfiles too, which silently disables `private_patterns` and leaks the hidden tests and this
very CI file into the student repo.

### Pushing the schedule to the web app

The same job then uploads `.manytask.yml` to the Manytask web app:

```yaml
    - |
      if [ -n "$MANYTASK_TOKEN" ]; then
        curl -fsSL -X POST \
          "${MANYTASK_URL:-https://app.manytask.org}/api/${MANYTASK_COURSE:-<course>}/update_config" \
          -H "Authorization: Bearer $MANYTASK_TOKEN" \
          -H "Content-Type: application/x-yaml" \
          --data-binary @.manytask.yml
      else
        echo "Skipping course-config update — MANYTASK_TOKEN not set"
      fi
```

Manytask is *course as code*: the web app stores the deadlines, scores and settings from
`.manytask.yml`, and the only way to update them is this HTTP API — **there is no `checker`
subcommand for it**, the checker only moves files. The endpoint is
`POST /api/<course>/update_config` with the raw YAML as the body (see the
[REST API reference](./api.md)).

`MANYTASK_TOKEN` is the **per-course token** issued by your Manytask admin, stored as a CI/CD
variable. The `-f` flag in `curl` makes a 4xx/5xx response fail the job — without it a rejected
config would pass silently. The `if` guard keeps the pipeline usable before the course is registered;
drop it once your course exists and you want a missing token to be a hard error.

> A course in the `finished` status rejects config updates with `409 Conflict`. That is expected —
> see [Running the course](./running_course.md#course-statuses).

## Optional — `deploy-mr-review`

If your course uses manual code review through merge requests, one more job delivers the config to
the mr-reviewer bot (see [`mr_review`](./manytask_yml_reference.md#mr_review)):

```yaml
deploy-mr-review:
  image: python:3.12-slim
  stage: deploy
  rules:
    - if: $CI_COMMIT_BRANCH == $CI_DEFAULT_BRANCH
      when: on_success
    - when: never
  before_script:
    - apt-get update -qq && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*
  script:
    - |
      if [ -z "$BOT_URL" ] || [ -z "$MANYTASK_TOKEN" ]; then
        echo "Skipping mr-reviewer config push — BOT_URL or MANYTASK_TOKEN not set"
        exit 0
      fi
      if ! grep -qE '^mr_review:' .manytask.yml; then
        echo "Skipping mr-reviewer config push — no mr_review section in .manytask.yml"
        exit 0
      fi
      curl -fsSL -X POST \
        "${BOT_URL}/courses/${MANYTASK_COURSE:-<course>}" \
        -H "Authorization: Bearer $MANYTASK_TOKEN" \
        -H "Content-Type: application/x-yaml" \
        --data-binary @.manytask.yml
```

The bot reads the **same `.manytask.yml`** and picks up its top-level `mr_review:` subsection; a
course without that section is not scanned at all, which is why the job self-skips when `grep` finds
no `mr_review:` key. It also needs no extra secret: the bot authenticates the push by replaying
`MANYTASK_TOKEN` against manytask's per-course `/ping`, so it is the same course token used for
`update_config`. Set `BOT_URL` to the bot's base URL as a group or project CI/CD variable; when it is
unset the job is a no-op, so the pipeline stays runnable on courses without a review bot.

## Variables and tokens

Set these in **Group → Settings → CI/CD → Variables** (group scope lets several courses share them)
or on the private project. Mark every token **Masked** and **Protected**.

| Variable | Required | Purpose |
|---|---|---|
| `CHECKER_PIP_SPEC` | yes (in-file) | Pinned checker install spec, shared by the jobs and the image build. Defined in `.releaser-ci.yml`, not in the UI. |
| `CI_DEPLOY_USER` / `CI_DEPLOY_PASSWORD` | yes | Auto-provided by GitLab from a deploy token named exactly `gitlab-deploy-token`. Used by kaniko to push the image. Do **not** define them by hand. |
| `GITLAB_API_TOKEN` | yes | Lets `checker export --commit` push to the public repo. Group access token, role `Maintainer`, scope `write_repository`. |
| `MANYTASK_TOKEN` | yes | Per-course token for the web app: `update_config` here, score reporting in the grade job, and auth for the review bot. |
| `MANYTASK_URL` | no | Manytask instance base URL. Defaults to the value hard-coded in the job. |
| `MANYTASK_COURSE` | no | Course slug in the API path. Defaults to the value hard-coded in the job. |
| `BOT_URL` | no | mr-reviewer base URL. Unset ⇒ `deploy-mr-review` is skipped. |
| `TESTENV_IMAGE` | no (student side) | Absolute registry path used by the student `.gitlab-ci.yml`. Not read by `.releaser-ci.yml`. |
| `DOCKER_AUTH_CONFIG` | no (student side) | Group variable letting student repos pull the testenv image across projects. |

### Creating the deploy token

On the **private** project: **Settings → Repository → Deploy tokens** → name it exactly
`gitlab-deploy-token`, scopes `read_registry` + `write_registry`. The name matters: GitLab only
auto-exposes `CI_DEPLOY_USER` / `CI_DEPLOY_PASSWORD` for that reserved name. The same token's
`read_registry` scope can back the `DOCKER_AUTH_CONFIG` group variable used by students to pull the
image.

## What you must change

Starting from the template file, these are the only edits a new course needs:

1. `CHECKER_PIP_SPEC` — pin the checker commit you want (or leave the template's).
2. `PUBLIC_REPO_URL` in `deploy-public` — your public repo, matching `export.destination` in
   `.checker.yml`.
3. The `update_config` URL — your Manytask instance and course slug, or set `MANYTASK_URL` /
   `MANYTASK_COURSE` as variables and leave the file alone.
4. `BOT_URL` — only if you run manual MR review; otherwise delete `deploy-mr-review`.
5. `git config user.email` / `user.name` — cosmetic, they author the export commits.

Everything else (`CI_REGISTRY*`, `CI_DEPLOY_*`, `CI_COMMIT_*`) is provided by GitLab.

## Verifying the pipeline

Push to a **non-default** branch first. `validate`, `build-testenv` and `check` run; both deploy jobs
are skipped by their `rules`, so nothing reaches students. When all three are green, merge to `main`
and watch `deploy-public` — the public repo should gain a commit with the exported files, and the
course page should show your schedule.

Locally, before pushing at all:

```bash
pip install "git+https://github.com/manytask/manytask.git@<commit-sha>#subdirectory=checker" pytest
checker validate
checker export --dry-run     # log what would be exported, write nothing
```

`--dry-run` is the fastest way to confirm your `public_patterns` / `private_patterns` do not leak
private tests.

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `UNAUTHORIZED: HTTP Basic: Access denied` in `build-testenv` | kaniko authenticated with the job token, or the deploy token is missing/misnamed | Create the deploy token named exactly `gitlab-deploy-token` with `write_registry`; keep the `printf` auth block |
| kaniko pushes anonymously / 401 from `jwt/auth` | malformed `/kaniko/.docker/config.json` | Use the `printf` username/password form, not a base64 `auth` blob |
| `check` fails but tasks pass locally | a toolchain is missing from `testenv.docker`, or a private test depends on an unexported file | Add the toolchain to the image; re-check `structure` patterns |
| `deploy-public` pushes into the private repo, or fails with detached HEAD | `./export` was not a git repository, so git walked up to the CI checkout | Keep the pre-clone / `git init` block and `git checkout -B main` |
| Export succeeds but students see `test_private.*` | `public_patterns` contains `"*"`, which matches dotfiles and disables `private_patterns` | Allow-list only the dotfiles students need |
| `curl` step exits 0 but the schedule never changes | `-f` missing, so an API error was swallowed | Keep `-fsSL`; check the token and course slug |
| `409 Conflict` from `update_config` | the course is in `finished` status | Change the status in the admin panel or `.manytask.yml` |
| `validate` fails with an unknown task | the task exists on disk but not in `deadlines.schedule` | Register it in `.manytask.yml` |

## Related references

- [Course template](./course_template.md) — the file this guide is based on, in context
- [Checker configuration](./checker_config.md) — the three config files together
- [.checker.yml reference](./checker_yml_reference.md) — export and structure patterns
- [.manytask.yml reference](./manytask_yml_reference.md) — schedule and grades schema
- [REST API](./api.md) — `update_config` and the rest of the endpoints
- [Running the course](./running_course.md) — course statuses and deadline advice
