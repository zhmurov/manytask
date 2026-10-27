from unittest.mock import Mock

import pytest

from manytask.course import CourseStatus
from manytask.grading import calculate_effective_grade


@pytest.mark.parametrize(
    "status, saved, calculated, expected",
    [
        (CourseStatus.FINISHED, 5, 2, 5),
        (CourseStatus.FINISHED, None, 5, 0),
        (CourseStatus.DORESHKA, None, 5, 3),
        (CourseStatus.DORESHKA, 4, 5, 4),
        (CourseStatus.DORESHKA, 2, 5, 3),
        (CourseStatus.ALL_TASKS_ISSUED, 5, 2, 5),
        (CourseStatus.ALL_TASKS_ISSUED, 2, 5, 5),
        (CourseStatus.IN_PROGRESS, 5, 2, 2),
        (CourseStatus.CREATED, None, 4, 4),
        (CourseStatus.HIDDEN, 5, None, 0),
    ],
)
def test_effective_grade_policy(status: CourseStatus, saved: int | None, calculated: int | None, expected: int) -> None:
    config = Mock()
    config.evaluate.return_value = calculated
    assert calculate_effective_grade(status, config, {"total_score": 10}, saved) == expected
    if status == CourseStatus.FINISHED:
        config.evaluate.assert_not_called()


def test_unmatched_grade_falls_back_to_zero() -> None:
    config = Mock()
    config.evaluate.side_effect = ValueError("No grade matched")
    assert calculate_effective_grade(CourseStatus.IN_PROGRESS, config, {}, None) == 0
