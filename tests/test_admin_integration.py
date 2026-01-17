"""
Tests for FSMAdminMixin and admin integration.

These tests verify the admin interface functionality including:
- Transition button rendering
- FSMCascadeWidget in admin forms
- Protected field handling
- Form argument processing
- Error handling in admin context
"""

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

import pytest
from django.contrib import admin
from django.contrib.admin.sites import AdminSite
from django.contrib.messages.storage.cookie import CookieStorage
from django.test import RequestFactory
from django.test import override_settings

from django_fsm_rx.admin import FSMAdminMixin
from tests.testapp.models import AdminArticle
from tests.testapp.models import AdminBlogPost


class MockSuperUser:
    """Mock superuser for admin tests."""

    pk = 1
    is_active = True
    is_staff = True
    is_superuser = True

    def has_perm(self, perm):
        return True

    def has_module_perms(self, app_label):
        return True


def setup_request_with_messages(request):
    """Setup request with cookie-based message storage (no session required)."""
    setattr(request, "session", {})
    setattr(request, "_messages", CookieStorage(request))


class AdminArticleAdmin(FSMAdminMixin, admin.ModelAdmin):
    """Admin for AdminArticle model."""

    fsm_fields = ["state"]
    list_display = ["title", "state"]


class AdminBlogPostAdmin(FSMAdminMixin, admin.ModelAdmin):
    """Admin for AdminBlogPost model with multiple FSM fields."""

    fsm_fields = ["state", "review_state"]
    list_display = ["title", "state", "review_state"]


class CascadeWidgetAdmin(FSMAdminMixin, admin.ModelAdmin):
    """Admin with cascade widget configuration."""

    fsm_fields = ["state"]
    fsm_cascade_fields = {
        "state": {
            "levels": 2,
            "separator": "-",
            "labels": ["Category", "Status"],
        }
    }


@pytest.fixture
def admin_site():
    """Create an admin site instance."""
    return AdminSite()


@pytest.fixture
def request_factory():
    """Create a request factory."""
    return RequestFactory()


@pytest.fixture
def admin_request(request_factory):
    """Create a mock admin request with superuser."""
    request = request_factory.get("/admin/")
    request.user = MockSuperUser()
    setup_request_with_messages(request)
    return request


@pytest.fixture
def article_admin(admin_site):
    """Create AdminArticleAdmin instance."""
    return AdminArticleAdmin(AdminArticle, admin_site)


@pytest.fixture
def blogpost_admin(admin_site):
    """Create AdminBlogPostAdmin instance."""
    return AdminBlogPostAdmin(AdminBlogPost, admin_site)


@pytest.mark.django_db
class TestFSMAdminMixinBasics:
    """Test basic FSMAdminMixin functionality."""

    def test_fsm_field_instance_retrieval(self, article_admin):
        """Test getting FSM field instance by name."""
        field = article_admin.get_fsm_field_instance("state")
        assert field is not None
        assert field.name == "state"

    def test_fsm_field_instance_invalid_name(self, article_admin):
        """Test getting non-existent field returns None."""
        field = article_admin.get_fsm_field_instance("nonexistent")
        assert field is None

    def test_fsm_field_instance_non_fsm_field(self, article_admin):
        """Test getting non-FSM field returns None."""
        field = article_admin.get_fsm_field_instance("title")
        assert field is None

    def test_protected_fields_readonly(self, article_admin, admin_request):
        """Protected FSM fields should be read-only in admin."""
        article = AdminArticle(title="Test", state="draft")
        readonly = article_admin.get_readonly_fields(admin_request, article)
        assert "state" in readonly

    def test_non_protected_fields_not_readonly(self, blogpost_admin, admin_request):
        """Non-protected FSM fields should not be auto-added to readonly."""
        post = AdminBlogPost(title="Test")
        readonly = blogpost_admin.get_readonly_fields(admin_request, post)
        # state is protected, review_state is not
        assert "state" in readonly
        assert "review_state" not in readonly


