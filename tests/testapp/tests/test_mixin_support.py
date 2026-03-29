from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm

from ..choices import ApplicationState


class WorkflowMixin:
    @fsm.transition(field="state", source=fsm.ANY_STATE, target=ApplicationState.DRAFT)
    def draft(self):
        pass

    @fsm.transition(field="state", source=ApplicationState.DRAFT, target=ApplicationState.PUBLISHED)
    def publish(self):
        pass


class MixinSupportTestModel(WorkflowMixin, models.Model):
    state = fsm.FSMField(choices=ApplicationState.choices, default=ApplicationState.NEW)


class MixinSupportTests(TestCase):
    def test_mixin_methods_drive_state_changes(self):
        model = MixinSupportTestModel()

        model.draft()
        assert model.state == ApplicationState.DRAFT

        model.publish()
        assert model.state == ApplicationState.PUBLISHED
