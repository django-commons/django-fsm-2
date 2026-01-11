from __future__ import annotations

from django.db import models
from django.test import TestCase

from django_fsm_2 import FSMField
from django_fsm_2 import transition
from django_fsm_2.signals import post_transition


class MultiDecoratedModel(models.Model):
    counter = models.IntegerField(default=0)
    signal_counter = models.IntegerField(default=0)
    state = FSMField(default="SUBMITTED_BY_USER")

    @transition(field=state, source="SUBMITTED_BY_USER", target="REVIEW_USER")
    @transition(field=state, source="SUBMITTED_BY_ADMIN", target="REVIEW_ADMIN")
    @transition(field=state, source="SUBMITTED_BY_ANONYMOUS", target="REVIEW_ANONYMOUS")
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
