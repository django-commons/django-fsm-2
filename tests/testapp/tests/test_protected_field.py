from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

from django_fsm import FSMField
from django_fsm import transition


class ProtectedAccessModel(models.Model):
    status = FSMField(default="new", protected=True)

    @transition(field=status, source="new", target="published")
    def publish(self):
        pass


class MultiProtectedAccessModel(models.Model):
    status1 = FSMField(default="new", protected=True)
    status2 = FSMField(default="new", protected=True)


class TestDirectAccessModels(TestCase):
    def test_multi_protected_field_create(self):
        obj = MultiProtectedAccessModel.objects.create()
        assert obj.status1 == "new"
        assert obj.status2 == "new"

    def test_no_direct_access(self):
        instance = ProtectedAccessModel()
        assert instance.status == "new"

        def try_change():
            instance.status = "change"

        with pytest.raises(AttributeError):
            try_change()

        instance.publish()
        instance.save()
        assert instance.status == "published"
