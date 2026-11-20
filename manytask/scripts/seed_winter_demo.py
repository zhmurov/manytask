"""Create or refresh the local winter demo using an existing admin's repository.

From manytask/: docker exec -i test-manytask python - < scripts/seed_winter_demo.py
Every run moves deadlines relative to now. No RMS repositories are changed.
"""

import argparse
import os
import secrets
from datetime import datetime, timedelta
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from manytask.config import ManytaskConfig
from manytask.course import CourseConfig, CourseStatus
from manytask.database import DataBaseApi, DatabaseConfig
from manytask.models import Course, User, UserOnCourse

COURSE_NAME = "winter-demo"
DEMO_URL = "http://localhost:8081/winter-demo/#$TASK_NAME"
EXPECTED_GROUPS = 2
EXPECTED_TASKS = 6


def demo_config(now: datetime) -> ManytaskConfig:
    schedule = []
    for group_name, hours, tasks in [
        ("Melting snow · urgent", 6, ["snowballs", "icicles", "warm-up"]),
        ("Fresh snow · later", 72, ["snowflakes", "snowdrifts", "winter-tree"]),
    ]:
        schedule.append(
            {
                "group": group_name,
                "start": now - timedelta(days=1),
                "steps": {0.5: now + timedelta(hours=hours / 2)},
                "end": now + timedelta(hours=hours),
                "tasks": [{"task": task, "score": 100} for task in tasks],
            }
        )
    return ManytaskConfig.model_validate(
        {
            "version": 1,
            "status": "in_progress",
            "ui": {"task_url_template": DEMO_URL},
            "deadlines": {"timezone": "Europe/Moscow", "deadlines": "hard", "schedule": schedule},
        }
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-course", help="Reuse this local course's existing repository configuration")
    args = parser.parse_args()
    database_url = os.environ["DATABASE_URL"]
    if urlparse(database_url).hostname not in {"localhost", "127.0.0.1", "postgres", "pgbouncer"}:
        raise SystemExit("This helper is only for the local development database.")
    admin = os.environ["INITIAL_INSTANCE_ADMIN"]
    api = DataBaseApi(DatabaseConfig(database_url=database_url, instance_admin_username=admin))
    with Session(api.engine) as session:
        source_query = (
            select(Course)
            .join(UserOnCourse, UserOnCourse.course_id == Course.id)
            .join(User, User.id == UserOnCourse.user_id)
            .where(User.username == admin, Course.name != COURSE_NAME, Course.gitlab_course_students_group != "")
            .order_by(Course.id.desc())
        )
        if args.source_course:
            source_query = source_query.where(Course.name == args.source_course)
        source = session.scalars(source_query).first()
        if source is None:
            raise SystemExit("Enroll the local instance admin in a course with a working repository first.")
        existing = session.scalar(select(Course).where(Course.name == COURSE_NAME))
        if existing is not None and existing.task_url_template != DEMO_URL:
            raise SystemExit("An unrelated winter-demo course already exists; no changes made.")
        settings = CourseConfig(
            course_name=COURSE_NAME,
            namespace_id=None,
            gitlab_course_group=source.gitlab_course_group,
            gitlab_course_public_repo=source.gitlab_course_public_repo,
            gitlab_course_students_group=source.gitlab_course_students_group,
            gitlab_default_branch=source.gitlab_default_branch,
            registration_secret=secrets.token_urlsafe(32),
            token=secrets.token_urlsafe(32),
            show_allscores=True,
            status=CourseStatus.IN_PROGRESS,
            task_url_template=DEMO_URL,
        )
    now = datetime.now(ZoneInfo("Europe/Moscow"))
    api.create_course(settings)
    api.update_course(COURSE_NAME, demo_config(now))
    api.sync_user_on_course(COURSE_NAME, admin, course_admin=True)
    # This visual demo reuses existing repositories and needs no RMS reconciliation.
    api.clear_rms_settings_pending(COURSE_NAME)
    groups = [group for group in api.get_groups(COURSE_NAME, enabled=True, started=True) if group.tasks]
    assert len(groups) == EXPECTED_GROUPS
    assert sum(len(group.tasks) for group in groups) == EXPECTED_TASKS
    urgent = next(group for group in groups if group.name.startswith("Melting"))
    assert 0 < (urgent.get_deadline(urgent.end) - now).total_seconds() < timedelta(days=1).total_seconds()
    print(f"Ready: http://localhost:8081/{COURSE_NAME}/")
    print(
        f"Urgent deadlines: {(now + timedelta(hours=3)):%d %b %H:%M} and {(now + timedelta(hours=6)):%d %b %H:%M} MSK"
    )
    print("The local instance admin is enrolled; rerun this helper to refresh the deadlines.")


if __name__ == "__main__":
    main()
