from __future__ import annotations

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
        field=state, source=StateChoice.SUBMITTED_BY_USER, target=StateChoice.REVIEW_USER
    )
    @fsm.transition(
        field=state, source=StateChoice.SUBMITTED_BY_ADMIN, target=StateChoice.REVIEW_ADMIN
    )
    @fsm.transition(
        field=state, source=StateChoice.SUBMITTED_BY_ANONYMOUS, target=StateChoice.REVIEW_ANONYMOUS
    )
    @fsm.transition(field=state, source=fsm.ANY_STATE, target=StateChoice.REVIEW_ANONYMOUS)
    def review(self):
        self.counter += 1


class MultiDecoratorsTests(TestCase):
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
