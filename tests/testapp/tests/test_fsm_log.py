"""
django-fsm-log compatibility.

Transition tracking relying on the third-party django-fsm-log package
(`fsm_log_by` / `fsm_log_description` decorators and its `StateLog` model),
kept aside the built-in `django_fsm.log` solution covered by test_transition_tracking.py.
"""

from __future__ import annotations

import typing
from unittest import mock

from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse
from django_fsm_log.models import StateLog as FSMLogStateLog

from tests.testapp.models import FSMLogAndTrackedBlogPost
from tests.testapp.models import FSMLogBlogPost
from tests.testapp.models import GenericTrackedPost
from tests.testapp.models import StateLog

from ..admin import FSMLogBlogPostAdmin

if typing.TYPE_CHECKING:
    from django.contrib.auth.models import User
    from django.core.handlers.wsgi import WSGIRequest


class FSMLogTestCase(TestCase):
    user: User

    @classmethod
    def setUpTestData(cls) -> None:
        cls.user = get_user_model().objects.create_user(
            username="jacob",
            password="password",  # noqa: S106
            is_staff=True,
            is_superuser=True,
        )

    def assert_fsm_log_created(
        self, post: FSMLogBlogPost | FSMLogAndTrackedBlogPost, description: str | None
    ) -> None:
        log = FSMLogStateLog.objects.for_(post).get()
        assert log.transition == "publish"
        assert log.source_state == "new"
        assert log.state == "published"
        assert log.by == self.user
        assert log.description == description


class FSMLogDecoratorsTestCase(FSMLogTestCase):
    def test_transition_is_logged(self) -> None:
        post = FSMLogBlogPost.objects.create()
        post.publish(by=self.user, description="published via django-fsm-log")

        self.assert_fsm_log_created(post, description="published via django-fsm-log")
        assert not StateLog.objects.exists()

    def test_transition_without_by_nor_description(self) -> None:
        post = FSMLogBlogPost.objects.create()
        post.publish()

        log = FSMLogStateLog.objects.for_(post).get()
        assert log.by is None
        assert log.description is None

    def test_coexists_with_builtin_tracking(self) -> None:
        post = FSMLogAndTrackedBlogPost.objects.create()
        post.publish(by=self.user, description="published twice")

        self.assert_fsm_log_created(post, description="published twice")

        log = StateLog.objects.for_(post).get()
        assert log.transition == "publish"
        assert log.by == self.user
        assert log.description == "published twice"

    def test_ignored_models_are_not_logged(self) -> None:
        # Models tracked by django_fsm.log are listed in DJANGO_FSM_LOG_IGNORED_MODELS
        post = GenericTrackedPost.objects.create()
        post.publish(by=self.user)

        assert not FSMLogStateLog.objects.exists()
        assert StateLog.objects.for_(post).exists()


class FSMLogAdminTestCase(FSMLogTestCase):
    def setUp(self) -> None:
        self.model_admin = FSMLogBlogPostAdmin(FSMLogBlogPost, AdminSite())

    def make_request(self, *, data: dict[str, str] | None = None) -> WSGIRequest:
        request = RequestFactory().post(path="/", data=data or {})
        request.user = self.user
        return request

    def test_execute_fsm_transition_passes_by(self) -> None:
        post = FSMLogBlogPost.objects.create()

        self.model_admin._execute_fsm_transition(
            transition_func=post.publish, request=self.make_request()
        )

        self.assert_fsm_log_created(post, description=None)

    @mock.patch.object(FSMLogBlogPostAdmin, "message_user")
    def test_response_change_transition(self, mock_message_user: mock.Mock) -> None:
        post = FSMLogBlogPost.objects.create()

        self.model_admin.response_change(
            request=self.make_request(data={"_fsm_transition_to": "publish"}),
            obj=post,
        )

        post.refresh_from_db()
        assert post.state == "published"
        self.assert_fsm_log_created(post, description=None)
        mock_message_user.assert_called_once()

    def test_change_view_renders_state_log_inline(self) -> None:
        post = FSMLogBlogPost.objects.create()
        post.publish(by=self.user, description="shown in the inline")
        post.save()
        self.client.force_login(user=self.user)

        response = self.client.get(
            reverse("admin:testapp_fsmlogblogpost_change", kwargs={"object_id": post.pk}),
        )

        assert response.status_code == 200  # noqa: PLR2004
        self.assertContains(response, "shown in the inline")
