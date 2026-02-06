from __future__ import annotations

import typing
from unittest.mock import patch

from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.client import RequestFactory
from django_fsm_log.models import StateLog

from django_fsm import ConcurrentTransition
from django_fsm import FSMField
from tests.testapp.admin import AdminBlogPostAdmin
from tests.testapp.models import AdminBlogPost
from tests.testapp.models import AdminBlogPostState

if typing.TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser
    from django.contrib.auth.models import User
    from django.core.handlers.wsgi import WSGIRequest


class ModelAdminTest(TestCase):
    blog_post: AdminBlogPost
    request: WSGIRequest

    @classmethod
    def setUpTestData(cls):
        blog_post = AdminBlogPost.objects.create(title="Article name")
        blog_post.moderate()
        blog_post.save()
        cls.blog_post = blog_post

        cls.request = RequestFactory().get(path="/path")
        cls.request.user = get_user_model().objects.create_user(
            username="jacob",
            password="password",  # noqa: S106
            is_staff=True,
        )

    def setUp(self):
        self.model_admin = AdminBlogPostAdmin(AdminBlogPost, AdminSite())

    def test_get_fsm_field_instance(self):
        assert self.model_admin.get_fsm_field_instance(fsm_field_name="dummy_name") is None
        fsm_field = self.model_admin.get_fsm_field_instance(fsm_field_name="state")
        assert fsm_field is not None
        assert isinstance(fsm_field, FSMField)

    def test_readonly_fields(self):
        assert self.model_admin.get_readonly_fields(request=self.request) == ("state",)

    def test_get_fsm_block_label(self):
        assert (
            self.model_admin.get_fsm_block_label(fsm_field_name="MyField") == "Transition (MyField)"
        )

    def test_get_fsm_object_transitions(self):
        fsm_object_transitions = self.model_admin.get_fsm_object_transitions(
            request=self.request, obj=self.blog_post
        )

        assert len(fsm_object_transitions) == 2  # noqa: PLR2004
        state_transition, step_transition = fsm_object_transitions

        assert state_transition.fsm_field == "state"
        assert state_transition.block_label == "Transition (state)"
        assert sorted([t.name for t in state_transition.available_transitions]) == [
            "hide",
            "publish",
        ]

        assert step_transition.fsm_field == "step"
        assert step_transition.block_label == "Transition (step)"
        assert sorted([t.name for t in step_transition.available_transitions]) == ["step_two"]

    def test_get_fsm_redirect_url(self):
        assert self.model_admin.get_fsm_redirect_url(request=self.request, obj=None) == "/path"

    @patch("django.contrib.admin.ModelAdmin.change_view")
    @patch("django_fsm.admin.FSMTransitionMixin.get_fsm_object_transitions")
    def test_change_view_context(
        self,
        mock_get_fsm_object_transitions,
        mock_super_change_view,
    ):
        mock_get_fsm_object_transitions.return_value = "object transitions"

        self.model_admin.change_view(
            request=self.request,
            form_url="/test",
            object_id=str(self.blog_post.pk),
            extra_context={
                "existing_context": "existing context",
            },
        )

        mock_get_fsm_object_transitions.assert_called_once_with(
            request=self.request,
            obj=self.blog_post,
        )

        mock_super_change_view.assert_called_once_with(
            request=self.request,
            object_id=str(self.blog_post.pk),
            form_url="/test",
            extra_context={
                "existing_context": "existing context",
                "fsm_object_transitions": "object transitions",
            },
        )


@patch("django.contrib.admin.options.ModelAdmin.message_user")
class ResponseChangeTest(TestCase):
    user: User | AnonymousUser

    def setUp(self):
        self.model_admin = AdminBlogPostAdmin(AdminBlogPost, AdminSite())

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="jacob",
            password="password",  # noqa: S106
            is_staff=True,
        )

    def test_unknown_transition(self, mock_message_user):
        assert StateLog.objects.count() == 0
        request = RequestFactory().post(
            path="/",
            data={"_fsm_transition_to": "unknown_transition"},
        )

        blog_post = AdminBlogPost.objects.create(title="Article name")
        assert blog_post.state == AdminBlogPostState.CREATED

        self.model_admin.response_change(
            request=request,
            obj=blog_post,
        )

        mock_message_user.assert_called_once_with(
            request=request,
            message="FSM transition 'unknown_transition' is not a valid.",
            level=messages.ERROR,
        )

        updated_blog_post = AdminBlogPost.objects.get(pk=blog_post.pk)
        assert updated_blog_post.state == AdminBlogPostState.CREATED
        assert StateLog.objects.count() == 0

    def test_transition_applied(self, mock_message_user):
        assert StateLog.objects.count() == 0
        request = RequestFactory().post(
            path="/",
            data={"_fsm_transition_to": "moderate"},
        )
        request.user = self.user

        blog_post = AdminBlogPost.objects.create(title="Article name")
        assert blog_post.state == AdminBlogPostState.CREATED

        self.model_admin.response_change(
            request=request,
            obj=blog_post,
        )

        mock_message_user.assert_called_once_with(
            request=request,
            message="FSM transition 'moderate' succeeded.",
            level=messages.INFO,
        )

        updated_blog_post = AdminBlogPost.objects.get(pk=blog_post.pk)
        assert updated_blog_post.state == AdminBlogPostState.REVIEWED
        assert StateLog.objects.count() == 1
        assert StateLog.objects.get().by == self.user

    def test_transition_not_allowed_exception(self, mock_message_user):
        assert StateLog.objects.count() == 0
        request = RequestFactory().post(
            path="/",
            data={"_fsm_transition_to": "publish"},
        )
        request.user = self.user

        blog_post = AdminBlogPost.objects.create(title="Article name")
        assert blog_post.state == AdminBlogPostState.CREATED

        self.model_admin.response_change(
            request=request,
            obj=blog_post,
        )

        mock_message_user.assert_called_once_with(
            request=request,
            message="FSM transition 'publish' is not allowed.",
            level=messages.ERROR,
        )

        updated_blog_post = AdminBlogPost.objects.get(pk=blog_post.pk)
        assert updated_blog_post.state == AdminBlogPostState.CREATED
        assert StateLog.objects.count() == 0

    def test_concurrent_transition_exception(self, mock_message_user):
        assert StateLog.objects.count() == 0
        request = RequestFactory().post(
            path="/",
            data={"_fsm_transition_to": "moderate"},
        )
        request.user = self.user

        blog_post = AdminBlogPost.objects.create(title="Article name")
        assert blog_post.state == AdminBlogPostState.CREATED

        with patch(
            "tests.testapp.models.AdminBlogPost.moderate",
            side_effect=ConcurrentTransition("error message"),
        ):
            self.model_admin.response_change(
                request=request,
                obj=blog_post,
            )

        mock_message_user.assert_called_once_with(
            request=request,
            message="FSM transition 'moderate' failed: error message.",
            level=messages.ERROR,
        )

        updated_blog_post = AdminBlogPost.objects.get(pk=blog_post.pk)
        assert updated_blog_post.state == AdminBlogPostState.CREATED
        assert StateLog.objects.count() == 0
