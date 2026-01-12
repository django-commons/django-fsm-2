from __future__ import annotations

from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.test import TestCase

from django_fsm_rx import has_transition_perm
from tests.testapp.models import BlogPost


class PermissionFSMFieldTest(TestCase):
    def setUp(self):
        self.model = BlogPost()
        self.unprivileged = User.objects.create(username="unprivileged")
        self.privileged = User.objects.create(username="privileged")
        self.staff = User.objects.create(username="staff", is_staff=True)

        self.privileged.user_permissions.add(Permission.objects.get_by_natural_key("can_publish_post", "testapp", "blogpost"))
        self.privileged.user_permissions.add(Permission.objects.get_by_natural_key("can_remove_post", "testapp", "blogpost"))

    def test_privileged_access_succeed(self):
        self.assertTrue(has_transition_perm(self.model.publish, self.privileged))
        self.assertTrue(has_transition_perm(self.model.remove, self.privileged))

        transitions = self.model.get_available_user_state_transitions(self.privileged)
        self.assertEqual(
            {"publish", "remove", "moderate"},
            {transition.name for transition in transitions},
        )

    def test_unprivileged_access_prohibited(self):
        self.assertFalse(has_transition_perm(self.model.publish, self.unprivileged))
        self.assertFalse(has_transition_perm(self.model.remove, self.unprivileged))

        transitions = self.model.get_available_user_state_transitions(self.unprivileged)
        self.assertEqual({"moderate"}, {transition.name for transition in transitions})

    def test_permission_instance_method(self):
        self.assertFalse(has_transition_perm(self.model.restore, self.unprivileged))
        self.assertTrue(has_transition_perm(self.model.restore, self.staff))
