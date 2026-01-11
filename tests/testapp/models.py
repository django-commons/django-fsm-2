from __future__ import annotations

from django import forms
from django.db import models

from django_fsm_2 import GET_STATE
from django_fsm_2 import RETURN_VALUE
from django_fsm_2 import FSMField
from django_fsm_2 import FSMKeyField
from django_fsm_2 import FSMModelMixin
from django_fsm_2 import transition
from django_fsm_2.log import fsm_log_by
from django_fsm_2.log import fsm_log_description


class Application(models.Model):
    """
    Student application need to be approved by dept chair and dean.
    Test workflow
    """

    state = FSMField(default="new")

    @transition(field=state, source="new", target="published")
    def standard(self):
        pass

    @transition(field=state, source="published")
    def no_target(self):
        pass

    @transition(field=state, source="*", target="blocked")
    def any_source(self):
        pass

    @transition(field=state, source="+", target="hidden")
    def any_source_except_target(self):
        pass

    @transition(
        field=state,
        source="new",
        target=GET_STATE(
            lambda _, allowed: "published" if allowed else "rejected",
            states=["published", "rejected"],
        ),
    )
    def get_state(self, *, allowed: bool):
        pass

    @transition(
        field=state,
        source="*",
        target=GET_STATE(
            lambda _, allowed: "published" if allowed else "rejected",
            states=["published", "rejected"],
        ),
    )
    def get_state_any_source(self, *, allowed: bool):
        pass

    @transition(
        field=state,
        source="+",
        target=GET_STATE(
            lambda _, allowed: "published" if allowed else "rejected",
            states=["published", "rejected"],
        ),
    )
    def get_state_any_source_except_target(self, *, allowed: bool):
        pass

    @transition(field=state, source="new", target=RETURN_VALUE("moderated", "blocked"))
    def return_value(self):
        return "published"

    @transition(field=state, source="*", target=RETURN_VALUE("moderated", "blocked"))
    def return_value_any_source(self):
        return "published"

    @transition(field=state, source="+", target=RETURN_VALUE("moderated", "blocked"))
    def return_value_any_source_except_target(self):
        return "published"

    @transition(field=state, source="new", target="published", on_error="failed")
    def on_error(self):
        pass


class DbState(models.Model):
    """
    States in DB
    """

    id = models.CharField(primary_key=True, max_length=50)

    label = models.CharField(max_length=255)

    def __str__(self):
        return self.label


class FKApplication(models.Model):
    """
    Student application need to be approved by dept chair and dean.
    Test workflow for FSMKeyField
    """

    state = FSMKeyField(DbState, default="new", on_delete=models.CASCADE)

    @transition(field=state, source="new", target="published")
    def standard(self):
        pass

    @transition(field=state, source="published")
    def no_target(self):
        pass

    @transition(field=state, source="*", target="blocked")
    def any_source(self):
        pass

    @transition(field=state, source="+", target="hidden")
    def any_source_except_target(self):
        pass

    @transition(
        field=state,
        source="new",
        target=GET_STATE(
            lambda _, allowed: "published" if allowed else "rejected",
            states=["published", "rejected"],
        ),
    )
    def get_state(self, *, allowed: bool):
        pass

    @transition(
        field=state,
        source="*",
        target=GET_STATE(
            lambda _, allowed: "published" if allowed else "rejected",
            states=["published", "rejected"],
        ),
    )
    def get_state_any_source(self, *, allowed: bool):
        pass

    @transition(
        field=state,
        source="+",
        target=GET_STATE(
            lambda _, allowed: "published" if allowed else "rejected",
            states=["published", "rejected"],
        ),
    )
    def get_state_any_source_except_target(self, *, allowed: bool):
        pass

    @transition(field=state, source="new", target=RETURN_VALUE("moderated", "blocked"))
    def return_value(self):
        return "published"

    @transition(field=state, source="*", target=RETURN_VALUE("moderated", "blocked"))
    def return_value_any_source(self):
        return "published"

    @transition(field=state, source="+", target=RETURN_VALUE("moderated", "blocked"))
    def return_value_any_source_except_target(self):
        return "published"

    @transition(field=state, source="new", target="published", on_error="failed")
    def on_error(self):
        pass


class MultiStateApplication(Application):
    another_state = FSMKeyField(DbState, default="new", on_delete=models.CASCADE)

    @transition(field=another_state, source="new", target="published")
    def another_state_standard(self):
        pass


class BlogPostState(models.IntegerChoices):
    NEW = 0, "New"
    PUBLISHED = 1, "Published"
    HIDDEN = 2, "Hidden"
    REMOVED = 3, "Removed"
    RESTORED = 4, "Restored"
    MODERATED = 5, "Moderated"
    STOLEN = 6, "Stolen"
    FAILED = 7, "Failed"


