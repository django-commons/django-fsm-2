from __future__ import annotations

from django.contrib.auth.models import User
from django.db import models
from django.test import TestCase
from django.test.utils import override_settings
from guardian.shortcuts import assign_perm

import django_fsm as fsm

from ..choices import ApplicationState


class ObjectPermissionTestModel(models.Model):
    state = fsm.FSMField(choices=ApplicationState.choices, default=ApplicationState.NEW)

    objects: models.Manager[ObjectPermissionTestModel] = models.Manager()

    class Meta:
        permissions = [
            ("can_publish_objectpermissiontestmodel", "Can publish ObjectPermissionTestModel"),
        ]

    @fsm.transition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.PUBLISHED,
        on_error=ApplicationState.FAILED,
        permission="testapp.can_publish_objectpermissiontestmodel",
    )
    def publish(self) -> None:
        pass


@override_settings(
    AUTHENTICATION_BACKENDS=(
        "django.contrib.auth.backends.ModelBackend",
        "guardian.backends.ObjectPermissionBackend",
    )
)
class ObjectPermissionFSMFieldTest(TestCase):
    def setUp(self):
        super().setUp()
        self.model = ObjectPermissionTestModel.objects.create()

        self.unprivileged = User.objects.create(username="unprivileged")
        self.privileged = User.objects.create(username="object_only_privileged")
        assign_perm("can_publish_objectpermissiontestmodel", self.privileged, self.model)

    def test_object_only_access_success(self):
        assert fsm.has_transition_perm(self.model.publish, self.privileged)

        self.model.publish()

    def test_object_only_other_access_prohibited(self):
        assert not fsm.has_transition_perm(self.model.publish, self.unprivileged)
