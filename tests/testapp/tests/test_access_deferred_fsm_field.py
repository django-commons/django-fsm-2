from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm


class DeferrableModel(models.Model):
    state = fsm.FSMField(default="new")

    objects: models.Manager[DeferrableModel] = models.Manager()

    @fsm.transition(field=state, source="new", target="published")
    def publish(self):
        pass

    @fsm.transition(field=state, source=fsm.ANY_OTHER_STATE, target="removed")
    def remove(self):
        pass


class Test(TestCase):
    def setUp(self):
        DeferrableModel.objects.create()
        self.model = DeferrableModel.objects.only("id").get()

    def test_usecase(self):
        assert self.model.state == "new"
        assert fsm.can_proceed(self.model.remove)
        self.model.remove()

        assert self.model.state == "removed"
        assert not fsm.can_proceed(self.model.remove)
