"""Tests for FSMAdminMixin functionality."""

from __future__ import annotations

from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import Client
from django.test import RequestFactory
from django.test import TestCase
from django.test import override_settings
from django.urls import reverse

from django_fsm.admin import FSMAdminMixin

from ..admin import AdminArticleAdmin
from ..models import AdminArticle


class FSMAdminMixinTests(TestCase):
    """Tests for FSMAdminMixin basic functionality."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass",
        )

    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin = AdminArticleAdmin(AdminArticle, self.site)
        self.client = Client()
        self.client.login(username="admin", password="adminpass")

    def test_get_fsm_field_names(self):
        """Test that FSM fields are correctly identified."""
        field_names = self.admin.get_fsm_field_names(None, AdminArticle)
        self.assertEqual(field_names, ["state"])

    def test_fsm_field_instance_list(self):
        """Test that FSM field instances are returned."""
        fields = self.admin.fsm_field_instance_list(None, AdminArticle)
        self.assertEqual(len(fields), 1)
        self.assertEqual(fields[0].name, "state")

    def test_get_fsm_object_transitions(self):
        """Test getting available transitions for an object."""
        article = AdminArticle.objects.create(title="Test Article")
        request = self.factory.get("/")
        request.user = self.superuser

        transitions = self.admin.get_fsm_object_transitions(request, article)

        # Should have one FSMObjectTransitions for the state field
        self.assertEqual(len(transitions), 1)
        obj_trans = transitions[0]
        self.assertEqual(obj_trans.field_name, "state")
        self.assertEqual(obj_trans.current_state, "draft")

        # Should have submit transition available (reset is hidden from admin)
        trans_names = [t.name for t in obj_trans.transitions]
        self.assertIn("submit", trans_names)
        self.assertNotIn("reset", trans_names)  # custom={'admin': False}

    def test_fsm_transition_action(self):
        """Test executing a transition via admin using the client."""
        article = AdminArticle.objects.create(title="Test Article")
        url = reverse("admin:testapp_adminarticle_change", args=[article.pk])

        # Execute transition via POST
        response = self.client.post(url, {
            "_fsm_transition": "submit",
            "_fsm_field": "state",
            "title": "Test Article",
        })

        # Should redirect
        self.assertEqual(response.status_code, 302)

        # Verify state changed
        article = AdminArticle.objects.get(pk=article.pk)
        self.assertEqual(article.state, "pending")

    def test_fsm_transitions_hidden_when_admin_false(self):
        """Test that transitions with admin=False are hidden."""
        article = AdminArticle.objects.create(title="Test Article")
        request = self.factory.get("/")
        request.user = self.superuser

        transitions = self.admin.get_fsm_object_transitions(request, article)
        obj_trans = transitions[0]

        # reset has custom={'admin': False}, should not be visible
        trans_names = [t.name for t in obj_trans.transitions]
        self.assertNotIn("reset", trans_names)

    def test_change_form_template(self):
        """Test that the admin uses FSM change form template."""
        # FSMAdminMixin should set the change_form_template
        self.assertEqual(
            self.admin.change_form_template,
            "django_fsm/fsm_admin_change_form.html"
        )


class FSMAdminIntegrationTests(TestCase):
    """Integration tests for FSM admin views."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass",
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="admin", password="adminpass")
        self.article = AdminArticle.objects.create(title="Test Article")

    def test_change_view_shows_transitions(self):
        """Test that change view includes transition buttons."""
        url = reverse("admin:testapp_adminarticle_change", args=[self.article.pk])
        response = self.client.get(url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "State Transitions")
        self.assertContains(response, "Submit for Review")  # Custom label

    def test_transition_via_post(self):
        """Test executing transition via POST request."""
        url = reverse("admin:testapp_adminarticle_change", args=[self.article.pk])
        response = self.client.post(url, {
            "_fsm_transition": "submit",
            "_fsm_field": "state",
            "title": "Test Article",
        })

        # Should redirect after successful transition
        self.assertEqual(response.status_code, 302)

        # Verify state changed
        self.article = AdminArticle.objects.get(pk=self.article.pk)
        self.assertEqual(self.article.state, "pending")

    def test_transition_with_form_view(self):
        """Test that transitions with forms redirect to form view."""
        # First move to pending state
        self.article.submit()
        self.article.save()

        url = reverse("admin:testapp_adminarticle_change", args=[self.article.pk])
        response = self.client.get(url)

        # Should show publish button which links to form
        self.assertContains(response, "Publish")

    def test_invalid_transition_rejected(self):
        """Test that invalid transitions are rejected."""
        url = reverse("admin:testapp_adminarticle_change", args=[self.article.pk])
        response = self.client.post(url, {
            "_fsm_transition": "archive",  # Not valid from draft
            "_fsm_field": "state",
            "title": "Test Article",
        })

        # Should show error message but still return 200 (stays on page)
        # Note: The transition should fail gracefully
        self.assertIn(response.status_code, [200, 302])

        # State should not change
        self.article = AdminArticle.objects.get(pk=self.article.pk)
        self.assertEqual(self.article.state, "draft")


