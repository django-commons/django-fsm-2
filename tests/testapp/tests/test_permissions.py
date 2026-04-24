from __future__ import annotations

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import TestCase

import django_fsm as fsm
from tests.testapp.models import BlogPost


class PermissionFSMFieldTest(TestCase):
    def setUp(self):
        self.model = BlogPost()
        self.unprivileged_user = User.objects.create(username="unprivileged")
        self.privileged_user = User.objects.create(username="privileged")
        self.staff_user = User.objects.create(username="staff", is_staff=True)

        self.privileged_user.user_permissions.add(
            Permission.objects.get_by_natural_key("can_publish_post", "testapp", "blogpost")
        )
        self.privileged_user.user_permissions.add(
            Permission.objects.get_by_natural_key("can_remove_post", "testapp", "blogpost")
        )

    def test_privileged_access_succeed(self):
        assert fsm.has_transition_perm(self.model.publish, self.privileged_user)
        assert fsm.has_transition_perm(self.model.remove, self.privileged_user)

        available_transitions = self.model.get_available_user_state_transitions(  # type: ignore[attr-defined]
            self.privileged_user
        )
        assert {transition.name for transition in available_transitions} == {
            "publish",
            "remove",
            "moderate",
        }

    def test_unprivileged_access_prohibited(self):
        assert not fsm.has_transition_perm(self.model.publish, self.unprivileged_user)
        assert not fsm.has_transition_perm(self.model.remove, self.unprivileged_user)

        available_transitions = self.model.get_available_user_state_transitions(  # type: ignore[attr-defined]
            self.unprivileged_user
        )
        assert {transition.name for transition in available_transitions} == {"moderate"}

    def test_permission_instance_method(self):
        assert not fsm.has_transition_perm(self.model.restore, self.unprivileged_user)
        assert fsm.has_transition_perm(self.model.restore, self.staff_user)
