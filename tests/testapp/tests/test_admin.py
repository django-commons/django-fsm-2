from __future__ import annotations

import contextlib
import typing
from http import HTTPStatus
from unittest import mock
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseRedirect
from django.test import TestCase
from django.test.client import RequestFactory
from django.test.utils import modify_settings
from django.urls import reverse
from django_fsm_log.models import StateLog

from django_fsm import ConcurrentTransition
from django_fsm.admin import FSMTransitionMixin
from tests.testapp.admin import AdminBlogPostAdmin
from tests.testapp.admin_forms import AdminBlogPostRenameModelForm
from tests.testapp.admin_forms import FSMLogDescription
from tests.testapp.models import AdminBlogPost
from tests.testapp.models import AdminBlogPostState

if typing.TYPE_CHECKING:
    from django.contrib.auth.models import AnonymousUser
    from django.contrib.auth.models import User
    from django.core.handlers.wsgi import WSGIRequest

disable_fsm_log = modify_settings(
    DJANGO_FSM_LOG_IGNORED_MODELS={
        "append": "tests.testapp.models.AdminBlogPost",
    }
)


class BaseAdminTestCase(TestCase):
    model = AdminBlogPost
    admin_class = AdminBlogPostAdmin
    user: User | AnonymousUser
    blog_post: AdminBlogPost

    fsm_log_enabled = True

    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="jacob",
            password="password",  # noqa: S106
            is_staff=True,
        )

        cls.blog_post = cls.model.objects.create(
            title="Article name", state=AdminBlogPostState.PUBLISHED
        )

    def setUp(self) -> None:
        self.model_admin = self.admin_class(self.model, AdminSite())

    def make_request(self, *, data: typing.Any | None = None) -> WSGIRequest:
        factory = RequestFactory()
        request = factory.post(path="/", data=data or {})
        request.user = self.user
        return request

    def assert_state_log_empty(self) -> None:
        assert StateLog.objects.count() == 0

    def assert_state_log_for_user(
        self,
        *,
        description: str | None = None,
        source_state: AdminBlogPostState | None = None,
        state: AdminBlogPostState | None = None,
        transition: str | None = None,
    ) -> None:
        if self.fsm_log_enabled:
            statelog = StateLog.objects.get()
            assert statelog.by == self.user
            if description is not None:
                assert statelog.description == description
            if source_state is not None:
                assert statelog.source_state == source_state
            if state is not None:
                assert statelog.state == state
            if transition is not None:
                assert statelog.transition == transition
        else:
            self.assert_state_log_empty()


class EmptyFieldAdmin(FSMTransitionMixin, admin.ModelAdmin[AdminBlogPost]):
    fsm_fields = []


class InvalidFieldAdmin(FSMTransitionMixin, admin.ModelAdmin[AdminBlogPost]):
    fsm_fields = ["title"]


class InvalidFormPathAdmin(FSMTransitionMixin, admin.ModelAdmin[AdminBlogPost]):
    fsm_fields = ["state"]

    fsm_forms = {
        "complex_transition": "invalid.path",
    }


class ModelAdminMisconfigurationTestCase(TestCase):
    user: User | AnonymousUser
    blog_post: AdminBlogPost
    request: WSGIRequest

    def setUp(self) -> None:
        with contextlib.suppress(admin.sites.NotRegistered):  # type: ignore[attr-defined]
            admin.site.unregister(AdminBlogPost)

    def tearDown(self) -> None:
        """Reconnect original admin"""
        with contextlib.suppress(admin.sites.NotRegistered):  # type: ignore[attr-defined]
            admin.site.unregister(AdminBlogPost)
        admin.site.register(AdminBlogPost, AdminBlogPostAdmin)

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

        cls.request = RequestFactory().post(path="/")
        cls.request.user = cls.user

    def test_empty_fsm_field(self):
        with pytest.raises(ImproperlyConfigured):
            admin.site.register(AdminBlogPost, EmptyFieldAdmin)

    def test_invalid_fsm_field(self):
        admin.site.register(AdminBlogPost, InvalidFieldAdmin)

        with pytest.raises(ImproperlyConfigured, match="'title' is not an FSMField"):
            InvalidFieldAdmin(AdminBlogPost, AdminSite()).get_readonly_fields(
                request=self.request,
                obj=self.blog_post,
            )

    def test_invalid_form_path(self):
        admin.site.register(AdminBlogPost, InvalidFormPathAdmin)

        with pytest.raises(
            ImproperlyConfigured,
            match=r"Failed to import form invalid\.path",
        ):
            InvalidFormPathAdmin(AdminBlogPost, AdminSite())._get_transition_data(
                obj=self.blog_post,
                transition_name="complex_transition",
            )


