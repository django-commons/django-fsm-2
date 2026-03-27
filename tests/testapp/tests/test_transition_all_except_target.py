from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm

from ..choices import ApplicationState


class ExceptTargetTransition(models.Model):
    state = fsm.FSMField(choices=ApplicationState.choices, default=ApplicationState.NEW)

    @fsm.transition(field=state, source=ApplicationState.NEW, target=ApplicationState.PUBLISHED)
    def publish(self):
        pass

    @fsm.transition(field=state, source=fsm.ANY_OTHER_STATE, target=ApplicationState.REMOVED)
    def remove(self):
        pass


class TestExceptTargetTransition(TestCase):
    def setUp(self):
        self.model = ExceptTargetTransition()

    def test_usecase(self):
        assert self.model.state == ApplicationState.NEW
        assert fsm.can_proceed(self.model.remove)
        self.model.remove()

        assert self.model.state == ApplicationState.REMOVED
        assert not fsm.can_proceed(self.model.remove)
