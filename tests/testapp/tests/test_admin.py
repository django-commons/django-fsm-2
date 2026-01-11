from __future__ import annotations

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import User
from django.test import Client
from django.test import RequestFactory
from django.urls import reverse

from django_fsm_2.admin import FSMAdminMixin
from django_fsm_2.admin import FSMObjectTransitions
from tests.testapp.admin import AdminBlogPostAdmin
from tests.testapp.models import AdminBlogPost


@pytest.fixture
def admin_user(db):
    """Create an admin user."""
    return User.objects.create_superuser(
        username="admin",
        email="admin@example.com",
        password="password",
    )


@pytest.fixture
def regular_user(db):
    """Create a regular user."""
    return User.objects.create_user(
        username="user",
        email="user@example.com",
        password="password",
    )


@pytest.fixture
def admin_site():
    """Create an admin site."""
    return AdminSite()


@pytest.fixture
def model_admin(admin_site):
    """Create the model admin."""
    return AdminBlogPostAdmin(AdminBlogPost, admin_site)


@pytest.fixture
def blog_post(db):
    """Create a test blog post."""
    return AdminBlogPost.objects.create(title="Test Post")


@pytest.fixture
def request_factory():
    """Create a request factory."""
    return RequestFactory()


@pytest.fixture
def client():
    """Create a test client."""
    return Client()


class TestFSMAdminMixin:
    """Tests for FSMAdminMixin."""

    def test_get_fsm_field_instance(self, model_admin):
        """Test getting FSM field instance by name."""
        field = model_admin.get_fsm_field_instance("state")
        assert field is not None
        assert field.name == "state"

        # Non-FSM field should return None
        non_field = model_admin.get_fsm_field_instance("title")
        assert non_field is None

        # Non-existent field should return None
        missing = model_admin.get_fsm_field_instance("nonexistent")
        assert missing is None

    def test_get_readonly_fields_includes_protected(
        self, model_admin, request_factory, admin_user
    ):
        """Test that protected FSM fields are added to readonly fields."""
        request = request_factory.get("/")
        request.user = admin_user

        readonly = model_admin.get_readonly_fields(request)

        # state is protected, should be in readonly
        assert "state" in readonly

    def test_get_fsm_block_label(self, model_admin):
        """Test getting transition block label."""
        label = model_admin.get_fsm_block_label("state")
        assert label == "Transitions (state)"

    def test_get_fsm_transition_label_custom(self, model_admin, blog_post):
        """Test getting transition label from custom property."""
        # Get the publish transition which has a custom label
        transitions = list(blog_post.get_available_state_transitions())
        publish_transition = next(t for t in transitions if t.name == "publish")

        label = model_admin.get_fsm_transition_label(publish_transition)
        assert label == "Publish Post"

    def test_get_fsm_transition_label_default(self, model_admin, blog_post):
        """Test getting transition label without custom property."""
        # Get the reset transition which has no custom label
        transitions = list(blog_post.get_available_state_transitions())
        reset_transition = next(t for t in transitions if t.name == "reset")

        label = model_admin.get_fsm_transition_label(reset_transition)
        assert label == "Reset"

    def test_is_fsm_transition_visible_default(self, model_admin, blog_post):
        """Test transition visibility default."""
        transitions = list(blog_post.get_available_state_transitions())
        publish_transition = next(t for t in transitions if t.name == "publish")

        assert model_admin.is_fsm_transition_visible(publish_transition) is True

    def test_is_fsm_transition_visible_hidden(self, model_admin, blog_post):
        """Test transition hidden via admin=False."""
        transitions = list(blog_post.get_all_state_transitions())
        schedule_transition = next(t for t in transitions if t.name == "schedule")

        assert model_admin.is_fsm_transition_visible(schedule_transition) is False

    def test_get_fsm_object_transitions(
        self, model_admin, blog_post, request_factory, admin_user
    ):
        """Test getting object transitions."""
        request = request_factory.get("/")
        request.user = admin_user

        transitions = model_admin.get_fsm_object_transitions(request, blog_post)

        assert len(transitions) == 2  # state and review_state
        assert all(isinstance(t, FSMObjectTransitions) for t in transitions)

        # Find state transitions
        state_transitions = next(t for t in transitions if t.fsm_field == "state")
        assert state_transitions.block_label == "Transitions (state)"

        # publish and reset should be visible, schedule should not
        transition_names = [t.name for t in state_transitions.available_transitions]
        assert "publish" in transition_names
        assert "reset" in transition_names
        assert "schedule" not in transition_names

    def test_get_fsm_transition_form(self, model_admin, blog_post):
        """Test getting form for transition with arguments."""
        # Get the reject transition which has a form
        transitions = list(blog_post.get_available_review_state_transitions())
        reject_transition = next(t for t in transitions if t.name == "reject")

        form_class = model_admin.get_fsm_transition_form(reject_transition)
        assert form_class is not None
        assert form_class.__name__ == "RejectionForm"

        # publish has no form
        state_transitions = list(blog_post.get_available_state_transitions())
        publish_transition = next(t for t in state_transitions if t.name == "publish")
        assert model_admin.get_fsm_transition_form(publish_transition) is None


