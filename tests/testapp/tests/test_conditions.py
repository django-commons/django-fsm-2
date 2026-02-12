from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

from django_fsm import FSMField
from django_fsm import TransitionNotAllowed
from django_fsm import can_proceed
from django_fsm import transition


def condition_func(instance: models.Model) -> bool:
    return True


class BlogPostWithConditions(models.Model):
    state = FSMField(default="new")

    def model_condition(self: models.Model) -> bool:
        return True

    def unmet_condition(self: models.Model) -> bool:
        return False

    @transition(
        field=state, source="new", target="published", conditions=[condition_func, model_condition]
    )
    def publish(self):
        pass

    @transition(
        field=state,
        source="published",
        target="destroyed",
        conditions=[condition_func, unmet_condition],
    )
    def destroy(self):
        pass


class ConditionalTest(TestCase):
    def setUp(self):
        self.model = BlogPostWithConditions()

    def test_initial_staet(self):
        assert self.model.state == "new"

    def test_known_transition_should_succeed(self):
        assert can_proceed(self.model.publish)
        self.model.publish()
        assert self.model.state == "published"

    def test_unmet_condition(self):
        self.model.publish()
        assert self.model.state == "published"
        assert not can_proceed(self.model.destroy)
        with pytest.raises(TransitionNotAllowed):
            self.model.destroy()

        assert can_proceed(self.model.destroy, check_conditions=False)

    def test_failed_condition_reported_on_exception(self):
        self.model.publish()
        with pytest.raises(TransitionNotAllowed) as exc_info:
            self.model.destroy()
        assert exc_info.value.failed_condition is BlogPostWithConditions.unmet_condition

    def test_failed_condition_named_in_message(self):
        self.model.publish()
        with pytest.raises(TransitionNotAllowed, match="unmet_condition"):
            self.model.destroy()

    def test_failed_condition_is_none_when_no_condition_failure(self):
        """TransitionNotAllowed for a missing transition has no failed_condition."""
        with pytest.raises(TransitionNotAllowed) as exc_info:
            self.model.destroy()  # state is "new", destroy only works from "published"
        assert exc_info.value.failed_condition is None


def _eval_tracking_condition(instance: models.Model) -> bool:
    instance._eval_log.append("first")  # type: ignore[attr-defined]
    return False


def _never_reached_condition(instance: models.Model) -> bool:
    instance._eval_log.append("second")  # type: ignore[attr-defined]
    return False


class BlogPostShortCircuit(models.Model):
    state = FSMField(default="new")

    _eval_log: list[str] = []

    @transition(
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
        with pytest.raises(TransitionNotAllowed) as exc_info:
            obj.publish()
        assert exc_info.value.failed_condition is _eval_tracking_condition
        assert obj._eval_log == ["first"]
