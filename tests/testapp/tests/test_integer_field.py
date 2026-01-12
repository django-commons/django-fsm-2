from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

from django_fsm_rx import FSMIntegerField
from django_fsm_rx import TransitionNotAllowed
from django_fsm_rx import transition


class BlogPostStateEnum:
    NEW = 10
    PUBLISHED = 20
    HIDDEN = 30


class BlogPostWithIntegerField(models.Model):
    state = FSMIntegerField(default=BlogPostStateEnum.NEW)

    @transition(field=state, source=BlogPostStateEnum.NEW, target=BlogPostStateEnum.PUBLISHED)
    def publish(self):
        pass

    @transition(field=state, source=BlogPostStateEnum.PUBLISHED, target=BlogPostStateEnum.HIDDEN)
    def hide(self):
        pass


class BlogPostWithIntegerFieldTest(TestCase):
    def setUp(self):
        self.model = BlogPostWithIntegerField()

    def test_known_transition_should_succeed(self):
        self.model.publish()
        assert self.model.state == BlogPostStateEnum.PUBLISHED

        self.model.hide()
        assert self.model.state == BlogPostStateEnum.HIDDEN

    def test_unknown_transition_fails(self):
        with pytest.raises(TransitionNotAllowed):
            self.model.hide()
