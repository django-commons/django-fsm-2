from __future__ import annotations

from django.db import models
from django.test import TestCase

from django_fsm import FSMField
from django_fsm import FSMModelMixin
from django_fsm import transition


class RefreshableProtectedAccessModel(models.Model):
    status = FSMField(default="new", protected=True)

    class Meta:
        app_label = "django_fsm"

    @transition(field=status, source="new", target="published")
    def publish(self):
        pass


class RefreshableModel(FSMModelMixin, RefreshableProtectedAccessModel):
    pass


class TestDirectAccessModels(TestCase):
    def test_no_direct_access(self):
        instance = RefreshableProtectedAccessModel()
        self.assertEqual(instance.status, "new")

        def try_change():
            instance.status = "change"

        self.assertRaises(AttributeError, try_change)

        instance.publish()
        instance.save()
        self.assertEqual(instance.status, "published")

    def test_refresh_from_db(self):
        instance = RefreshableModel()
        instance.save()

        instance.refresh_from_db()
