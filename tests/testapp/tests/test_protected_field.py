from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

import django_fsm as fsm

from ..choices import ApplicationState


class ProtectedAccessModel(models.Model):
    status = fsm.FSMField(
        choices=ApplicationState.choices, default=ApplicationState.NEW, protected=True
    )

    objects: models.Manager[ProtectedAccessModel] = models.Manager()

    @fsm.transition(field=status, source=ApplicationState.NEW, target=ApplicationState.PUBLISHED)
    def publish(self):
        pass


class MultiProtectedAccessModel(models.Model):
    status1 = fsm.FSMField(default=ApplicationState.NEW, protected=True)
    status2 = fsm.FSMField(default=ApplicationState.NEW, protected=True)

    objects: models.Manager[MultiProtectedAccessModel] = models.Manager()


class TestDirectAccessModels(TestCase):
    def test_multi_protected_field_create(self):
        instance = MultiProtectedAccessModel.objects.create()

        assert instance.status1 == ApplicationState.NEW
        assert instance.status2 == ApplicationState.NEW

    def test_no_direct_access(self):
        instance = ProtectedAccessModel()
        assert instance.status == ApplicationState.NEW

        def try_change() -> None:
            instance.status = "change"

        with pytest.raises(AttributeError):
            try_change()

        instance.publish()
        instance.save()

        assert instance.status == ApplicationState.PUBLISHED