class BlogPost(models.Model):
    """
    Test workflow
    """

    state = FSMField(choices=BlogPostState.choices, default=BlogPostState.NEW, protected=True)

    class Meta:
        permissions = [
            ("can_publish_post", "Can publish post"),
            ("can_remove_post", "Can remove post"),
        ]

    def can_restore(self, user):
        return user.is_superuser or user.is_staff

    @transition(
        field=state,
        source=BlogPostState.NEW,
        target=BlogPostState.PUBLISHED,
        on_error=BlogPostState.FAILED,
        permission="testapp.can_publish_post",
    )
    def publish(self):
        pass

    @transition(field=state, source=BlogPostState.PUBLISHED)
    def notify_all(self):
        pass

    @transition(
        field=state,
        source=BlogPostState.PUBLISHED,
        target=BlogPostState.HIDDEN,
        on_error=BlogPostState.FAILED,
    )
    def hide(self):
        pass

    @transition(
        field=state,
        source=BlogPostState.NEW,
        target=BlogPostState.REMOVED,
        on_error=BlogPostState.FAILED,
        permission=lambda _, u: u.has_perm("testapp.can_remove_post"),
    )
    def remove(self):
        raise Exception(f"No rights to delete {self}")

    @transition(
        field=state,
        source=BlogPostState.NEW,
        target=BlogPostState.RESTORED,
        on_error=BlogPostState.FAILED,
        permission=can_restore,
    )
    def restore(self):
        pass

    @transition(field=state, source=[BlogPostState.PUBLISHED, BlogPostState.HIDDEN], target=BlogPostState.STOLEN)
    def steal(self):
        pass

    @transition(field=state, source="*", target=BlogPostState.MODERATED)
    def moderate(self):
        pass


# =============================================================================
# Admin test models
# =============================================================================


class PublishForm(forms.Form):
    """Form for publish transition arguments."""

    reviewer = forms.CharField(max_length=100, required=True, help_text="Name of the reviewer")
    notes = forms.CharField(widget=forms.Textarea, required=False, help_text="Optional notes")


class AdminArticle(FSMModelMixin, models.Model):
    """Model for testing FSMAdminMixin functionality."""

    title = models.CharField(max_length=200)
    content = models.TextField(blank=True)
    state = FSMField(default="draft", protected=True)

    class Meta:
        verbose_name = "Article"
        verbose_name_plural = "Articles"

    def __str__(self):
        return f"{self.title} ({self.state})"

    @transition(
        field=state,
        source="draft",
        target="pending",
        custom={"label": "Submit for Review"},
    )
    def submit(self):
        """Submit the article for review."""
        pass

    @transition(
        field=state,
        source="pending",
        target="published",
        custom={"label": "Publish", "form": "tests.testapp.models.PublishForm"},
    )
    def publish(self, reviewer=None, notes=None):
        """Publish the article."""
        pass

    @transition(
        field=state,
        source="pending",
        target="draft",
        custom={"label": "Reject"},
    )
    def reject(self):
        """Reject the article back to draft."""
        pass

    @transition(
        field=state,
        source="published",
        target="archived",
    )
    def archive(self):
        """Archive the published article."""
        pass

    @transition(
        field=state,
        source="*",
        target="draft",
        custom={"admin": False},
    )
    def reset(self):
        """Reset to draft - hidden from admin."""
        pass


class RejectionForm(forms.Form):
    """Form for rejection transition arguments."""

    reason = forms.CharField(
        max_length=500,
        required=True,
        widget=forms.Textarea,
        help_text="Reason for rejection",
    )


class AdminBlogPost(FSMModelMixin, models.Model):
    """Model for testing FSMAdminMixin functionality in tests."""

    title = models.CharField(max_length=200)
    state = FSMField(default="new", protected=True)
    review_state = FSMField(default="pending")

    class Meta:
        verbose_name = "Admin Blog Post"
        verbose_name_plural = "Admin Blog Posts"

    def __str__(self):
        return f"{self.title} ({self.state})"

    # State transitions
    @transition(
        field=state,
        source="new",
        target="published",
        custom={"label": "Publish Post"},
    )
    def publish(self):
        """Publish the blog post."""
        pass

    @transition(
        field=state,
        source="published",
        target="archived",
        custom={"label": "Archive Post"},
    )
    def archive(self):
        """Archive the blog post."""
        pass

    @transition(
        field=state,
        source="*",
        target="new",
    )
    def reset(self):
        """Reset to new state - no custom label."""
        pass

    @transition(
        field=state,
        source="*",
        target="scheduled",
        custom={"admin": False},
    )
    def schedule(self):
        """Schedule for later - hidden from admin."""
        pass

    # Review state transitions
    @transition(
        field=review_state,
        source="pending",
        target="rejected",
        custom={"label": "Reject", "form": "tests.testapp.models.RejectionForm"},
    )
    def reject(self, reason=None):
        """Reject the blog post."""
        pass

    @transition(
        field=review_state,
        source="pending",
        target="approved",
        custom={"label": "Approve"},
    )
    def approve(self):
        """Approve the blog post."""
        pass


class LoggableArticle(FSMModelMixin, models.Model):
    """Model for testing FSM log decorators."""

    title = models.CharField(max_length=200)
    state = FSMField(default="draft", protected=True)

    class Meta:
        verbose_name = "Loggable Article"
        verbose_name_plural = "Loggable Articles"

    def __str__(self):
        return f"{self.title} ({self.state})"

    @fsm_log_by
    @fsm_log_description
    @transition(field=state, source="draft", target="published")
    def publish(self, by=None, description=None):
        """Publish with logging support."""
        pass

    @fsm_log_by
    @transition(field=state, source="published", target="archived")
    def archive(self, by=None):
        """Archive with user tracking."""
        pass
