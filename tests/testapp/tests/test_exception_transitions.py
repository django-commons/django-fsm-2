from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

import django_fsm as fsm
from django_fsm.signals import post_transition

from ..choices import ApplicationState


class ExceptionalBlogPost(models.Model):
    state = fsm.FSMField(choices=ApplicationState.choices, default=ApplicationState.NEW)

    @fsm.transition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.PUBLISHED,
        on_error=ApplicationState.CRASHED,
    )
    def publish(self):
        raise Exception("Upss")

    @fsm.transition(field=state, source=ApplicationState.NEW, target=ApplicationState.REMOVED)
    def delete(self):
        raise Exception("Upss")


class FSMFieldExceptionTest(TestCase):
    def setUp(self):
        self.model = ExceptionalBlogPost()
        post_transition.connect(self.on_post_transition, sender=ExceptionalBlogPost)
        self.post_transition_data = {}

    def tearDown(self):
        post_transition.disconnect(self.on_post_transition, sender=ExceptionalBlogPost)

    def on_post_transition(self, **kwargs):
        self.post_transition_data = kwargs

    def test_state_moves_to_error_on_exception(self):
        assert fsm.can_proceed(self.model.publish)

        with pytest.raises(Exception, match="Upss"):
            self.model.publish()

        assert self.model.state == ApplicationState.CRASHED
        assert self.post_transition_data["target"] == ApplicationState.CRASHED
        assert "exception" in self.post_transition_data

    def test_state_unchanged_without_error_target(self):
        assert fsm.can_proceed(self.model.delete)

        with pytest.raises(Exception, match="Upss"):
            self.model.delete()

        assert self.model.state == ApplicationState.NEW
        assert self.post_transition_data == {}
