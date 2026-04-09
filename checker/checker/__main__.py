from __future__ import annotations

import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Annotated, List, Optional
from zoneinfo import ZoneInfo

import typer

from .configs import CheckerConfig, CheckerSubConfig, ManytaskConfig
from .course import Course, FileSystemTask
from .exceptions import CheckerValidationError, TestingError
from .exporter import Exporter
from .tester import Tester
from .utils import print_ascii_tag, print_info

CHECKER_CONFIG = ".checker.yml"
MANYTASK_CONFIG = ".manytask.yml"

cli = typer.Typer(
    context_settings={"show_default": True},
    invoke_without_command=True,
    no_args_is_help=True,
)


def _version_callback(value: bool) -> None:
    if value:
        from importlib.metadata import version

        try:
            ver = version("manytask-checker")
        except Exception:
            ver = "unknown"
        typer.echo(f"manytask-checker {ver}")
        raise typer.Exit()


@cli.callback()
def main(
    version: Annotated[
        Optional[bool],
        typer.Option("--version", callback=_version_callback, is_eager=True, help="Show version and exit"),
    ] = None,
) -> None:
    """Manytask checker - automated tests for students' assignments."""
    print_ascii_tag()


@cli.command()
def validate(
    root: Annotated[Path, typer.Argument(help="Root directory of the course")] = Path("."),
    verbose: Annotated[bool, typer.Option("-v/-s", "--verbose/--silent", help="Verbose output")] = True,
) -> None:
    """Validate the configuration files, plugins and tasks.

    1. Validate the configuration files content.
    2. Validate mentioned plugins.
    3. Check all tasks are valid and consistent with the manytask.
    """
    if not root.exists() or not root.is_dir():
        print_info(f"Root directory does not exist or is not a directory: {root}", color="red")
        raise typer.Exit(code=1)

    # get configs paths
    course_config_path = root / CHECKER_CONFIG
    manytask_config_path = root / MANYTASK_CONFIG

    print_info("Validating configuration files...")
    try:
        checker_config = CheckerConfig.from_yaml(course_config_path)
        manytask_config = ManytaskConfig.from_yaml(manytask_config_path)
    except CheckerValidationError as e:
        print_info("Configuration Failed", color="red")
        print_info(e)
        raise typer.Exit(code=1)
    print_info("Ok", color="green")

    print_info("Validating Course Structure (and tasks configs)...")
    try:
        course = Course(manytask_config, root)
        course.validate()
    except CheckerValidationError as e:
        print_info("Course Validation Failed", color="red")
        print_info(e)
        raise typer.Exit(code=1)
    print_info("Ok", color="green")

    print_info("Validating Exporter...")
    try:
        exporter = Exporter(
            course,
            checker_config.structure,
            checker_config.export,
            verbose=True,
            dry_run=True,
        )
        exporter.validate()
    except CheckerValidationError as e:
        print_info("Exporter Validation Failed", color="red")
        print_info(e)
        raise typer.Exit(code=1)
    print_info("Ok", color="green")

    print_info("Validating tester...")
    try:
        tester = Tester(course, checker_config, verbose=verbose)
        tester.validate()
    except CheckerValidationError as e:
        print_info("Tester Validation Failed", color="red")
        print_info(e)
        raise typer.Exit(code=1)
    print_info("Ok", color="green")


