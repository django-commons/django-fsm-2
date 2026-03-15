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
    def review(self):
        self.counter += 1


def count_calls(sender, instance, name, source, target, **kwargs):
    instance.signal_counter += 1


post_transition.connect(count_calls, sender=MultiDecoratedModel)


class TestStateProxy(TestCase):
    def test_transition_method_called_once(self):
        model = MultiDecoratedModel()
        model.review()
        assert model.counter == 1
        assert model.signal_counter == 1
