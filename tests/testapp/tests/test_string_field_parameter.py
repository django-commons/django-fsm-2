from __future__ import annotations

from django.db import models
from django.test import TestCase

from django_fsm import FSMField
from django_fsm import transition


class BlogPostWithStringField(models.Model):
    state = FSMField(default="new")

    class Meta:
        app_label = "testapp"

    @transition(field="state", source="new", target="published", conditions=[])
    def publish(self):
        pass

    @transition(field="state", source="published", target="destroyed")
    def destroy(self):
        pass

    @transition(field="state", source="published", target="review")
    def review(self):
        pass


class StringFieldTestCase(TestCase):
    def setUp(self):
        self.model = BlogPostWithStringField()

    def test_initial_state(self):
        assert self.model.state == "new"
        self.model.publish()
        assert self.model.state == "published"
