from __future__ import annotations

from django.db import models
from django.test import TestCase

from django_fsm import GET_STATE
from django_fsm import RETURN_VALUE
from django_fsm import FSMField
from django_fsm import transition
from django_fsm.signals import post_transition
from django_fsm.signals import pre_transition


class MultiResultTest(models.Model):
    state = FSMField(default="new")

    @transition(field=state, source="new", target=RETURN_VALUE("for_moderators", "published"))
    def publish(self, *, is_public=False):
        return "published" if is_public else "for_moderators"

    @transition(
        field=state,
        source="for_moderators",
        target=GET_STATE(lambda _, allowed: "published" if allowed else "rejected", states=["published", "rejected"]),
    )
    def moderate(self, allowed):
        pass


class Test(TestCase):
    def test_return_state_succeed(self):
        instance = MultiResultTest()
        instance.publish(is_public=True)
        assert instance.state == "published"

    def test_get_state_succeed(self):
        instance = MultiResultTest(state="for_moderators")
        instance.moderate(allowed=False)
        assert instance.state == "rejected"


class TestSignals(TestCase):
    def setUp(self):
        self.pre_transition_called = False
        self.post_transition_called = False
        pre_transition.connect(self.on_pre_transition, sender=MultiResultTest)
        post_transition.connect(self.on_post_transition, sender=MultiResultTest)

    def on_pre_transition(self, sender, instance, name, source, target, **kwargs):
        assert instance.state == source
        self.pre_transition_called = True

    def on_post_transition(self, sender, instance, name, source, target, **kwargs):
        assert instance.state == target
        self.post_transition_called = True

    def test_signals_called_with_get_state(self):
        instance = MultiResultTest(state="for_moderators")
        instance.moderate(allowed=False)
        assert self.pre_transition_called
        assert self.post_transition_called

    def test_signals_called_with_return_value(self):
        instance = MultiResultTest()
        instance.publish(is_public=True)
        assert self.pre_transition_called
        assert self.post_transition_called
