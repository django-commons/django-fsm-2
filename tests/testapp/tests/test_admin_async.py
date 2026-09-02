from __future__ import annotations

from unittest import mock

from asgiref.sync import async_to_sync
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.db import models
from django.http import HttpResponseRedirect
from django.test import TestCase
from django.test.client import RequestFactory

import django_fsm as fsm
from django_fsm.admin import FSMAdminMixin

from ..choices import ApplicationState


async def _async_perm_allow(_instance, _user):
    return True


async def _async_perm_deny(_instance, _user):
    return False


async def _async_true(_instance):
    return True


async def _async_false(_instance):
    return False


class AsyncAdminArticle(models.Model):
    state = fsm.FSMField(default=ApplicationState.NEW)

    class Meta:
        app_label = "testapp"

    @fsm.atransition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.PUBLISHED,
        custom={"admin": True},
    )
    async def publish(self):
        pass

    @fsm.atransition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.HIDDEN,
        permission=_async_perm_allow,
        custom={"admin": True},
    )
    async def hide(self):
        pass

    @fsm.atransition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.REJECTED,
        permission=_async_perm_deny,
        custom={"admin": True},
    )
    async def reject(self):
        pass

    @fsm.atransition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.MODERATED,
        conditions=[_async_false],
        custom={"admin": True},
    )
    async def moderate(self):
        pass


class AsyncArticleAdmin(FSMAdminMixin, admin.ModelAdmin):
    fsm_fields = ["state"]


class AdminAsyncTransitionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="alex",
            password="password",  # noqa: S106
            is_staff=True,
            is_superuser=True,
        )
        cls.article = AsyncAdminArticle.objects.create()

    def setUp(self):
        self.model_admin = AsyncArticleAdmin(AsyncAdminArticle, AdminSite())

    def make_request(self, *, data=None):
        factory = RequestFactory()
        request = factory.post("/", data=data or {})
        request.user = self.user
        return request

    def test_field_has_async_transition_detected(self):
        assert self.model_admin._field_has_async_transition("state")

    def test_extra_context_lists_async_transitions_filtered_by_async_perm_and_condition(self):
        request = self.make_request()

        contexts = list(self.model_admin._get_fsm_extra_context(request=request, obj=self.article))

        assert len(contexts) == 1
        names = {t.name for t in contexts[0].available_transitions}

        # publish (no perm, no condition) and hide (async perm allow) included.
        assert "publish" in names
        assert "hide" in names
        # reject (async perm deny) filtered out.
        assert "reject" not in names
        # moderate (async condition false) filtered out.
        assert "moderate" not in names

    def test_execute_fsm_transition_runs_async_method(self):
        request = self.make_request()
        article = AsyncAdminArticle.objects.create()

        self.model_admin._execute_fsm_transition(
            transition_func=article.publish,
            request=request,
        )

        # The async transition body ran and mutated state.
        assert article.state == ApplicationState.PUBLISHED

    @mock.patch.object(FSMAdminMixin, "message_user")
    def test_response_change_applies_async_transition_and_saves(self, _msg):  # noqa: PT019
        article = AsyncAdminArticle.objects.create()
        request = self.make_request(data={self.model_admin.fsm_post_param: "publish"})

        response = self.model_admin.response_change(request=request, obj=article)

        assert isinstance(response, HttpResponseRedirect)
        article.refresh_from_db()
        assert article.state == ApplicationState.PUBLISHED

    @mock.patch.object(FSMAdminMixin, "message_user")
    def test_response_change_runs_async_transition_when_directly_posted(self, _msg):  # noqa: PT019
        # Without a configured transition form, response_change goes through
        # _apply_fsm_transition without re-checking permission. This mirrors the
        # existing sync behavior. The async wrapper is bridged via async_to_sync.
        article = AsyncAdminArticle.objects.create()
        request = self.make_request(data={self.model_admin.fsm_post_param: "reject"})

        response = self.model_admin.response_change(request=request, obj=article)

        assert isinstance(response, HttpResponseRedirect)
        article.refresh_from_db()
        assert article.state == ApplicationState.REJECTED


class AdminTransitionViewPermissionTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = get_user_model().objects.create_user(
            username="alex2",
            password="password",  # noqa: S106
            is_staff=True,
            is_superuser=True,
        )

    def setUp(self):
        self.model_admin = AsyncArticleAdmin(AsyncAdminArticle, AdminSite())

    def test_async_permission_denial_blocks_transition_view(self):
        article = AsyncAdminArticle.objects.create()
        transition = self.model_admin._get_fsm_transition_by_name(
            obj=article, transition_name="reject"
        )

        has_perm = async_to_sync(transition.ahas_perm)(article, self.user)

        assert has_perm is False

    def test_async_permission_allow_returns_true(self):
        article = AsyncAdminArticle.objects.create()
        transition = self.model_admin._get_fsm_transition_by_name(
            obj=article, transition_name="hide"
        )

        has_perm = async_to_sync(transition.ahas_perm)(article, self.user)

        assert has_perm is True
