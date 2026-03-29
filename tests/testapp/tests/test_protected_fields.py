from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

import django_fsm as fsm

from ..choices import ApplicationState


class RefreshableProtectedAccessModel(models.Model):
    status = fsm.FSMField(
        choices=ApplicationState.choices, default=ApplicationState.NEW, protected=True
    )

    objects: models.Manager[RefreshableProtectedAccessModel] = models.Manager()

    @fsm.transition(field=status, source=ApplicationState.NEW, target=ApplicationState.PUBLISHED)
    def publish(self):
        pass


class RefreshableModel(fsm.FSMModelMixin, RefreshableProtectedAccessModel):
    pass


class TestDirectAccessModels(TestCase):
    def test_no_direct_access(self):
        instance = RefreshableProtectedAccessModel()
        assert instance.status == ApplicationState.NEW

        with pytest.raises(AttributeError):
            instance.status = "change"

        instance.publish()
        instance.save()

        assert instance.status == ApplicationState.PUBLISHED

    def test_refresh_from_db(self):
        instance = RefreshableModel()
        assert instance.status == ApplicationState.NEW

        instance.save()
        instance.refresh_from_db()

        assert instance.status == ApplicationState.NEW

    def test_concurrent_refresh_from_db(self):
        instance = RefreshableModel()
        assert instance.status == ApplicationState.NEW

        instance.save()

        # NOTE: This simulates a concurrent update scenario
        concurrent_instance = RefreshableModel.objects.get(pk=instance.pk)
        assert concurrent_instance.status == instance.status == ApplicationState.NEW

        concurrent_instance.publish()
        assert concurrent_instance.status == ApplicationState.PUBLISHED

        concurrent_instance.save()

        assert instance.status == ApplicationState.NEW

        instance.refresh_from_db()
        assert instance.status == ApplicationState.PUBLISHED
