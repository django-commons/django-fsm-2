from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models
from django.test import TestCase

import django_fsm as fsm
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
        custom={"label": "Review (always forbidden)"},
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
    def review(self) -> None:
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


class MultiDecoratedTransitionPermissionsTestCase(TestCase):
    """Each `@fsm.transition` decoration on `review` carries its own permission —
    `has_transition_perm` must check the one matching the instance's current
    source state, not some other decoration on the same method."""

    def setUp(self):
        self.staff_user = User.objects.create(username="staff", is_staff=True)
        self.regular_user = User.objects.create(username="regular")

    def test_denies_everyone_when_source_permission_is_always_false(self):
        model = MultiDecoratedModel(state=StateChoice.SUBMITTED_BY_USER)

        assert not fsm.has_transition_perm(model.review, self.staff_user)
        assert not fsm.has_transition_perm(model.review, self.regular_user)

    def test_checks_is_staff_permission_for_admin_source_state(self):
        model = MultiDecoratedModel(state=StateChoice.SUBMITTED_BY_ADMIN)

        assert fsm.has_transition_perm(model.review, self.staff_user)
        assert not fsm.has_transition_perm(model.review, self.regular_user)

    def test_allows_everyone_when_source_state_has_no_permission(self):
        model = MultiDecoratedModel(state=StateChoice.SUBMITTED_BY_ANONYMOUS)

        assert fsm.has_transition_perm(model.review, self.staff_user)
        assert fsm.has_transition_perm(model.review, self.regular_user)

    def test_falls_back_to_any_state_permission(self):
        model = MultiDecoratedModel(state=StateChoice.REVIEW_USER)

        assert fsm.has_transition_perm(model.review, self.staff_user)
        assert fsm.has_transition_perm(model.review, self.regular_user)

    def test_available_user_state_transitions_respects_source_permission(self):
        model = MultiDecoratedModel(state=StateChoice.SUBMITTED_BY_ADMIN)

        staff_transitions = {
            transition.name
            for transition in model.get_available_user_state_transitions(  # type: ignore[attr-defined]
                self.staff_user
            )
        }
        regular_transitions = {
            transition.name
            for transition in model.get_available_user_state_transitions(  # type: ignore[attr-defined]
                self.regular_user
            )
        }

        assert staff_transitions == {"review"}
        assert regular_transitions == set()