@pytest.mark.django_db
class TestAdminIntegration:
    """Integration tests for admin interface."""

    def test_admin_change_view(self, client, admin_user, blog_post):
        """Test that change view renders with FSM transitions."""
        client.force_login(admin_user)

        url = reverse("admin:testapp_adminblogpost_change", args=[blog_post.pk])
        response = client.get(url)

        assert response.status_code == 200
        assert b"fsm_object_transitions" in response.content or b"Transitions" in response.content

    def test_admin_inline_transition(self, client, admin_user, blog_post):
        """Test inline transition via POST."""
        from tests.testapp.models import AdminBlogPost

        client.force_login(admin_user)

        url = reverse("admin:testapp_adminblogpost_change", args=[blog_post.pk])

        response = client.post(
            url,
            {
                "title": blog_post.title,
                "review_state": "pending",  # non-protected field, required
                "_fsm_transition_to": "publish",
            },
        )

        # Should redirect after transition
        assert response.status_code == 302

        # State should have changed - get fresh from DB since
        # refresh_from_db() skips protected FSM fields by design
        db_post = AdminBlogPost.objects.get(pk=blog_post.pk)
        assert db_post.state == "published"

    def test_admin_transition_view_get(self, client, admin_user, blog_post):
        """Test transition form view GET request."""
        client.force_login(admin_user)

        url = reverse(
            "admin:testapp_adminblogpost_fsm_transition",
            args=[blog_post.pk, "reject"],
        )
        response = client.get(url)

        assert response.status_code == 200
        assert b"reason" in response.content  # Form field

    def test_admin_transition_view_post(self, client, admin_user, blog_post):
        """Test transition form view POST request."""
        client.force_login(admin_user)

        url = reverse(
            "admin:testapp_adminblogpost_fsm_transition",
            args=[blog_post.pk, "reject"],
        )
        response = client.post(url, {"reason": "Not good enough"})

        # Should redirect after transition
        assert response.status_code == 302

        # State should have changed
        blog_post.refresh_from_db()
        assert blog_post.review_state == "rejected"

    def test_admin_transition_view_invalid_transition(
        self, client, admin_user, blog_post
    ):
        """Test transition view with invalid transition name."""
        client.force_login(admin_user)

        url = reverse(
            "admin:testapp_adminblogpost_fsm_transition",
            args=[blog_post.pk, "invalid_transition"],
        )
        response = client.get(url)

        assert response.status_code == 400

    def test_admin_transition_not_allowed(self, client, admin_user, blog_post):
        """Test transition that is not allowed from current state."""
        client.force_login(admin_user)

        # archive is only available from 'published', not 'new'
        url = reverse("admin:testapp_adminblogpost_change", args=[blog_post.pk])
        response = client.post(
            url,
            {
                "title": blog_post.title,
                "review_state": "pending",
                "_fsm_transition_to": "archive",
            },
        )

        # Should redirect with error message
        assert response.status_code == 302

        # State should NOT have changed - get fresh from DB
        from tests.testapp.models import AdminBlogPost
        db_post = AdminBlogPost.objects.get(pk=blog_post.pk)
        assert db_post.state == "new"


@pytest.mark.django_db
class TestFSMLogIntegration:
    """Test FSM log decorator integration."""

    def test_fsm_log_by_decorator(self, admin_user):
        """Test that fsm_log_by decorator works."""
        from django_fsm_2.log import fsm_log_by

        class MockModel:
            def __init__(self):
                self._fsm_log_by = None

            @fsm_log_by
            def do_transition(self, by=None):
                # Check that _fsm_log_by was set during the call
                return getattr(self, "_fsm_log_by", None)

        obj = MockModel()
        result = obj.do_transition(by=admin_user)
        assert result == admin_user

        # Should be cleaned up after the call
        assert not hasattr(obj, "_fsm_log_by")

    def test_fsm_log_description_decorator(self):
        """Test that fsm_log_description decorator works."""
        from django_fsm_2.log import fsm_log_description

        class MockModel:
            @fsm_log_description
            def do_transition(self, description=None):
                return getattr(self, "_fsm_log_description", None)

        obj = MockModel()
        result = obj.do_transition(description="Test description")
        assert result == "Test description"

    def test_fsm_log_context_manager(self, admin_user):
        """Test fsm_log_context context manager."""
        from django_fsm_2.log import fsm_log_context

        class MockModel:
            pass

        obj = MockModel()

        with fsm_log_context(obj, by=admin_user, description="Test"):
            assert obj._fsm_log_by == admin_user
            assert obj._fsm_log_description == "Test"

        # Should be cleaned up after context
        assert not hasattr(obj, "_fsm_log_by")
        assert not hasattr(obj, "_fsm_log_description")
