from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm


class StateChoice(models.TextChoices):
    NEW = "NEW", "new"
    PUBLISHED = "PUBLISHED", "published"
    REMOVED = "REMOVED", "removed"


class DeferrableModel(models.Model):
    state = fsm.FSMField(choices=StateChoice.choices, default=StateChoice.NEW)

    objects: models.Manager[DeferrableModel] = models.Manager()

    @fsm.transition(field=state, source=StateChoice.NEW, target=StateChoice.PUBLISHED)
    def publish(self):
        pass

    @fsm.transition(field=state, source=fsm.ANY_OTHER_STATE, target=StateChoice.REMOVED)
    def remove(self):
        pass


class Test(TestCase):
    def setUp(self):
        DeferrableModel.objects.create()
        self.model = DeferrableModel.objects.only("id").get()

    def test_usecase(self):
        assert self.model.state == StateChoice.NEW
        assert fsm.can_proceed(self.model.remove)
        self.model.remove()

        assert self.model.state == StateChoice.REMOVED
        assert not fsm.can_proceed(self.model.remove)
