"""Typed grade reports assembled without Flask or repository URL generation."""

from dataclasses import dataclass
from typing import Callable, NotRequired, TypedDict

from manytask.abstract import StorageApi
from manytask.course import Course
from manytask.database import calculate_effective_grade
from manytask.utils.generic import calculate_percent


class TaskColumn(TypedDict):
    name: str
    score: int
    group: str


class StudentScores(TypedDict):
    username: str
    scores: dict[str, int]
    total_score: int
    percent: float
    large_count: int
    is_admin: NotRequired[bool]
    first_name: NotRequired[str]
    last_name: NotRequired[str]
    comment: NotRequired[str | None]
    repo_url: NotRequired[str]


class StudentRow(StudentScores):
    grade: int
    grade_is_override: bool


class TableData(TypedDict):
    tasks: list[TaskColumn]
    students: list[StudentRow]
    max_score: NotRequired[int]


@dataclass(frozen=True)
class GradeReport:
    tasks: list[TaskColumn]
    students: list[StudentRow]
    max_score: int


def build_grade_report(
    storage_api: StorageApi, course: Course, *, include_admin_data: bool = False, is_program_manager: bool = False
) -> GradeReport:
    """Apply visibility and grade rules before passing report rows to a presenter."""
    scores_and_names = storage_api.get_all_scores_with_names(course.course_name)
    grades_config = storage_api.get_grades(course.course_name)
    tasks: list[TaskColumn] = []
    large_tasks: list[tuple[str, int]] = []
    max_score = 0
    for group in storage_api.get_groups(course.course_name, enabled=True, started=True):
        for task in group.tasks:
            if task.enabled:
                tasks.append({"name": task.name, "score": 0, "group": group.name})
                if not task.is_bonus:
                    max_score += task.score
                if task.is_large:
                    large_tasks.append((task.name, task.min_score))

    rows: list[StudentRow] = []
    for username, student in scores_and_names.items():
        if student.is_admin and not include_admin_data:
            continue
        large_count = student.count_solved_large_tasks(large_tasks)
        percent = calculate_percent(student.total_score, max_score)
        scores: StudentScores = {
            "username": username,
            "scores": student.scores,
            "total_score": student.total_score,
            "percent": percent,
            "large_count": large_count,
        }
        if include_admin_data:
            scores["is_admin"] = student.is_admin
            scores["comment"] = student.comment
        if include_admin_data or is_program_manager:
            scores["first_name"] = student.first_name
            scores["last_name"] = student.last_name
        grade = student.final_grade_override
        if grade is None:
            grade = calculate_effective_grade(course.status, grades_config, dict(scores), student.final_grade)
        row: StudentRow = {**scores, "grade": grade, "grade_is_override": student.final_grade_override is not None}
        rows.append(row)
    return GradeReport(tasks=tasks, students=rows, max_score=max_score)


def present_grade_report(report: GradeReport, *, repo_url: Callable[[str], str] | None = None) -> TableData:
    """Construct the existing API shape; repository links are supplied by the adapter."""
    students: list[StudentRow] = [row.copy() for row in report.students]
    if repo_url is not None:
        for row in students:
            row["repo_url"] = repo_url(row["username"])
    result: TableData = {"tasks": report.tasks, "students": students}
    # Preserve the existing response for an empty or fully hidden class.
    if students:
        result["max_score"] = report.max_score
    return result
