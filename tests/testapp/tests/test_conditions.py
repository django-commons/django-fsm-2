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
