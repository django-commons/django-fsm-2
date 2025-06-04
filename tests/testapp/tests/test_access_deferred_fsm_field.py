from __future__ import annotations

from django.db import models
from django.test import TestCase

from django_fsm import FSMField
from django_fsm import can_proceed
from django_fsm import transition


class DeferrableModel(models.Model):
    state = FSMField(default="new")

    @transition(field=state, source="new", target="published")
    def publish(self):
        pass

    @transition(field=state, source="+", target="removed")
    def remove(self):
        pass


class Test(TestCase):
    def setUp(self):
        DeferrableModel.objects.create()
        self.model = DeferrableModel.objects.only("id").get()

    def test_usecase(self):
        assert self.model.state == "new"
        assert can_proceed(self.model.remove)
        self.model.remove()

        assert self.model.state == "removed"
        assert not can_proceed(self.model.remove)
