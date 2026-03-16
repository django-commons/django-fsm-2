from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm


class ExceptTargetTransition(models.Model):
    state = fsm.FSMField(default="new")

    @fsm.transition(field=state, source="new", target="published")
    def publish(self):
        pass

    @fsm.transition(field=state, source=fsm.ANY_OTHER_STATE, target="removed")
    def remove(self):
        pass


class TestExceptTargetTransition(TestCase):
    def setUp(self):
        self.model = ExceptTargetTransition()

    def test_usecase(self):
        assert self.model.state == "new"
        assert fsm.can_proceed(self.model.remove)
        self.model.remove()

        assert self.model.state == "removed"
        assert not fsm.can_proceed(self.model.remove)
