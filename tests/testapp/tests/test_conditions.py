from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

import django_fsm as fsm


def condition_func(instance: models.Model) -> bool:
    return True


class BlogPostWithConditions(models.Model):
    state = fsm.FSMField(default="new")

    def model_condition(self: models.Model) -> bool:
        return True

    def unmet_condition(self: models.Model) -> bool:
        return False

    @fsm.transition(
        field=state, source="new", target="published", conditions=[condition_func, model_condition]
    )
    def publish(self):
        pass

    @fsm.transition(
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
        assert fsm.can_proceed(self.model.publish)
        self.model.publish()
        assert self.model.state == "published"

    def test_unmet_condition(self):
        self.model.publish()
        assert self.model.state == "published"
        assert not fsm.can_proceed(self.model.destroy)
        with pytest.raises(fsm.TransitionNotAllowed):
            self.model.destroy()

        assert fsm.can_proceed(self.model.destroy, check_conditions=False)
