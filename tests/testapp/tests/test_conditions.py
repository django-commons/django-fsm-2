from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

import django_fsm as fsm

from ..choices import ApplicationState


def condition_func(instance: models.Model) -> bool:
    return True


class BlogPostWithConditions(models.Model):
    state = fsm.FSMField(default=ApplicationState.NEW)

    def model_condition(self: models.Model) -> bool:
        return True

    def unmet_condition(self: models.Model) -> bool:
        return False

    @fsm.transition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.PUBLISHED,
        conditions=[condition_func, model_condition],
    )
    def publish(self):
        pass

    @fsm.transition(
        field=state,
        source=ApplicationState.PUBLISHED,
        target=ApplicationState.REMOVED,
        conditions=[condition_func, unmet_condition],
    )
    def remove(self):
        pass


class ConditionTransitionTests(TestCase):
    def setUp(self):
        self.model = BlogPostWithConditions()

    def test_initial_state_instantiated(self):
        assert self.model.state == ApplicationState.NEW

    def test_valid_condition_should_succeed(self):
        assert fsm.can_proceed(self.model.publish)

        self.model.publish()

        assert self.model.state == ApplicationState.PUBLISHED

    def test_unmet_condition(self):
        self.model.publish()

        assert self.model.state == ApplicationState.PUBLISHED

        assert not fsm.can_proceed(self.model.remove)

        with pytest.raises(fsm.TransitionNotAllowed):
            self.model.remove()

        assert fsm.can_proceed(self.model.remove, check_conditions=False)

    def test_failed_condition_reported_on_exception(self):
        self.model.publish()
        with pytest.raises(fsm.TransitionNotAllowed) as exc_info:
            self.model.remove()
        assert exc_info.value.failed_condition is BlogPostWithConditions.unmet_condition

    def test_failed_condition_named_in_message(self):
        self.model.publish()
        with pytest.raises(fsm.TransitionNotAllowed, match="unmet_condition"):
            self.model.remove()

    def test_failed_condition_is_none_when_no_condition_failure(self):
        """TransitionNotAllowed for a missing transition has no failed_condition."""
        with pytest.raises(fsm.TransitionNotAllowed) as exc_info:
            self.model.remove()  # state is "new", destroy only works from "published"
        assert exc_info.value.failed_condition is None


def _eval_tracking_condition(instance: models.Model) -> bool:
    instance._eval_log.append("first")
    return False


def _never_reached_condition(instance: models.Model) -> bool:
    instance._eval_log.append("second")
    return False


class BlogPostShortCircuit(models.Model):
    state = fsm.FSMField(default="new")

    @fsm.transition(
        field=state,
        source="new",
        target="published",
        conditions=[_eval_tracking_condition, _never_reached_condition],
    )
    def publish(self):
        pass


class ShortCircuitTest(TestCase):
    def test_only_first_failing_condition_evaluated(self):
        obj = BlogPostShortCircuit()
        obj._eval_log = []
        with pytest.raises(fsm.TransitionNotAllowed) as exc_info:
            obj.publish()
        assert exc_info.value.failed_condition is _eval_tracking_condition
        assert obj._eval_log == ["first"]
