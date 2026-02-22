from __future__ import annotations

import typing
from http import HTTPStatus
from unittest import mock
from unittest.mock import patch

import pytest
from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.http import HttpResponseRedirect
from django.test import TestCase
from django.test.client import RequestFactory
from django.urls import reverse
from django_fsm_log.models import StateLog

from django_fsm import ConcurrentTransition
from tests.testapp.admin import AdminBlogPostAdmin
from tests.testapp.admin import ProxyAdminBlogPost
from tests.testapp.admin import ProxyAdminBlogPostAdmin
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

    def test_protected_fields_are_readonly(self):
        assert self.model_admin.get_readonly_fields(request=self.request) == ("state",)

    def test_get_fsm_redirect_url(self):
        assert (
            self.model_admin.get_fsm_redirect_url(
                request=RequestFactory().get(path="/path"),
                obj=None,
            )
            == "/path"
        )

    def test_get_fsm_extra_context_filters_admin_hidden(
        self,
    ) -> None:
        blog_post = AdminBlogPost.objects.create(
            title="Article name",
            state=AdminBlogPostState.REVIEWED,
        )

        transitions = list(
            self.model_admin._get_fsm_extra_context(request=self.request, obj=blog_post)
        )

        assert len(transitions) == 2  # noqa: PLR2004

        transitions_by_field = {
            item.fsm_field: {transition.name for transition in item.available_transitions}
            for item in transitions
        }

        assert transitions_by_field["state"] == {
            "publish",
            "hide",
            "invalid",
            "complex_transition",
            "complex_transition_model_form",
        }
        assert transitions_by_field["step"] == {"step_two"}

    @mock.patch("django.contrib.admin.ModelAdmin.change_view")
    @mock.patch("django_fsm.admin.FSMTransitionMixin._get_fsm_extra_context")
    def test_change_view_context(
        self,
        mock_get_fsm_extra_context: mock.Mock,
        mock_super_change_view: mock.Mock,
    ) -> None:
        mock_get_fsm_extra_context.return_value = ["object transitions"]

        self.model_admin.change_view(
            request=self.request,
            form_url="/test",
            object_id=str(self.blog_post.pk),
            extra_context={
                "existing_context": "existing context",
            },
        )

        mock_get_fsm_extra_context.assert_called_once_with(
            request=self.request,
            obj=self.blog_post,
        )

        mock_super_change_view.assert_called_once_with(
            request=self.request,
            object_id=str(self.blog_post.pk),
            form_url="/test",
            extra_context={
                "existing_context": "existing context",
                "fsm_object_transitions": ["object transitions"],
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

    def prepare_request(self, data: typing.Any) -> WSGIRequest:
        request = RequestFactory().post(path="/", data=data)
        request.user = self.user

        return request

    def test_invalid_transition(self, mock_message_user: mock.Mock) -> None:
        assert StateLog.objects.count() == 0

        blog_post = AdminBlogPost.objects.create(title="Article name")

        self.model_admin.response_change(
            request=self.prepare_request(
                data={"_fsm_transition_to": "invalid"},
            ),
            obj=blog_post,
        )

        mock_message_user.assert_called_once_with(
            request=mock.ANY,
            message="FSM transition 'invalid' failed: You shall not pass!.",
            level=messages.ERROR,
        )
        assert StateLog.objects.count() == 0

    def test_unknown_transition(self, mock_message_user: mock.Mock) -> None:
        assert StateLog.objects.count() == 0

        blog_post = AdminBlogPost.objects.create(title="Article name")
        assert blog_post.state == AdminBlogPostState.CREATED

        with pytest.raises(AttributeError):
            self.model_admin.response_change(
                request=self.prepare_request(
                    data={"_fsm_transition_to": "unknown_transition"},
                ),
                obj=blog_post,
            )

    def test_transition_applied(self, mock_message_user: mock.Mock) -> None:
        assert StateLog.objects.count() == 0

        blog_post = AdminBlogPost.objects.create(title="Article name")
        assert blog_post.state == AdminBlogPostState.CREATED

        self.model_admin.response_change(
            request=self.prepare_request(
                data={"_fsm_transition_to": "moderate"},
            ),
            obj=blog_post,
        )

        mock_message_user.assert_called_once_with(
            request=mock.ANY,
            message="FSM transition 'moderate' succeeded.",
            level=messages.SUCCESS,
        )

        blog_post.refresh_from_db()
        assert blog_post.state == AdminBlogPostState.REVIEWED
        assert StateLog.objects.count() == 1
        assert StateLog.objects.get().by == self.user

    def test_transition_not_allowed_exception(self, mock_message_user: mock.Mock) -> None:
        assert StateLog.objects.count() == 0

        blog_post = AdminBlogPost.objects.create(title="Article name")
        assert blog_post.state == AdminBlogPostState.CREATED

        self.model_admin.response_change(
            request=self.prepare_request(
                data={"_fsm_transition_to": "publish"},
            ),
            obj=blog_post,
        )

        mock_message_user.assert_called_once_with(
            request=mock.ANY,
            message="FSM transition 'publish' is not allowed.",
            level=messages.ERROR,
        )

        blog_post.refresh_from_db()
        assert blog_post.state == AdminBlogPostState.CREATED
        assert StateLog.objects.count() == 0

    def test_concurrent_transition_exception(self, mock_message_user: mock.Mock) -> None:
        assert StateLog.objects.count() == 0

        blog_post = AdminBlogPost.objects.create(title="Article name")
        assert blog_post.state == AdminBlogPostState.CREATED

        with mock.patch(
            "tests.testapp.models.AdminBlogPost.moderate",
            side_effect=ConcurrentTransition("error message"),
        ):
            self.model_admin.response_change(
                request=self.prepare_request(
                    data={"_fsm_transition_to": "moderate"},
                ),
                obj=blog_post,
            )

        mock_message_user.assert_called_once_with(
            request=mock.ANY,
            message="FSM transition 'moderate' failed: error message.",
            level=messages.ERROR,
        )

        blog_post.refresh_from_db()
        assert blog_post.state == AdminBlogPostState.CREATED
        assert StateLog.objects.count() == 0


@mock.patch("tests.testapp.admin.AdminBlogPostAdmin.message_user")
class TransitionFormTest(TestCase):
    user: User | AnonymousUser
    blog_post: AdminBlogPost

    def setUp(self):
        self.model_admin = AdminBlogPostAdmin(AdminBlogPost, AdminSite())

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="jacob",
            password="password",  # noqa: S106
            is_staff=True,
        )

        cls.blog_post = AdminBlogPost.objects.create(
            title="Article name", state=AdminBlogPostState.PUBLISHED
        )

    def prepare_request(self, data: typing.Any) -> WSGIRequest:
        request = RequestFactory().post(path="/", data=data)
        request.user = self.user

        return request

    def test_unknown_transition_raise_error(self, mock_message_user: mock.Mock) -> None:
        request = self.prepare_request(
            data={"_fsm_transition_to": "unknown_transition"},
        )

        with pytest.raises(AttributeError):
            self.model_admin.response_change(
                request=request,
                obj=self.blog_post,
            )

    def test_transition_without_form_execute_transition(self, mock_message_user: mock.Mock) -> None:
        assert StateLog.objects.count() == 0

        res = self.model_admin.response_change(
            request=self.prepare_request(
                data={"_fsm_transition_to": "hide"},
            ),
            obj=self.blog_post,
        )

        assert isinstance(res, HttpResponseRedirect)
        assert res.status_code == HTTPStatus.FOUND
        mock_message_user.assert_called_once_with(
            request=mock.ANY,
            message="FSM transition 'hide' succeeded.",
            level=messages.SUCCESS,
        )

        self.blog_post.refresh_from_db()
        assert self.blog_post.state == AdminBlogPostState.HIDDEN

        assert StateLog.objects.count() == 1

    def test_transition_with_form_redirects_properly(self, mock_message_user: mock.Mock) -> None:
        assert StateLog.objects.count() == 0

        res = self.model_admin.response_change(
            request=self.prepare_request(
                data={"_fsm_transition_to": "complex_transition"},
            ),
            obj=self.blog_post,
        )

        assert isinstance(res, HttpResponseRedirect)
        assert res.status_code == HTTPStatus.FOUND
        assert res.url == reverse(
            f"admin:{self.model_admin.opts.app_label}_{self.model_admin.opts.model_name}_transition",
            kwargs={
                "object_id": self.blog_post.pk,
                "transition_name": "complex_transition",
            },
        )
        assert StateLog.objects.count() == 0

        self.blog_post.refresh_from_db()
        assert self.blog_post.state == AdminBlogPostState.PUBLISHED
        assert self.blog_post.title == "Article name"
        mock_message_user.assert_not_called()

    def test_transition_form_submission_executes(self, mock_message_user: mock.Mock) -> None:
        assert StateLog.objects.count() == 0

        res = self.model_admin.fsm_transition_view(
            request=self.prepare_request(
                data={
                    "new_title": "New Title",
                    "comment": "Because",
                    "description": "Because",
                },
            ),
            object_id=str(self.blog_post.pk),
            transition_name="complex_transition",
        )

        assert isinstance(res, HttpResponseRedirect)
        assert res.status_code == HTTPStatus.FOUND
        mock_message_user.assert_called_once_with(
            request=mock.ANY,
            message="FSM transition 'complex_transition' succeeded.",
            level=messages.SUCCESS,
        )

        self.blog_post.refresh_from_db()
        assert self.blog_post.state == AdminBlogPostState.CREATED
        assert self.blog_post.title == "New Title"

        assert StateLog.objects.count() == 1


class TransitionFormAlternativeTest(TransitionFormTest):
    def setUp(self):
        self.model_admin = ProxyAdminBlogPostAdmin(ProxyAdminBlogPost, AdminSite())
