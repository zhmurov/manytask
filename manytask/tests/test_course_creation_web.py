"""Course-creation form conflicts must not modify existing RMS resources."""

from http import HTTPStatus
from typing import Any
from unittest.mock import patch

import pytest
from flask_wtf import CSRFProtect

from tests import test_web
from tests.constants import TEST_COURSE_NAME
from tests.helpers import build_test_session, set_session

app = test_web.app
mock_course = test_web.mock_course
mock_storage_api = test_web.mock_storage_api


@pytest.mark.parametrize("duplicate_name", [True, False])
def test_course_creation_form_rejects_registered_resources_before_rms_setup(
    app, mock_course, mock_gitlab_oauth, duplicate_name: bool
) -> None:
    app.oauth = mock_gitlab_oauth
    CSRFProtect(app)
    app.config["WTF_CSRF_ENABLED"] = False
    app.create_course_labels = {}
    app.storage_api.stored_user.instance_admin = True
    with (
        app.test_client() as client,
        patch("manytask.web.validate_csrf"),
        patch("manytask.web.check_course_creation_namespace_permission", return_value=(None, None, None, None)),
        patch.object(app.storage_api, "get_course_id_by_name", create=True, return_value=1 if duplicate_name else None),
        patch.object(app.rms_api, "create_course_group") as create_group,
    ):
        set_session(client, build_test_session(include_manytask=True))
        response = client.post(
            "/instance_admin/courses/new",
            data={
                "namespace_id": "0",
                "unique_course_name": TEST_COURSE_NAME,
                "course_group": mock_course.gitlab_course_group,
                "course_public_repo": f"{mock_course.gitlab_course_group}/public",
                "course_students_group": f"{mock_course.gitlab_course_group}/students",
            },
        )
    assert response.status_code == HTTPStatus.OK
    assert b"already exists" in response.data if duplicate_name else b"already used" in response.data
    create_group.assert_not_called()


@pytest.mark.parametrize("existing_group", ["", "other-course"])
def test_sourcecraft_creation_preserves_prefix_with_flat_repo_slug(
    app: Any, mock_course: Any, mock_gitlab_oauth: Any, existing_group: str
) -> None:
    app.oauth = mock_gitlab_oauth
    CSRFProtect(app)
    app.config["WTF_CSRF_ENABLED"] = False
    app.app_config.rms = "sourcecraft"
    app.storage_api.stored_user.instance_admin = True
    mock_course.gitlab_course_group = existing_group
    with (
        app.test_client() as client,
        patch("manytask.web.validate_csrf"),
        patch("manytask.web.check_course_creation_namespace_permission", return_value=(None, None, None, None)),
        patch.object(app.storage_api, "get_course_id_by_name", create=True, return_value=None),
        patch.object(app.storage_api, "create_course", create=True, return_value=True) as store_course,
        patch.object(app.rms_api, "create_course_group", return_value=-1),
    ):
        set_session(client, build_test_session(include_manytask=True))
        response = client.post(
            "/instance_admin/courses/new",
            data={
                "namespace_id": "0",
                "unique_course_name": "new-sourcecraft-course",
                "course_group": "new-course",
                "course_public_repo": "new-course-public-26s",
                "course_students_group": "new-course-students-26s",
                "default_branch": "main",
                "registration_secret": "test-registration-secret",
                "token": "test-course-token",
            },
        )
    assert response.status_code == HTTPStatus.FOUND
    settings = store_course.call_args.args[0]
    assert settings.gitlab_course_group == "new-course"
    assert settings.gitlab_course_public_repo == "new-course-public-26s"
