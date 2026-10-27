from types import SimpleNamespace
from unittest.mock import Mock

from manytask.abstract import StudentCourseScores
from manytask.course import CourseStatus
from manytask.reporting import build_grade_report, present_grade_report


def test_report_privacy_without_flask_or_rms() -> None:
    storage = Mock()
    storage.get_groups.return_value = []
    storage.get_all_scores_with_names.return_value = {
        "student": StudentCourseScores("student", "First", "Last", final_grade_override=4, comment="private"),
        "admin": StudentCourseScores("admin", "Admin", "User", is_admin=True),
    }
    course = SimpleNamespace(course_name="course", status=CourseStatus.IN_PROGRESS)
    report = build_grade_report(storage, course, is_program_manager=True)
    data = present_grade_report(report)
    assert [row["username"] for row in data["students"]] == ["student"]
    assert data["students"][0]["first_name"] == "First"
    assert (
        data["students"][0]["grade"] == storage.get_all_scores_with_names.return_value["student"].final_grade_override
    )
    assert "comment" not in data["students"][0]
    assert "repo_url" not in data["students"][0]


def test_presentation_adds_links_without_mutating_report() -> None:
    storage = Mock()
    storage.get_groups.return_value = []
    storage.get_all_scores_with_names.return_value = {
        "admin": StudentCourseScores("admin", "Admin", "User", final_grade_override=5, is_admin=True),
    }
    report = build_grade_report(
        storage, SimpleNamespace(course_name="course", status=CourseStatus.IN_PROGRESS), include_admin_data=True
    )
    data = present_grade_report(report, repo_url=lambda username: f"https://example.test/{username}")
    assert data["students"][0]["repo_url"] == "https://example.test/admin"
    assert "repo_url" not in report.students[0]
    assert data["students"][0]["is_admin"]
