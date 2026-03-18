from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm
from django_fsm.signals import post_transition
from django_fsm.signals import pre_transition


class MultiResultTest(models.Model):
    state = fsm.FSMField(default="new")

    @fsm.transition(
        field=state, source="new", target=fsm.RETURN_VALUE("for_moderators", "published")
    )
    def publish(self, *, is_public=False):
        return "published" if is_public else "for_moderators"

    @fsm.transition(field=state, source="new", target=fsm.RETURN_VALUE())
    def publish_without_states(self, *, is_public=False):
        return "published" if is_public else "for_moderators"

    @fsm.transition(
        field=state,
        source="for_moderators",
        target=fsm.GET_STATE(
            lambda _, allowed: "published" if allowed else "rejected",
            states=["published", "rejected"],
        ),
    )
    def moderate(self, allowed):
        pass

    @fsm.transition(
        field=state,
        source="for_moderators",
        target=fsm.GET_STATE(
            lambda _, allowed: "published" if allowed else "rejected",
        ),
    )
    def moderate_without_states(self, allowed):
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

    def tearDown(self):
        pre_transition.disconnect(self.on_pre_transition, sender=MultiResultTest)
        post_transition.disconnect(self.on_post_transition, sender=MultiResultTest)

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

    def test_signals_called_with_get_state_without_states(self):
        instance = MultiResultTest(state="for_moderators")
        instance.moderate_without_states(allowed=False)
        assert self.pre_transition_called
        assert self.post_transition_called

    def test_signals_called_with_return_value(self):
        instance = MultiResultTest()
        instance.publish(is_public=True)
        assert self.pre_transition_called
        assert self.post_transition_called

    def test_signals_called_with_return_value_without_states(self):
        instance = MultiResultTest()
        instance.publish_without_states(is_public=True)
        assert self.pre_transition_called
        assert self.post_transition_called