class FSMAdminForcePermitTests(TestCase):
    """Tests for FSM_ADMIN_FORCE_PERMIT setting."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass",
        )

    def setUp(self):
        self.factory = RequestFactory()
        self.site = AdminSite()
        self.admin = AdminArticleAdmin(AdminArticle, self.site)

    @override_settings(FSM_ADMIN_FORCE_PERMIT=True)
    def test_force_permit_hides_unmarked_transitions(self):
        """Test that FSM_ADMIN_FORCE_PERMIT=True hides transitions without admin=True."""
        article = AdminArticle.objects.create(title="Test Article")
        request = self.factory.get("/")
        request.user = self.superuser

        transitions = self.admin.get_fsm_object_transitions(request, article)
        obj_trans = transitions[0]

        # With FORCE_PERMIT, only transitions with custom={'admin': True} should show
        # Our test model doesn't have any with admin=True, so should be empty
        # Actually, 'submit' has custom={'label': ...} but not admin=True
        trans_names = [t.name for t in obj_trans.transitions]

        # Note: The current implementation filters based on 'admin' key
        # When FORCE_PERMIT is True, only those with admin=True are shown
        # When FORCE_PERMIT is False, all except admin=False are shown
        self.assertEqual(len(trans_names), 0)

    @override_settings(FSM_ADMIN_FORCE_PERMIT=False)
    def test_default_shows_most_transitions(self):
        """Test that default settings show transitions without admin=False."""
        article = AdminArticle.objects.create(title="Test Article")
        request = self.factory.get("/")
        request.user = self.superuser

        transitions = self.admin.get_fsm_object_transitions(request, article)
        obj_trans = transitions[0]

        trans_names = [t.name for t in obj_trans.transitions]
        # submit should be shown (has label but no admin=False)
        self.assertIn("submit", trans_names)
        # reset should NOT be shown (has admin=False)
        self.assertNotIn("reset", trans_names)


class FSMAdminTransitionFormTests(TestCase):
    """Tests for transitions that require forms."""

    @classmethod
    def setUpTestData(cls):
        cls.superuser = User.objects.create_superuser(
            username="admin",
            email="admin@example.com",
            password="adminpass",
        )

    def setUp(self):
        self.client = Client()
        self.client.login(username="admin", password="adminpass")
        self.article = AdminArticle.objects.create(title="Test Article")
        # Move to pending state
        self.article.submit()
        self.article.save()

    def test_transition_form_page_renders(self):
        """Test that the transition form page renders correctly."""
        url = reverse(
            "admin:testapp_adminarticle_fsm_transition",
            args=[self.article.pk]
        )
        response = self.client.get(url, {
            "transition": "publish",
            "field": "state",
        })

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Transition:")
        self.assertContains(response, "publish")
        self.assertContains(response, "reviewer")  # Form field

    def test_transition_form_submission(self):
        """Test submitting a transition form."""
        url = reverse(
            "admin:testapp_adminarticle_fsm_transition",
            args=[self.article.pk]
        )
        response = self.client.post(url + "?transition=publish&field=state", {
            "reviewer": "John Doe",
            "notes": "Approved after review",
        })

        # Should redirect after successful transition
        self.assertEqual(response.status_code, 302)

        # Verify state changed
        self.article = AdminArticle.objects.get(pk=self.article.pk)
        self.assertEqual(self.article.state, "published")

    def test_transition_form_validation(self):
        """Test that form validation works."""
        url = reverse(
            "admin:testapp_adminarticle_fsm_transition",
            args=[self.article.pk]
        )
        response = self.client.post(url + "?transition=publish&field=state", {
            # Missing required 'reviewer' field
            "notes": "Some notes",
        })

        # Should return to form with errors
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "required")

        # State should not change
        self.article = AdminArticle.objects.get(pk=self.article.pk)
        self.assertEqual(self.article.state, "pending")
