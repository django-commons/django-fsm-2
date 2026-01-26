from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

from django_fsm import FSMField
from django_fsm import FSMModelMixin
from django_fsm import transition


class RefreshableProtectedAccessModel(models.Model):
    status = FSMField(default="new", protected=True)

    objects: models.Manager[RefreshableProtectedAccessModel] = models.Manager()

    @transition(field=status, source="new", target="published")
    def publish(self):
        pass


class RefreshableModel(FSMModelMixin, RefreshableProtectedAccessModel):
    pass


class TestDirectAccessModels(TestCase):
    def test_no_direct_access(self):
        instance = RefreshableProtectedAccessModel()
        assert instance.status == "new"

        with pytest.raises(AttributeError):
            instance.status = "change"

        instance.publish()
        instance.save()
        assert instance.status == "published"

    def test_refresh_from_db(self):
        instance = RefreshableModel()
        assert instance.status == "new"
        instance.save()

        instance.refresh_from_db()
        assert instance.status == "new"

    def test_concurrent_refresh_from_db(self):
        instance = RefreshableModel()
        assert instance.status == "new"
        instance.save()

        # NOTE: This simulates a concurrent update scenario
        concurrent_instance = RefreshableModel.objects.get(pk=instance.pk)
        assert concurrent_instance.status == instance.status == "new"
        concurrent_instance.publish()
        assert concurrent_instance.status == "published"
        concurrent_instance.save()

        assert instance.status == "new"
        instance.refresh_from_db()
        assert instance.status == "published"
