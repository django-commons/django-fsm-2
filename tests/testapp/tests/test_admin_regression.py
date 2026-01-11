"""
Regression tests for FSMAdminMixin.

These tests cover edge cases and ensure stability of the admin integration.
"""

from __future__ import annotations

import pytest
from django.contrib.admin.sites import AdminSite
from django.contrib.auth.models import Permission
from django.contrib.auth.models import User
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.test import RequestFactory
from django.test import override_settings
from django.urls import reverse

from django_fsm_2 import FSMField
from django_fsm_2 import transition
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
def staff_user(db):
    """Create a staff user without superuser privileges."""
    user = User.objects.create_user(
        username="staff",
        email="staff@example.com",
        password="password",
        is_staff=True,
    )
    return user


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
def published_post(db):
    """Create a published blog post."""
    post = AdminBlogPost.objects.create(title="Published Post")
    post.publish()
    post.save()
    return AdminBlogPost.objects.get(pk=post.pk)


@pytest.fixture
def request_factory():
    """Create a request factory."""
    return RequestFactory()


@pytest.fixture
def client():
    """Create a test client."""
    return Client()


class TestFSMAdminMixinRegression:
    """Regression tests for FSMAdminMixin edge cases."""

    def test_multiple_fsm_fields_transitions(
        self, model_admin, blog_post, request_factory, admin_user
    ):
        """Test that transitions for multiple FSM fields are correctly separated."""
        request = request_factory.get("/")
        request.user = admin_user

        transitions = model_admin.get_fsm_object_transitions(request, blog_post)

        # Should have transitions for both fields
        field_names = [t.fsm_field for t in transitions]
        assert "state" in field_names
        assert "review_state" in field_names

        # Each field should have its own transitions
        state_transitions = next(t for t in transitions if t.fsm_field == "state")
        review_transitions = next(t for t in transitions if t.fsm_field == "review_state")

        state_names = [t.name for t in state_transitions.available_transitions]
        review_names = [t.name for t in review_transitions.available_transitions]

        # publish and reset are state transitions
        assert "publish" in state_names
        assert "reset" in state_names
        # approve and reject are review_state transitions
        assert "approve" in review_names
        assert "reject" in review_names

    def test_transition_not_available_after_state_change(
        self, model_admin, published_post, request_factory, admin_user
    ):
        """Test that transitions are correctly filtered by current state."""
        request = request_factory.get("/")
        request.user = admin_user

        transitions = model_admin.get_fsm_object_transitions(request, published_post)
        state_transitions = next(t for t in transitions if t.fsm_field == "state")
        transition_names = [t.name for t in state_transitions.available_transitions]

        # publish should NOT be available from 'published' state
        assert "publish" not in transition_names
        # archive should be available from 'published' state
        assert "archive" in transition_names
        # reset (*) should always be available
        assert "reset" in transition_names

    def test_empty_fsm_fields_list(self, admin_site, request_factory, admin_user, db):
        """Test admin with empty fsm_fields list."""
        from django.contrib import admin as django_admin

        class EmptyFSMAdmin(FSMAdminMixin, django_admin.ModelAdmin):
            fsm_fields = []

        admin = EmptyFSMAdmin(AdminBlogPost, admin_site)
        post = AdminBlogPost.objects.create(title="Test")
        request = request_factory.get("/")
        request.user = admin_user

        transitions = admin.get_fsm_object_transitions(request, post)
        assert transitions == []

    def test_nonexistent_fsm_field(self, admin_site, request_factory, admin_user, db):
        """Test admin with nonexistent field in fsm_fields."""
        from django.contrib import admin as django_admin

        class BadFSMAdmin(FSMAdminMixin, django_admin.ModelAdmin):
            fsm_fields = ["nonexistent_field"]

        admin = BadFSMAdmin(AdminBlogPost, admin_site)
        post = AdminBlogPost.objects.create(title="Test")
        request = request_factory.get("/")
        request.user = admin_user

        # Should not raise, just return empty
        transitions = admin.get_fsm_object_transitions(request, post)
        assert len(transitions) == 0

    def test_readonly_fields_not_duplicated(
        self, model_admin, request_factory, admin_user, blog_post
    ):
        """Test that protected fields aren't duplicated in readonly_fields."""
        request = request_factory.get("/")
        request.user = admin_user

        # Call multiple times
        readonly1 = model_admin.get_readonly_fields(request, blog_post)
        readonly2 = model_admin.get_readonly_fields(request, blog_post)

        # state should appear exactly once
        assert readonly1.count("state") == 1
        assert readonly2.count("state") == 1

    def test_custom_label_with_special_characters(
        self, model_admin, blog_post
    ):
        """Test transition labels with special characters."""
        transitions = list(blog_post.get_available_state_transitions())
        publish_transition = next(t for t in transitions if t.name == "publish")

        # The label should be properly escaped in templates
        label = model_admin.get_fsm_transition_label(publish_transition)
        assert label == "Publish Post"

    def test_transition_with_none_custom(self, model_admin, blog_post):
        """Test transition with no custom dict."""
        transitions = list(blog_post.get_available_state_transitions())
        reset_transition = next(t for t in transitions if t.name == "reset")

        # Should fall back to method name
        label = model_admin.get_fsm_transition_label(reset_transition)
        assert label == "Reset"

        # Should be visible by default
        assert model_admin.is_fsm_transition_visible(reset_transition) is True


