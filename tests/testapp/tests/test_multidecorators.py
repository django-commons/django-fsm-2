from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm
from django_fsm.signals import post_transition


class MultiDecoratedModel(models.Model):
    counter = models.IntegerField(default=0)
    signal_counter = models.IntegerField(default=0)
    state = fsm.FSMField(default="SUBMITTED_BY_USER")

    @fsm.transition(field=state, source="SUBMITTED_BY_USER", target="REVIEW_USER")
    @fsm.transition(field=state, source="SUBMITTED_BY_ADMIN", target="REVIEW_ADMIN")
    @fsm.transition(field=state, source="SUBMITTED_BY_ANONYMOUS", target="REVIEW_ANONYMOUS")
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
