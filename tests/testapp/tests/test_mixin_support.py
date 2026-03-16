from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm


class WorkflowMixin:
    @fsm.transition(field="state", source=fsm.ANY_STATE, target="draft")
    def draft(self):
        pass

    @fsm.transition(field="state", source="draft", target="published")
    def publish(self):
        pass


class MixinSupportTestModel(WorkflowMixin, models.Model):
    state = fsm.FSMField(default="new")


class Test(TestCase):
    def test_usecase(self):
        model = MixinSupportTestModel()

        model.draft()
        assert model.state == "draft"

        model.publish()
        assert model.state == "published"