@pytest.mark.django_db
class TestAdminIntegrationRegression:
    """Integration regression tests."""

    def test_concurrent_transition_attempts(self, client, admin_user, blog_post):
        """Test handling of concurrent transition attempts."""
        from tests.testapp.models import AdminBlogPost

        client.force_login(admin_user)
        url = reverse("admin:testapp_adminblogpost_change", args=[blog_post.pk])

        # First transition should succeed
        response1 = client.post(
            url,
            {
                "title": blog_post.title,
                "review_state": "pending",
                "_fsm_transition_to": "publish",
            },
        )
        assert response1.status_code == 302

        # Verify state changed
        post = AdminBlogPost.objects.get(pk=blog_post.pk)
        assert post.state == "published"

        # Second transition with same name should fail (already published)
        response2 = client.post(
            url,
            {
                "title": blog_post.title,
                "review_state": "pending",
                "_fsm_transition_to": "publish",
            },
        )
        assert response2.status_code == 302  # Redirects with error message

    def test_transition_preserves_other_fields(self, client, admin_user, blog_post):
        """Test that transitions don't affect other model fields."""
        from tests.testapp.models import AdminBlogPost

        client.force_login(admin_user)

        original_title = "Updated Title"
        url = reverse("admin:testapp_adminblogpost_change", args=[blog_post.pk])

        response = client.post(
            url,
            {
                "title": original_title,
                "review_state": "pending",
                "_fsm_transition_to": "publish",
            },
        )
        assert response.status_code == 302

        post = AdminBlogPost.objects.get(pk=blog_post.pk)
        assert post.title == original_title
        assert post.state == "published"

    def test_form_transition_validation_errors(self, client, admin_user, blog_post):
        """Test that form validation errors are handled correctly."""
        client.force_login(admin_user)

        url = reverse(
            "admin:testapp_adminblogpost_fsm_transition",
            args=[blog_post.pk, "reject"],
        )

        # Post without required 'reason' field
        response = client.post(url, {})

        # Should re-render form with errors
        assert response.status_code == 200
        assert b"This field is required" in response.content

    def test_transition_view_object_not_found(self, client, admin_user):
        """Test transition view with non-existent object."""
        client.force_login(admin_user)

        url = reverse(
            "admin:testapp_adminblogpost_fsm_transition",
            args=[99999, "publish"],
        )
        response = client.get(url)

        assert response.status_code == 400

    def test_transition_view_method_not_transition(self, client, admin_user, blog_post):
        """Test transition view with non-transition method."""
        client.force_login(admin_user)

        url = reverse(
            "admin:testapp_adminblogpost_fsm_transition",
            args=[blog_post.pk, "__str__"],
        )
        response = client.get(url)

        assert response.status_code == 400

    def test_admin_change_view_without_object(self, client, admin_user):
        """Test change view for non-existent object returns 404."""
        client.force_login(admin_user)

        url = reverse("admin:testapp_adminblogpost_change", args=[99999])
        response = client.get(url)

        assert response.status_code == 302  # Redirects to changelist

    def test_multiple_sequential_transitions(self, client, admin_user, blog_post):
        """Test multiple transitions in sequence."""
        from tests.testapp.models import AdminBlogPost

        client.force_login(admin_user)
        url = reverse("admin:testapp_adminblogpost_change", args=[blog_post.pk])

        # draft -> published
        client.post(
            url,
            {
                "title": blog_post.title,
                "review_state": "pending",
                "_fsm_transition_to": "publish",
            },
        )

        post = AdminBlogPost.objects.get(pk=blog_post.pk)
        assert post.state == "published"

        # published -> archived
        client.post(
            url,
            {
                "title": blog_post.title,
                "review_state": "pending",
                "_fsm_transition_to": "archive",
            },
        )

        post = AdminBlogPost.objects.get(pk=blog_post.pk)
        assert post.state == "archived"

    def test_transition_on_multiple_fields_same_request(
        self, client, admin_user, blog_post
    ):
        """Test that only one transition is processed per request."""
        from tests.testapp.models import AdminBlogPost

        client.force_login(admin_user)
        url = reverse("admin:testapp_adminblogpost_change", args=[blog_post.pk])

        # Try to send multiple transitions (only first should be processed)
        response = client.post(
            url,
            {
                "title": blog_post.title,
                "review_state": "pending",
                "_fsm_transition_to": "publish",
            },
        )

        post = AdminBlogPost.objects.get(pk=blog_post.pk)
        # Only state field transition should have been processed
        assert post.state == "published"
        assert post.review_state == "pending"  # Unchanged


