from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm


class BlogPostWithStringField(models.Model):
    state = fsm.FSMField(default="new")

    @fsm.transition(field="state", source="new", target="published", conditions=[])
    def publish(self):
        pass

    @fsm.transition(field="state", source="published", target="destroyed")
    def destroy(self):
        pass

    @fsm.transition(field="state", source="published", target="review")
    def review(self):
        pass


class StringFieldTestCase(TestCase):
    def setUp(self):
        self.model = BlogPostWithStringField()

    def test_initial_state(self):
        assert self.model.state == "new"
        self.model.publish()
        assert self.model.state == "published"
