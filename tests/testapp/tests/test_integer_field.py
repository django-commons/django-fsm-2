from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

import django_fsm as fsm

from ..choices import BlogPostState


class BlogPostWithIntegerField(models.Model):
    state = fsm.FSMIntegerField(choices=BlogPostState.choices, default=BlogPostState.NEW)

    @fsm.transition(field=state, source=BlogPostState.NEW, target=BlogPostState.PUBLISHED)
    def publish(self):
        pass

    @fsm.transition(field=state, source=BlogPostState.PUBLISHED, target=BlogPostState.HIDDEN)
    def hide(self):
        pass


class BlogPostWithIntegerFieldTest(TestCase):
    def setUp(self):
        self.model = BlogPostWithIntegerField()

    def test_known_transition_should_succeed(self):
        self.model.publish()
        assert self.model.state == BlogPostState.PUBLISHED

        self.model.hide()
        assert self.model.state == BlogPostState.HIDDEN

    def test_unknown_transition_fails(self):
        with pytest.raises(fsm.TransitionNotAllowed):
            self.model.hide()