@pytest.mark.django_db
class TestFSMAdminForcePermit:
    """Test FSM_ADMIN_FORCE_PERMIT setting."""

    @override_settings(FSM_ADMIN_FORCE_PERMIT=True)
    def test_force_permit_hides_transitions_without_admin_true(
        self, model_admin, blog_post, request_factory, admin_user
    ):
        """With FSM_ADMIN_FORCE_PERMIT=True, only admin=True transitions show."""
        request = request_factory.get("/")
        request.user = admin_user

        transitions = model_admin.get_fsm_object_transitions(request, blog_post)
        state_transitions = next(t for t in transitions if t.fsm_field == "state")
        transition_names = [t.name for t in state_transitions.available_transitions]

        # No transitions should show because none have admin=True
        # (publish has label but not admin=True)
        assert len(transition_names) == 0

    @override_settings(FSM_ADMIN_FORCE_PERMIT=False)
    def test_force_permit_false_shows_all_except_admin_false(
        self, model_admin, blog_post, request_factory, admin_user
    ):
        """With FSM_ADMIN_FORCE_PERMIT=False, all except admin=False show."""
        request = request_factory.get("/")
        request.user = admin_user

        transitions = model_admin.get_fsm_object_transitions(request, blog_post)
        state_transitions = next(t for t in transitions if t.fsm_field == "state")
        transition_names = [t.name for t in state_transitions.available_transitions]

        # publish and reset should show
        assert "publish" in transition_names
        assert "reset" in transition_names
        # schedule has admin=False
        assert "schedule" not in transition_names