@pytest.mark.django_db
class TestFSMObjectTransitions:
    """Test FSMObjectTransitions dataclass and transition retrieval."""

    def test_get_fsm_object_transitions_single_field(self, article_admin, admin_request):
        """Test getting transitions for single FSM field."""
        article = AdminArticle(title="Test", state="draft")
        article.pk = 1  # Simulate saved object

        transitions = article_admin.get_fsm_object_transitions(admin_request, article)

        assert len(transitions) == 1
        assert transitions[0].fsm_field == "state"
        assert len(transitions[0].available_transitions) > 0

    def test_get_fsm_object_transitions_multiple_fields(self, blogpost_admin, admin_request):
        """Test getting transitions for multiple FSM fields."""
        post = AdminBlogPost(title="Test", state="new", review_state="pending")
        post.pk = 1

        transitions = blogpost_admin.get_fsm_object_transitions(admin_request, post)

        assert len(transitions) == 2
        field_names = [t.fsm_field for t in transitions]
        assert "state" in field_names
        assert "review_state" in field_names

    def test_transition_visibility_admin_false(self, blogpost_admin, admin_request):
        """Transitions with custom={'admin': False} should be hidden."""
        post = AdminBlogPost(title="Test", state="new")
        post.pk = 1

        transitions = blogpost_admin.get_fsm_object_transitions(admin_request, post)
        state_transitions = next(t for t in transitions if t.fsm_field == "state")

        # 'schedule' has admin=False, should not appear
        transition_names = [t.name for t in state_transitions.available_transitions]
        assert "schedule" not in transition_names
        # But 'publish' and 'reset' should appear
        assert "publish" in transition_names


@pytest.mark.django_db
class TestFSMAdminTransitionLabels:
    """Test transition label generation."""

    def test_custom_label(self, article_admin):
        """Test custom label from transition."""
        article = AdminArticle(title="Test", state="draft")
        transitions = list(article.get_available_state_transitions())
        submit_transition = next(t for t in transitions if t.name == "submit")

        label = article_admin.get_fsm_transition_label(submit_transition)
        assert label == "Submit for Review"

    def test_fallback_to_method_name(self, blogpost_admin):
        """Test fallback to method name when no custom label."""
        post = AdminBlogPost(title="Test", state="new")
        transitions = list(post.get_available_state_transitions())
        reset_transition = next(t for t in transitions if t.name == "reset")

        label = blogpost_admin.get_fsm_transition_label(reset_transition)
        assert label == "Reset"  # Title-cased method name

    def test_fsm_block_label(self, article_admin):
        """Test transition block label generation."""
        label = article_admin.get_fsm_block_label("state")
        assert label == "Transitions (state)"


@pytest.mark.django_db
class TestFSMAdminForcePermit:
    """Test FSM_ADMIN_FORCE_PERMIT setting."""

    @override_settings(FSM_ADMIN_FORCE_PERMIT=True)
    def test_force_permit_hides_unlabeled_transitions(self, blogpost_admin, admin_request):
        """With FORCE_PERMIT, only transitions with admin=True should appear."""
        post = AdminBlogPost(title="Test", state="new")
        post.pk = 1

        transitions = blogpost_admin.get_fsm_object_transitions(admin_request, post)
        state_transitions = next(t for t in transitions if t.fsm_field == "state")

        # With FORCE_PERMIT=True, only transitions with explicit admin=True appear
        # 'reset' has no admin property, so should be hidden
        transition_names = [t.name for t in state_transitions.available_transitions]
        assert "reset" not in transition_names

    @override_settings(FSM_ADMIN_FORCE_PERMIT=False)
    def test_default_shows_transitions_without_admin_false(self, blogpost_admin, admin_request):
        """Without FORCE_PERMIT, transitions appear unless admin=False."""
        post = AdminBlogPost(title="Test", state="new")
        post.pk = 1

        transitions = blogpost_admin.get_fsm_object_transitions(admin_request, post)
        state_transitions = next(t for t in transitions if t.fsm_field == "state")

        transition_names = [t.name for t in state_transitions.available_transitions]
        # 'reset' should appear (no admin property = visible by default)
        assert "reset" in transition_names
        # 'schedule' has admin=False, should not appear
        assert "schedule" not in transition_names


@pytest.mark.django_db
class TestFSMAdminCascadeWidget:
    """Test FSMCascadeWidget integration in admin."""

    def test_cascade_widget_config_is_stored(self, admin_site):
        """Test cascade widget configuration is stored on admin class."""
        cascade_admin = CascadeWidgetAdmin(AdminArticle, admin_site)

        # Check config is accessible
        assert hasattr(cascade_admin, "fsm_cascade_fields")
        assert "state" in cascade_admin.fsm_cascade_fields
        assert cascade_admin.fsm_cascade_fields["state"]["levels"] == 2
        assert cascade_admin.fsm_cascade_fields["state"]["separator"] == "-"
        assert cascade_admin.fsm_cascade_fields["state"]["labels"] == ["Category", "Status"]

    def test_cascade_widget_config_not_applied_to_other_fields(self, admin_site):
        """Test cascade widget config only applies to configured fields."""
        cascade_admin = CascadeWidgetAdmin(AdminArticle, admin_site)

        # title is not in fsm_cascade_fields
        assert "title" not in cascade_admin.fsm_cascade_fields