def _run_validate(root: Path, verbose: bool) -> None:
    """Internal helper to run validation logic (used by check command)."""
    if not root.exists() or not root.is_dir():
        print_info(f"Root directory does not exist or is not a directory: {root}", color="red")
        raise typer.Exit(code=1)

    course_config_path = root / CHECKER_CONFIG
    manytask_config_path = root / MANYTASK_CONFIG

    print_info("Validating configuration files...")
    try:
        checker_config = CheckerConfig.from_yaml(course_config_path)
        manytask_config = ManytaskConfig.from_yaml(manytask_config_path)
    except CheckerValidationError as e:
        print_info("Configuration Failed", color="red")
        print_info(e)
        raise typer.Exit(code=1)
    print_info("Ok", color="green")

    print_info("Validating Course Structure (and tasks configs)...")
    try:
        course = Course(manytask_config, root)
        course.validate()
    except CheckerValidationError as e:
        print_info("Course Validation Failed", color="red")
        print_info(e)
        raise typer.Exit(code=1)
    print_info("Ok", color="green")

    print_info("Validating Exporter...")
    try:
        exporter = Exporter(
            course,
            checker_config.structure,
            checker_config.export,
            verbose=True,
            dry_run=True,
        )
        exporter.validate()
    except CheckerValidationError as e:
        print_info("Exporter Validation Failed", color="red")
        print_info(e)
        raise typer.Exit(code=1)
    print_info("Ok", color="green")

    print_info("Validating tester...")
    try:
        tester = Tester(course, checker_config, verbose=verbose)
        tester.validate()
    except CheckerValidationError as e:
        print_info("Tester Validation Failed", color="red")
        print_info(e)
        raise typer.Exit(code=1)
    print_info("Ok", color="green")


@cli.command()
def check(  # noqa: PLR0913
    root: Annotated[Path, typer.Argument(help="Root directory of the course")] = Path("."),
    reference_root: Annotated[Path, typer.Argument(help="Reference root directory")] = Path("."),
    task: Annotated[
        Optional[List[str]],
        typer.Option("-t", "--task", help="Task name to check (multiple possible)"),
    ] = None,
    group: Annotated[
        Optional[List[str]],
        typer.Option("-g", "--group", help="Group name to check (multiple possible)"),
    ] = None,
    parallelize: Annotated[
        bool,
        typer.Option("-p/-P", "--parallelize/--no-parallelize", help="Execute parallel checking of tasks"),
    ] = True,
    num_processes: Annotated[
        int,
        typer.Option("-n", "--num-processes", help="Num of processes parallel checking"),
    ] = os.cpu_count() or 1,
    no_clean: Annotated[bool, typer.Option("--no-clean", help="Clean or not check tmp folders")] = False,
    verbose: Annotated[
        bool,
        typer.Option("-v/-s", "--verbose/--silent", help="Verbose tests output"),
    ] = True,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Do not execute anything, only log actions")] = False,
) -> None:
    """Check private repository: run tests, lint etc. First forces validation.

    1. Run `validate` command.
    2. Export tasks to temporary directory for testing.
    3. Run pipelines: global, tasks and (dry-run) report.
    4. Cleanup temporary directory.
    """
    # validate first
    _run_validate(root=root, verbose=verbose)  # TODO: check verbose level

    # get configs paths
    course_config_path = root / CHECKER_CONFIG
    manytask_config_path = root / MANYTASK_CONFIG

    # load configs
    checker_config = CheckerConfig.from_yaml(course_config_path)
    manytask_config = ManytaskConfig.from_yaml(manytask_config_path)

    # read filesystem, check existing tasks
    course = Course(manytask_config, root, reference_root)

    # create exporter and export files for testing
    exporter = Exporter(
        course,
        checker_config.structure,
        checker_config.export,
        verbose=True,
        cleanup=not no_clean,
        dry_run=dry_run,
    )
    exporter.export_for_testing(exporter.temporary_dir)

    # validate tasks and groups if passed
    filesystem_tasks: dict[str, FileSystemTask] = dict()
    if task:
        task_dict = dict.fromkeys(task)
        for filesystem_task in course.get_tasks(enabled=True):
            if filesystem_task.name in task_dict:
                filesystem_tasks[filesystem_task.name] = filesystem_task
                del task_dict[filesystem_task.name]
        if task_dict:
            print_info(f"Can't find the tasks: {list(task_dict.keys())}", color="red")
            raise typer.Exit(code=1)
    if group:
        group_dict = dict.fromkeys(group)
        for filesystem_group in course.get_groups(enabled=True):
            if filesystem_group.name in group_dict:
                for filesystem_task in filesystem_group.tasks:
                    filesystem_tasks[filesystem_task.name] = filesystem_task
                del group_dict[filesystem_group.name]
        if group_dict:
            print_info(f"Can't find the groups: {list(group_dict.keys())}", color="red")
            raise typer.Exit(code=1)
    if filesystem_tasks:
        print_info(f"Checking tasks: {', '.join(filesystem_tasks.keys())}")

    # create tester to... to test =)
    tester = Tester(course, checker_config, verbose=verbose, dry_run=dry_run)

    # run tests
    # TODO: progressbar on parallelize
    try:
        tester.run(
            exporter.temporary_dir,
            tasks=list(filesystem_tasks.values()) if filesystem_tasks else None,
            report=False,
        )
    except TestingError as e:
        print_info("TESTING FAILED", color="red")
        print_info(e)
        raise typer.Exit(code=1)
    except Exception as e:
        print_info("UNEXPECTED ERROR", color="red")
        print_info(e)
        raise e
    print_info("TESTING PASSED", color="green")


