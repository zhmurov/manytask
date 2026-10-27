"""Flask adapter for the shared grade-reporting operation."""

from manytask.course import Course
from manytask.main import CustomFlask
from manytask.reporting import TableData, build_grade_report, present_grade_report


def get_database_table_data(
    app: CustomFlask,
    course: Course,
    include_admin_data: bool = False,
    is_program_manager: bool = False,
) -> TableData:
    report = build_grade_report(
        app.storage_api, course, include_admin_data=include_admin_data, is_program_manager=is_program_manager
    )
    return present_grade_report(
        report,
        repo_url=(
            lambda username: app.rms_api.get_url_for_repo(
                username=username, course_students_group=course.gitlab_course_students_group
            )
        )
        if include_admin_data
        else None,
    )