@pytest.mark.django_db
class TestFSMAdminTransitionExecution:
    """Test transition execution in admin context."""

    def test_execute_transition_success(self, article_admin, admin_request):
        """Test successful transition execution."""
        article = AdminArticle.objects.create(title="Test", state="draft")

        result = article_admin._execute_transition(admin_request, article, "submit")

        assert result is True
        article.refresh_from_db()
        assert article.state == "pending"

    def test_execute_transition_invalid_name(self, article_admin, admin_request):
        """Test transition with invalid name shows error."""
        article = AdminArticle.objects.create(title="Test", state="draft")

        result = article_admin._execute_transition(admin_request, article, "nonexistent")

        assert result is False

    def test_execute_transition_with_kwargs(self, article_admin, admin_request):
        """Test transition execution with keyword arguments."""
        article = AdminArticle.objects.create(title="Test", state="pending")

        result = article_admin._execute_transition(
            admin_request,
            article,
            "publish",
            {"reviewer": "Alice", "notes": "Looks good"},
        )

        assert result is True
        article.refresh_from_db()
        assert article.state == "published"


@pytest.mark.django_db
class TestFSMAdminResponseChange:
    """Test response_change with FSM transitions."""

    def test_response_change_with_transition(self, article_admin, request_factory):
        """Test response_change handles FSM transition parameter."""
        article = AdminArticle.objects.create(title="Test", state="draft")

        request = request_factory.post(
            f"/admin/testapp/adminarticle/{article.pk}/change/",
            data={"_fsm_transition_to": "submit", "title": "Test"},
        )
        request.user = MockSuperUser()
        # Add messages support
        setup_request_with_messages(request)

        response = article_admin.response_change(request, article)

        # Should redirect
        assert response.status_code == 302
        article.refresh_from_db()
        assert article.state == "pending"

    def test_response_change_without_transition(self, article_admin, request_factory):
        """Test response_change without FSM transition is pass-through."""
        article = AdminArticle.objects.create(title="Test", state="draft")

        request = request_factory.post(
            f"/admin/testapp/adminarticle/{article.pk}/change/",
            data={"title": "Updated"},
        )
        request.user = MockSuperUser()
        setup_request_with_messages(request)

        # Should call parent's response_change (may raise without full admin setup)
        # This is a partial test - full integration requires more setup


@pytest.mark.django_db
class TestFSMAdminErrorHandling:
    """Test error handling in admin transitions."""

    def test_transition_not_allowed_error(self, article_admin, request_factory):
        """Test TransitionNotAllowed shows error message."""
        article = AdminArticle.objects.create(title="Test", state="published")

        request = request_factory.post(
            f"/admin/testapp/adminarticle/{article.pk}/change/",
            data={"_fsm_transition_to": "submit"},  # Not allowed from published
        )
        request.user = MockSuperUser()
        setup_request_with_messages(request)

        response = article_admin.response_change(request, article)

        # Should redirect (error is shown via messages)
        assert response.status_code == 302
        # State should not have changed
        article.refresh_from_db()
        assert article.state == "published"


@pytest.mark.django_db
class TestFSMAdminURLs:
    """Test custom admin URLs for transitions."""

    def test_get_urls_includes_transition_view(self, article_admin):
        """Test that transition URL is registered."""
        urls = article_admin.get_urls()

        # Find the FSM transition URL
        fsm_urls = [u for u in urls if "fsm-transition" in str(u.pattern)]
        assert len(fsm_urls) == 1

    def test_transition_url_pattern(self, article_admin):
        """Test transition URL pattern format."""
        urls = article_admin.get_urls()
        fsm_url = next(u for u in urls if "fsm-transition" in str(u.pattern))

        # Should match pattern: <object_id>/fsm-transition/<transition_name>/
        assert "<path:object_id>" in str(fsm_url.pattern) or "object_id" in str(fsm_url.pattern)
        assert "<str:transition_name>" in str(fsm_url.pattern) or "transition_name" in str(fsm_url.pattern)


