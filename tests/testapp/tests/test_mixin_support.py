from __future__ import annotations

from django.db import models
from django.test import TestCase

from django_fsm import FSMField
from django_fsm import transition


class WorkflowMixin:
    @transition(field="state", source="*", target="draft")
    def draft(self):
        pass

    @transition(field="state", source="draft", target="published")
    def publish(self):
        pass


class MixinSupportTestModel(WorkflowMixin, models.Model):
    state = FSMField(default="new")


class Test(TestCase):
    def test_usecase(self):
        model = MixinSupportTestModel()

        model.draft()
        assert model.state == "draft"

        model.publish()
        assert model.state == "published"
