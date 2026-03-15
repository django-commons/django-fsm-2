from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm
from django_fsm.signals import post_transition
from django_fsm.signals import pre_transition


class ApplicationState(models.TextChoices):
    NEW = "NEW", "New"
    FOR_MODERATORS = "FOR_MODERATORS", "for moderators"
    PUBLISHED = "PUBLISHED", "Published"
    REJECTED = "REJECTED", "Rejected"


class MultiResultTest(models.Model):
    state = fsm.FSMField(choices=ApplicationState.choices, default=ApplicationState.NEW)

    @fsm.transition(
        field=state,
        source=ApplicationState.NEW,
        target=fsm.RETURN_VALUE(ApplicationState.FOR_MODERATORS, ApplicationState.PUBLISHED),
    )
    def publish(self, *, is_public=False):
        return ApplicationState.PUBLISHED if is_public else ApplicationState.FOR_MODERATORS

    @fsm.transition(field=state, source=ApplicationState.NEW, target=fsm.RETURN_VALUE())
    def publish_without_states(self, *, is_public=False):
        return ApplicationState.PUBLISHED if is_public else ApplicationState.FOR_MODERATORS

    @fsm.transition(
        field=state,
        source=ApplicationState.FOR_MODERATORS,
        target=fsm.GET_STATE(
            lambda _, allowed: ApplicationState.PUBLISHED if allowed else ApplicationState.REJECTED,
            states=[ApplicationState.PUBLISHED, ApplicationState.REJECTED],
        ),
    )
    def moderate(self, allowed):
        pass

    @fsm.transition(
        field=state,
        source=ApplicationState.FOR_MODERATORS,
        target=fsm.GET_STATE(
            lambda _, allowed: ApplicationState.PUBLISHED if allowed else ApplicationState.REJECTED,
        ),
    )
    def moderate_without_states(self, allowed):
        pass


class Test(TestCase):
    def test_return_state_succeed(self):
        instance = MultiResultTest()
        instance.publish(is_public=True)
        assert instance.state == ApplicationState.PUBLISHED

    def test_get_state_succeed(self):
        instance = MultiResultTest(state=ApplicationState.FOR_MODERATORS)
        instance.moderate(allowed=False)
        assert instance.state == ApplicationState.REJECTED


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
        instance = MultiResultTest(state=ApplicationState.FOR_MODERATORS)
        instance.moderate(allowed=False)
        assert self.pre_transition_called
        assert self.post_transition_called

    def test_signals_called_with_get_state_without_states(self):
        instance = MultiResultTest(state=ApplicationState.FOR_MODERATORS)
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