def _parse_timestamp(value: Optional[str]) -> datetime:
    if value is None:
        return datetime.now(tz=ZoneInfo("Europe/Moscow"))
    try:
        return datetime.fromisoformat(value)
    except ValueError as e:
        raise typer.BadParameter("Use ISO 8601, e.g. 2025-09-08T13:39:13 or 2025-09-08T13:39:13Z") from e


@cli.command()
def grade(  # noqa: PLR0913
    root: Annotated[Path, typer.Argument(help="Root directory of the course")] = Path("."),
    reference_root: Annotated[Path, typer.Argument(help="Reference root directory")] = Path("."),
    submit_score: Annotated[
        bool,
        typer.Option("--submit-score", help="Submit score to the Manytask server"),
    ] = False,
    timestamp: Annotated[
        Optional[str],
        typer.Option(
            "--timestamp",
            help="Timestamp to use for the submission (ISO 8601, e.g. 2025-09-08T13:39:13). Default: current time in Europe/Moscow",
        ),
    ] = None,
    username: Annotated[Optional[str], typer.Option("--username", help="Username to use for the submission")] = None,
    branch: Annotated[
        Optional[str], typer.Option("--branch", help="Rewrite branch name for the submission")
    ] = None,
    no_clean: Annotated[bool, typer.Option("--no-clean", help="Clean or not check tmp folders")] = False,
    verbose: Annotated[
        bool,
        typer.Option("-v/-s", "--verbose/--silent", help="Verbose tests output"),
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Do not execute anything, only log actions")] = False,
) -> None:
    """Process the configuration file and grade the tasks.

    1. Detect changes to test.
    2. Export tasks to temporary directory for testing.
    3. Run pipelines: global, tasks and report.
    4. Cleanup temporary directory.
    """
    parsed_timestamp = _parse_timestamp(timestamp)

    # get configs paths
    course_config_path = reference_root / CHECKER_CONFIG
    manytask_config_path = reference_root / MANYTASK_CONFIG

    # load configs
    checker_config = CheckerConfig.from_yaml(course_config_path)
    manytask_config = ManytaskConfig.from_yaml(manytask_config_path)

    # read filesystem, check existing tasks
    course = Course(manytask_config, root, reference_root, branch_name=branch)

    # create exporter and export files for testing
    exporter = Exporter(
        course,
        checker_config.structure,
        checker_config.export,
        verbose=False,
        cleanup=not no_clean,
        dry_run=dry_run,
    )
    exporter.export_for_testing(exporter.temporary_dir)

    # detect changes to test
    try:
        changed_tasks = course.detect_changes(checker_config.testing.changes_detection)
    except Exception as e:
        print_info("DETECT CHANGES FAILED", color="red")
        print_info(e)
        raise typer.Exit(code=1)

    if not changed_tasks:
        print_info("No tasks to test", color="orange")
        return

    # create tester to... to test =)
    tester = Tester(course, checker_config, verbose=verbose, dry_run=dry_run)

    # run tests
    # TODO: progressbar on parallelize
    try:
        tester.run(
            exporter.temporary_dir,
            changed_tasks,
            report=True,
            timestamp=parsed_timestamp,
        )
    except TestingError as e:
        print_info("TESTING FAILED", color="red")
        print_info(e)
        raise typer.Exit(code=1)
    except Exception as e:
        print_info("UNEXPECTED ERROR", color="red")
        print_info(e)
        raise typer.Exit(code=1)
    print_info("TESTING PASSED", color="green")


@cli.command()
def export(
    reference_root: Annotated[Path, typer.Argument(help="Reference root directory")] = Path("."),
    export_root: Annotated[Path, typer.Argument(help="Export root directory")] = Path("./export"),
    commit: Annotated[
        bool,
        typer.Option("--commit", help="Commit and push changes to the repository"),
    ] = False,
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Do not execute anything, only log actions")] = False,
) -> None:
    """Export tasks from reference to public repository."""
    # get configs paths
    course_config_path = reference_root / CHECKER_CONFIG
    manytask_config_path = reference_root / MANYTASK_CONFIG

    # load configs
    checker_config = CheckerConfig.from_yaml(course_config_path)
    manytask_config = ManytaskConfig.from_yaml(manytask_config_path)

    # read filesystem, check existing tasks
    course = Course(manytask_config, reference_root)

    # if export_root not empty - delete all except git folder
    if export_root.exists():
        for path in export_root.iterdir():
            if path.name == ".git":
                continue
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()

    # create exporter and export files for public
    exporter = Exporter(
        course,
        checker_config.structure,
        checker_config.export,
        verbose=True,
        dry_run=dry_run,
    )
    export_root.mkdir(exist_ok=True, parents=True)
    exporter.export_public(export_root, commit=commit, commit_message=checker_config.export.commit_message)


@cli.command()
def export_private(
    reference_root: Annotated[Path, typer.Argument(help="Reference root directory")] = Path("."),
    export_root: Annotated[Path, typer.Argument(help="Export root directory")] = Path("./export"),
    dry_run: Annotated[bool, typer.Option("--dry-run", help="Do not execute anything, only log actions")] = False,
) -> None:
    """Export files to testing directory."""
    # get configs paths
    course_config_path = reference_root / CHECKER_CONFIG
    manytask_config_path = reference_root / MANYTASK_CONFIG

    # load configs
    checker_config = CheckerConfig.from_yaml(course_config_path)
    manytask_config = ManytaskConfig.from_yaml(manytask_config_path)

    # read filesystem, check existing tasks
    course = Course(manytask_config, reference_root)

    # create exporter and export files for public
    exporter = Exporter(
        course,
        checker_config.structure,
        checker_config.export,
        verbose=True,
        dry_run=dry_run,
    )
    export_root.mkdir(exist_ok=True, parents=True)
    exporter.export_private(export_root)


@cli.command(hidden=True)
def schema(
    output_folder: Annotated[Path, typer.Argument(help="Output folder for the schema files")] = Path("."),
) -> None:
    """Generate json schema for the checker configs."""
    checker_schema = CheckerConfig.get_json_schema()
    manytask_schema = ManytaskConfig.get_json_schema()
    task_schema = CheckerSubConfig.get_json_schema()

    with open(output_folder / "schema-checker.json", "w") as f:
        json.dump(checker_schema, f, indent=2)
    with open(output_folder / "schema-manytask.json", "w") as f:
        json.dump(manytask_schema, f, indent=2)
    with open(output_folder / "schema-task.json", "w") as f:
        json.dump(task_schema, f, indent=2)


if __name__ == "__main__":
    cli()