class ModelAdminTestCase(TestCase):
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

    # Basics
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

    # Execution
    def test_execute_transition_falls_back_to_plain_call(self) -> None:
        called: dict[str, str] = {}

        def transition_method(*, comment: str) -> None:
            called["comment"] = comment

        with mock.patch.object(self.model_admin, "_is_fsm_log_enabled", return_value=True):
            self.model_admin._execute_transition(
                transition_method=transition_method,
                request=self.request,
                kwargs={"comment": "Because"},
            )

        assert called["comment"] == "Because"

    # Context
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

        # Only available transitions
        assert transitions_by_field["step"] == {"step_two"}
        # but not if custom.admin is False
        assert "secret_transition" in blog_post.get_available_user_state_transitions(  # type: ignore[attr-defined]
            user=self.request.user
        )
        assert "secret_transition" not in transitions_by_field["state"]

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
class ResponseChangeViewTestCase(BaseAdminTestCase):
    # Classic updates
    @mock.patch("django.contrib.admin.ModelAdmin.response_change")
    def test_classic_update_keep_working(
        self, mock_response_change: mock.Mock, mock_message_user: mock.Mock
    ) -> None:
        self.assert_state_log_empty()

        blog_post = AdminBlogPost.objects.create(title="Article name")
        assert blog_post.state == AdminBlogPostState.CREATED

        self.model_admin.response_change(
            request=self.make_request(
                data={"title": "New Name"},
            ),
            obj=blog_post,
        )

        mock_response_change.assert_called_once()

        self.assert_state_log_empty()

    # Errors
    def test_unknown_transition(self, mock_message_user: mock.Mock) -> None:
        self.assert_state_log_empty()

        blog_post = AdminBlogPost.objects.create(title="Article name")
        assert blog_post.state == AdminBlogPostState.CREATED

        with pytest.raises(AttributeError):
            self.model_admin.response_change(
                request=self.make_request(
                    data={"_fsm_transition_to": "unknown_transition"},
                ),
                obj=blog_post,
            )

        self.assert_state_log_empty()

    def test_transition_raised_exception(self, mock_message_user: mock.Mock) -> None:
        self.assert_state_log_empty()

        self.model_admin.response_change(
            request=self.make_request(
                data={"_fsm_transition_to": "invalid_without_forms"},
            ),
            obj=self.blog_post,
        )

        mock_message_user.assert_called_once_with(
            request=mock.ANY,
            message="FSM transition 'invalid_without_forms' failed: You shall not pass!.",
            level=messages.ERROR,
        )
        self.assert_state_log_empty()

    def test_execute_transition_falls_back_to_plain_call(
        self, mock_message_user: mock.Mock
    ) -> None:
        self.assert_state_log_empty()

        self.model_admin.response_change(
            request=self.make_request(
                data={"_fsm_transition_to": "non_fsm_log_invalid"},
            ),
            obj=self.blog_post,
        )

        mock_message_user.assert_called_once_with(
            request=mock.ANY,
            message="FSM transition 'non_fsm_log_invalid' failed: Domain-raised exception.",
            level=messages.ERROR,
        )
        self.assert_state_log_empty()

    # Transitions
    def test_transition_applied(self, mock_message_user: mock.Mock) -> None:
        self.assert_state_log_empty()

        blog_post = AdminBlogPost.objects.create(title="Article name")
        assert blog_post.state == AdminBlogPostState.CREATED

        self.model_admin.response_change(
            request=self.make_request(
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

        self.assert_state_log_for_user()

    def test_transition_not_allowed_exception(self, mock_message_user: mock.Mock) -> None:
        self.assert_state_log_empty()

        blog_post = AdminBlogPost.objects.create(title="Article name")
        assert blog_post.state == AdminBlogPostState.CREATED

        self.model_admin.response_change(
            request=self.make_request(
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
        self.assert_state_log_empty()

    def test_concurrent_transition_exception(self, mock_message_user: mock.Mock) -> None:
        self.assert_state_log_empty()

        blog_post = AdminBlogPost.objects.create(title="Article name")
        assert blog_post.state == AdminBlogPostState.CREATED

        with mock.patch(
            "tests.testapp.models.AdminBlogPost.moderate",
            side_effect=ConcurrentTransition("error message"),
        ):
            self.model_admin.response_change(
                request=self.make_request(
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
        self.assert_state_log_empty()

    def test_unknown_transition_raise_error(self, mock_message_user: mock.Mock) -> None:
        request = self.make_request(
            data={"_fsm_transition_to": "unknown_transition"},
        )

        with pytest.raises(AttributeError):
            self.model_admin.response_change(
                request=request,
                obj=self.blog_post,
            )

    def test_transition_without_form_execute_transition(self, mock_message_user: mock.Mock) -> None:
        self.assert_state_log_empty()

        res = self.model_admin.response_change(
            request=self.make_request(
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

        self.assert_state_log_for_user()

    def test_transition_with_form_redirects_properly(self, mock_message_user: mock.Mock) -> None:
        self.assert_state_log_empty()

        res = self.model_admin.response_change(
            request=self.make_request(
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
        self.assert_state_log_empty()

        self.blog_post.refresh_from_db()
        assert self.blog_post.state == AdminBlogPostState.PUBLISHED
        assert self.blog_post.title == "Article name"
        mock_message_user.assert_not_called()


@disable_fsm_log
class ResponseChangeViewWithoutFsmLogTestCase(ResponseChangeViewTestCase):
    fsm_log_enabled = False


@mock.patch("tests.testapp.admin.AdminBlogPostAdmin.message_user")
class TransitionViewTestCase(BaseAdminTestCase):
    # Errors
    def test_transition_raised_exception(self, mock_message_user: mock.Mock) -> None:
        self.assert_state_log_empty()

        self.model_admin.fsm_transition_view(
            request=self.make_request(
                data={
                    "description": "because",
                },
            ),
            object_id=str(self.blog_post.pk),
            transition_name="invalid",
        )

        mock_message_user.assert_called_once_with(
            request=mock.ANY,
            message="FSM transition 'invalid' failed: You shall not pass!.",
            level=messages.ERROR,
        )
        self.assert_state_log_empty()

    def test_invalid_object_id(self, mock_message_user: mock.Mock) -> None:
        self.assert_state_log_empty()

        invalid_object_id = "123456"
        assert not AdminBlogPost.objects.filter(pk=invalid_object_id).exists()

        res = self.model_admin.fsm_transition_view(
            request=self.make_request(
                data={
                    "state": AdminBlogPostState.CREATED,
                    "description": "because",
                },
            ),
            object_id=invalid_object_id,
            transition_name="force_state",
        )

        assert isinstance(res, HttpResponseRedirect)
        assert res.status_code == HTTPStatus.FOUND
        assert res["Location"] == reverse("admin:index")

        mock_message_user.assert_called_once_with(
            mock.ANY,
            f"{self.model._meta.verbose_name} with ID “{invalid_object_id}” doesn’t exist. Perhaps it was deleted?",  # noqa: RUF001, E501
            messages.WARNING,
        )
        self.assert_state_log_empty()

    def test_transition_without_form_(self, mock_message_user: mock.Mock) -> None:
        self.assert_state_log_empty()

        res = self.model_admin.fsm_transition_view(
            request=self.make_request(),
            transition_name="hide",
            object_id=str(self.blog_post.pk),
        )

        assert isinstance(res, HttpResponseBadRequest)
        assert res.status_code == HTTPStatus.BAD_REQUEST
        self.assert_state_log_empty()

    # Form submissions
    def test_transition_form_submission_executes(self, mock_message_user: mock.Mock) -> None:
        assert self.blog_post.state == AdminBlogPostState.PUBLISHED
        self.assert_state_log_empty()

        res = self.model_admin.fsm_transition_view(
            request=self.make_request(
                data={
                    "title": "New Title",
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

        self.assert_state_log_for_user(
            description="Because",
            source_state=AdminBlogPostState.PUBLISHED,
            state=AdminBlogPostState.CREATED,
            transition="complex_transition",
        )

    # Rendering
    def test_transition_form_rendered(self, mock_message_user: mock.Mock) -> None:
        request = RequestFactory().get(path="/")
        request.user = self.user
        mock_response = HttpResponse("ok")

        with mock.patch("django_fsm.admin.render", return_value=mock_response) as mock_render:
            res = self.model_admin.fsm_transition_view(
                request=request,
                object_id=str(self.blog_post.pk),
                transition_name="complex_transition",
            )

        assert res is mock_response
        mock_render.assert_called_once()
        args, kwargs = mock_render.call_args
        assert args[0] is request
        assert kwargs["template_name"] == self.model_admin.fsm_transition_form_template
        context = kwargs["context"]
        assert "transition_form" in context
        assert context["transition_form"].is_bound is False


class ModelFormTransitionViewTestCase(TransitionViewTestCase):
    """
    Runs TransitionViewTestCase but with **class-based forms** (instead of import path)
    """

    def setUp(self) -> None:
        self.fsm_forms_patcher = mock.patch.dict(
            AdminBlogPostAdmin.fsm_forms,
            {
                "complex_transition": AdminBlogPostRenameModelForm,
                "invalid": FSMLogDescription,
            },
            clear=False,
        )
        self.fsm_forms_patcher.start()
        super().setUp()

    def tearDown(self) -> None:
        self.fsm_forms_patcher.stop()
        super().tearDown()


@disable_fsm_log
class NoFsmLogTransitionViewTestCase(TransitionViewTestCase):
    """
    Runs TransitionViewTestCase but with **FSM log disabled**
    """

    fsm_log_enabled = False


@disable_fsm_log
class NoFsmLogModelFormTransitionViewTestCase(ModelFormTransitionViewTestCase):
    """
    Runs TransitionViewTestCase but with **class-based forms** and **FSM log disabled**
    """

    fsm_log_enabled = False