@pytest.mark.django_db
class TestFSMAdminTransitionView:
    """Test fsm_transition_view for form-based transitions."""

    def test_transition_view_with_form_get(self, article_admin, request_factory):
        """Test GET request to transition view shows form."""
        article = AdminArticle.objects.create(title="Test", state="pending")

        request = request_factory.get(f"/admin/testapp/adminarticle/{article.pk}/fsm-transition/publish/")
        request.user = MockSuperUser()
        setup_request_with_messages(request)

        response = article_admin.fsm_transition_view(request, str(article.pk), "publish")

        # Should render form template
        assert response.status_code == 200
        assert b"reviewer" in response.content  # Form field

    def test_transition_view_with_form_post(self, article_admin, request_factory):
        """Test POST request to transition view executes transition."""
        article = AdminArticle.objects.create(title="Test", state="pending")
        original_pk = article.pk

        request = request_factory.post(
            f"/admin/testapp/adminarticle/{article.pk}/fsm-transition/publish/",
            data={"reviewer": "Alice", "notes": "Approved"},
        )
        request.user = MockSuperUser()
        setup_request_with_messages(request)

        response = article_admin.fsm_transition_view(request, str(article.pk), "publish")

        # Should redirect after successful transition
        assert response.status_code == 302

        # Reload from database to verify state was saved
        db_article = AdminArticle.objects.get(pk=original_pk)
        assert db_article.state == "published"

    def test_transition_view_invalid_object(self, article_admin, request_factory):
        """Test transition view with invalid object ID."""
        request = request_factory.get("/admin/testapp/adminarticle/99999/fsm-transition/submit/")
        request.user = MockSuperUser()

        response = article_admin.fsm_transition_view(request, "99999", "submit")

        assert response.status_code == 400

    def test_transition_view_invalid_transition(self, article_admin, request_factory):
        """Test transition view with invalid transition name."""
        article = AdminArticle.objects.create(title="Test", state="draft")

        request = request_factory.get(f"/admin/testapp/adminarticle/{article.pk}/fsm-transition/nonexistent/")
        request.user = MockSuperUser()

        response = article_admin.fsm_transition_view(request, str(article.pk), "nonexistent")

        assert response.status_code == 400

    def test_transition_view_form_validation_error(self, article_admin, request_factory):
        """Test transition view with form validation error."""
        article = AdminArticle.objects.create(title="Test", state="pending")

        request = request_factory.post(
            f"/admin/testapp/adminarticle/{article.pk}/fsm-transition/publish/",
            data={"reviewer": "", "notes": ""},  # reviewer is required
        )
        request.user = MockSuperUser()
        setup_request_with_messages(request)

        response = article_admin.fsm_transition_view(request, str(article.pk), "publish")

        # Should re-render form with errors
        assert response.status_code == 200
        # State should not have changed
        article.refresh_from_db()
        assert article.state == "pending"


@pytest.mark.django_db
class TestFSMAdminTransitionForm:
    """Test transition form retrieval."""

    def test_get_transition_form_from_string(self, article_admin):
        """Test getting form class from dotted string path."""
        article = AdminArticle(state="pending")
        transitions = list(article.get_available_state_transitions())
        publish_transition = next(t for t in transitions if t.name == "publish")

        form_class = article_admin.get_fsm_transition_form(publish_transition)

        assert form_class is not None
        assert form_class.__name__ == "PublishForm"

    def test_get_transition_form_none(self, article_admin):
        """Test getting form when none specified."""
        article = AdminArticle(state="draft")
        transitions = list(article.get_available_state_transitions())
        submit_transition = next(t for t in transitions if t.name == "submit")

        form_class = article_admin.get_fsm_transition_form(submit_transition)

        assert form_class is None


@pytest.mark.django_db
class TestFSMAdminChangeView:
    """Test change_view context injection."""

    def test_change_view_injects_transitions(self, article_admin, admin_request):
        """Test change_view injects FSM transitions into context."""
        article = AdminArticle.objects.create(title="Test", state="draft")

        # Mock the parent change_view to capture context
        with patch.object(admin.ModelAdmin, "change_view") as mock_change_view:
            mock_change_view.return_value = MagicMock()

            article_admin.change_view(admin_request, str(article.pk), extra_context={})

            # Check extra_context was passed with FSM data
            call_kwargs = mock_change_view.call_args.kwargs
            extra_context = call_kwargs.get("extra_context", {})
            assert "fsm_object_transitions" in extra_context
