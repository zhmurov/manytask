"""Pure course grading policy shared by persistence and reporting."""

from typing import Any

from manytask.config import ManytaskFinalGradeConfig
from manytask.course import CourseStatus


def calculate_effective_grade(
    course_status: CourseStatus,
    grades_config: ManytaskFinalGradeConfig,
    student_scores_data: dict[str, Any],
    saved_grade: int | None,
) -> int:
    """Calculate effective grade for a student. Pure function, no DB access.

    Logic:
    1. If course is FINISHED, return saved grade (frozen).
    2. Calculate grade from scores using grades_config.evaluate().
    3. In DORESHKA: cap at 3, then take max(saved, capped) to prevent downgrade.
    4. In ALL_TASKS_ISSUED: take max(saved, calculated) to prevent downgrade.
    5. Otherwise (IN_PROGRESS): return calculated grade as-is (downgrade allowed).
    """
    if course_status == CourseStatus.FINISHED:
        return saved_grade if saved_grade is not None else 0

    try:
        calculated_grade = grades_config.evaluate(student_scores_data)
        if calculated_grade is None:
            calculated_grade = 0
    except ValueError:
        calculated_grade = 0

    freeze_statuses = {CourseStatus.DORESHKA, CourseStatus.ALL_TASKS_ISSUED}

    if course_status in freeze_statuses:
        capped_grade = calculated_grade
        if course_status == CourseStatus.DORESHKA:
            capped_grade = min(calculated_grade, 3)

        if saved_grade is not None:
            return max(saved_grade, capped_grade)
        return capped_grade

    return calculated_grade
