from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm

from ..choices import ApplicationState


class BlogPostWithStringField(models.Model):
    state = fsm.FSMField(choices=ApplicationState.choices, default=ApplicationState.NEW)

    @fsm.transition(
        field="state", source=ApplicationState.NEW, target=ApplicationState.PUBLISHED, conditions=[]
    )
    def publish(self):
        pass

    @fsm.transition(
        field="state", source=ApplicationState.PUBLISHED, target=ApplicationState.REMOVED
    )
    def remove(self):
        pass

    @fsm.transition(
        field="state", source=ApplicationState.PUBLISHED, target=ApplicationState.MODERATED
    )
    def review(self):
        pass


class StringFieldTestCase(TestCase):
    def setUp(self):
        self.model = BlogPostWithStringField()

    def test_initial_state(self):
        assert self.model.state == ApplicationState.NEW
        self.model.publish()
        assert self.model.state == ApplicationState.PUBLISHED
