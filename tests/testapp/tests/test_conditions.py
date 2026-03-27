from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

import django_fsm as fsm


class ApplicationState(models.TextChoices):
    NEW = "new", "New"
    PUBLISHED = "published", "Published"
    DESTROYED = "destroyed", "Destroyed"


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
        target=ApplicationState.DESTROYED,
        conditions=[condition_func, unmet_condition],
    )
    def destroy(self):
        pass


class ConditionalTest(TestCase):
    def setUp(self):
        self.model = BlogPostWithConditions()

    def test_initial_staet(self):
        assert self.model.state == ApplicationState.NEW

    def test_known_transition_should_succeed(self):
        assert fsm.can_proceed(self.model.publish)
        self.model.publish()
        assert self.model.state == ApplicationState.PUBLISHED

    def test_unmet_condition(self):
        self.model.publish()
        assert self.model.state == ApplicationState.PUBLISHED
        assert not fsm.can_proceed(self.model.destroy)
        with pytest.raises(fsm.TransitionNotAllowed):
            self.model.destroy()

        assert fsm.can_proceed(self.model.destroy, check_conditions=False)