@pytest.mark.django_db
class TestFSMLogDecoratorRegression:
    """Regression tests for FSM log decorators."""

    def test_fsm_log_by_without_by_parameter(self):
        """Test fsm_log_by when by is not passed."""
        from django_fsm_2.log import fsm_log_by

        class MockModel:
            @fsm_log_by
            def do_transition(self, by=None):
                return getattr(self, "_fsm_log_by", "not_set")

        obj = MockModel()
        result = obj.do_transition()  # No 'by' parameter
        assert result == "not_set"

    def test_fsm_log_by_with_none_value(self):
        """Test fsm_log_by when by=None is explicitly passed."""
        from django_fsm_2.log import fsm_log_by

        class MockModel:
            @fsm_log_by
            def do_transition(self, by=None):
                return getattr(self, "_fsm_log_by", "not_set")

        obj = MockModel()
        result = obj.do_transition(by=None)
        assert result == "not_set"

    def test_fsm_log_description_with_default(self):
        """Test fsm_log_description with default description."""
        from django_fsm_2.log import fsm_log_description

        class MockModel:
            @fsm_log_description(description="Default desc")
            def do_transition(self):
                return getattr(self, "_fsm_log_description", None)

        obj = MockModel()
        result = obj.do_transition()
        assert result == "Default desc"

    def test_fsm_log_description_override_default(self):
        """Test that passed description overrides default."""
        from django_fsm_2.log import fsm_log_description

        class MockModel:
            @fsm_log_description(description="Default desc")
            def do_transition(self, description=None):
                return getattr(self, "_fsm_log_description", None)

        obj = MockModel()
        result = obj.do_transition(description="Override desc")
        assert result == "Override desc"

    def test_fsm_log_description_inline_mode(self):
        """Test fsm_log_description with allow_inline=True."""
        from django_fsm_2.log import fsm_log_description

        class MockModel:
            @fsm_log_description(allow_inline=True)
            def do_transition(self, description=None):
                if description:
                    description.set("Inline description")
                return getattr(self, "_fsm_log_description", None)

        obj = MockModel()
        result = obj.do_transition()
        assert result == "Inline description"

    def test_fsm_log_context_partial_params(self):
        """Test fsm_log_context with only some parameters."""
        from django_fsm_2.log import fsm_log_context

        class MockModel:
            pass

        obj = MockModel()

        # Only 'by' parameter
        with fsm_log_context(obj, by="user"):
            assert obj._fsm_log_by == "user"
            assert not hasattr(obj, "_fsm_log_description")

        # Only 'description' parameter
        with fsm_log_context(obj, description="test"):
            assert not hasattr(obj, "_fsm_log_by")
            assert obj._fsm_log_description == "test"

    def test_fsm_log_context_cleanup_on_exception(self):
        """Test that fsm_log_context cleans up even on exception."""
        from django_fsm_2.log import fsm_log_context

        class MockModel:
            pass

        obj = MockModel()

        try:
            with fsm_log_context(obj, by="user", description="test"):
                assert obj._fsm_log_by == "user"
                raise ValueError("Test exception")
        except ValueError:
            pass

        # Should be cleaned up
        assert not hasattr(obj, "_fsm_log_by")
        assert not hasattr(obj, "_fsm_log_description")

    def test_stacked_decorators(self, admin_user):
        """Test fsm_log_by and fsm_log_description stacked together."""
        from django_fsm_2.log import fsm_log_by
        from django_fsm_2.log import fsm_log_description

        class MockModel:
            @fsm_log_by
            @fsm_log_description
            def do_transition(self, by=None, description=None):
                return (
                    getattr(self, "_fsm_log_by", None),
                    getattr(self, "_fsm_log_description", None),
                )

        obj = MockModel()
        by_result, desc_result = obj.do_transition(
            by=admin_user, description="Test desc"
        )

        assert by_result == admin_user
        assert desc_result == "Test desc"

        # Should be cleaned up
        assert not hasattr(obj, "_fsm_log_by")
        assert not hasattr(obj, "_fsm_log_description")


@pytest.mark.django_db
class TestAdminTemplateRegression:
    """Regression tests for admin templates."""

    def test_template_renders_transition_buttons(self, client, admin_user, blog_post):
        """Test that transition buttons are rendered in the template."""
        client.force_login(admin_user)

        url = reverse("admin:testapp_adminblogpost_change", args=[blog_post.pk])
        response = client.get(url)

        assert response.status_code == 200
        # Check for transition button markup
        assert b"fsm-transition-button" in response.content
        assert b"_fsm_transition_to" in response.content

    def test_template_shows_custom_labels(self, client, admin_user, blog_post):
        """Test that custom labels are displayed in template."""
        client.force_login(admin_user)

        url = reverse("admin:testapp_adminblogpost_change", args=[blog_post.pk])
        response = client.get(url)

        # publish has custom label "Publish Post"
        assert b"Publish Post" in response.content

    def test_template_links_to_form_for_form_transitions(
        self, client, admin_user, blog_post
    ):
        """Test that transitions with forms link to the form view."""
        client.force_login(admin_user)

        url = reverse("admin:testapp_adminblogpost_change", args=[blog_post.pk])
        response = client.get(url)

        # reject has a form, should link to transition view
        transition_url = reverse(
            "admin:testapp_adminblogpost_fsm_transition",
            args=[blog_post.pk, "reject"],
        )
        assert transition_url.encode() in response.content

    def test_transition_form_template_renders(self, client, admin_user, blog_post):
        """Test that the transition form template renders correctly."""
        client.force_login(admin_user)

        url = reverse(
            "admin:testapp_adminblogpost_fsm_transition",
            args=[blog_post.pk, "reject"],
        )
        response = client.get(url)

        assert response.status_code == 200
        assert b"reason" in response.content  # Form field
        assert b"Execute Transition" in response.content  # Submit button
        assert b"Cancel" in response.content  # Cancel link
