from __future__ import annotations

from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase

import django_fsm as fsm
from django_fsm.admin import FSMAdminMixin
from django_fsm.signals import post_transition


class StateChoice(models.TextChoices):
    SUBMITTED_BY_USER = "SUBMITTED_BY_USER", "Submitted by user"
    REVIEW_USER = "REVIEW_USER", "Review user"
    SUBMITTED_BY_ADMIN = "SUBMITTED_BY_ADMIN", "Submitted by admin"
    REVIEW_ADMIN = "REVIEW_ADMIN", "Review admin"
    SUBMITTED_BY_ANONYMOUS = "SUBMITTED_BY_ANONYMOUS", "Submitted by anonymous"
    REVIEW_ANONYMOUS = "REVIEW_ANONYMOUS", "Review anonymous"


class MultiDecoratedModel(models.Model):
    counter = models.IntegerField(default=0)
    signal_counter = models.IntegerField(default=0)
    state = fsm.FSMField(choices=StateChoice.choices, default=StateChoice.SUBMITTED_BY_USER)

    @fsm.transition(
        field=state,
        source=StateChoice.SUBMITTED_BY_USER,
        target=StateChoice.REVIEW_USER,
        permission=lambda _instance, _user: False,
        custom={"label": "Review (user)"},
    )
    @fsm.transition(
        field=state,
        source=StateChoice.SUBMITTED_BY_ADMIN,
        target=StateChoice.REVIEW_ADMIN,
        permission=lambda _instance, user: user.is_staff,
        custom={"label": "Review (admin)"},
    )
    @fsm.transition(
        field=state,
        source=StateChoice.SUBMITTED_BY_ANONYMOUS,
        target=StateChoice.REVIEW_ANONYMOUS,
        custom={"label": "Review (anon)"},
    )
    @fsm.transition(
        field=state,
        source=fsm.ANY_STATE,
        target=StateChoice.REVIEW_ANONYMOUS,
        custom={"label": "Review (any)"},
    )
    def review(self):
        self.counter += 1


class MultiDecoratorsTestCase(TestCase):
    def setUp(self):
        self.model = MultiDecoratedModel()
        self.post_transition_called = False
        post_transition.connect(self.on_post_transition, sender=MultiDecoratedModel)

    def tearDown(self):
        post_transition.disconnect(self.on_post_transition, sender=MultiDecoratedModel)

    def on_post_transition(self, sender, instance, name, source, target, **kwargs):
        assert instance.state == target
        self.post_transition_called = True
        instance.signal_counter += 1

    def test_decorated_method_called_once(self):
        assert self.model.counter == 0
        assert self.model.signal_counter == 0

        self.model.review()

        assert self.model.counter == 1
        assert self.model.signal_counter == 1

        self.model.review()

        assert self.model.counter == 2  # noqa: PLR2004
        assert self.model.signal_counter == 2  # noqa: PLR2004


class MultiDecoratedAdmin(FSMAdminMixin, admin.ModelAdmin[MultiDecoratedModel]):
    fsm_fields = ["state"]


class TransitionByNameResolvesSourceStateTestCase(TestCase):
    """Regression: `_get_fsm_transition_by_name` must match the object's current
    source state — not return an arbitrary decoration entry."""

    staff_user: fsm.UserWithPermissions
    regular_user: fsm.UserWithPermissions

    @classmethod
    def setUpTestData(cls):
        User = get_user_model()  # noqa: N806
        cls.staff_user = User.objects.create_user(
            username="staff",
            password="x",  # noqa: S106
            is_staff=True,
        )
        cls.regular_user = User.objects.create_user(
            username="regular",
            password="x",  # noqa: S106
        )

    def setUp(self):
        self.model_admin = MultiDecoratedAdmin(MultiDecoratedModel, AdminSite())

    def _lookup(self, state: StateChoice) -> tuple[fsm.Transition, MultiDecoratedModel]:
        obj = MultiDecoratedModel()
        obj.state = state
        transition = self.model_admin._get_fsm_transition_by_name(obj=obj, transition_name="review")
        return transition, obj

    def test_matches_submitted_by_user_source(self):
        transition, obj = self._lookup(StateChoice.SUBMITTED_BY_USER)

        assert transition.source == StateChoice.SUBMITTED_BY_USER
        assert transition.custom["label"] == "Review (user)"
        assert transition.has_perm(obj, self.staff_user) is False
        assert transition.has_perm(obj, self.regular_user) is False

    def test_matches_submitted_by_admin_source(self):
        transition, obj = self._lookup(StateChoice.SUBMITTED_BY_ADMIN)

        assert transition.source == StateChoice.SUBMITTED_BY_ADMIN
        assert transition.custom["label"] == "Review (admin)"
        assert transition.has_perm(obj, self.staff_user) is True
        assert transition.has_perm(obj, self.regular_user) is False

    def test_matches_submitted_by_anonymous_source(self):
        transition, _obj = self._lookup(StateChoice.SUBMITTED_BY_ANONYMOUS)

        assert transition.source == StateChoice.SUBMITTED_BY_ANONYMOUS
        assert transition.custom["label"] == "Review (anon)"

    def test_falls_back_to_any_state_when_no_explicit_source_matches(self):
        transition, _obj = self._lookup(StateChoice.REVIEW_USER)

        assert transition.source == fsm.ANY_STATE
        assert transition.custom["label"] == "Review (any)"
