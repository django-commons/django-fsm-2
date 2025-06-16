from __future__ import annotations

from django.db import models
from django_fsm_log.decorators import fsm_log_by
from django_fsm_log.decorators import fsm_log_description

from django_fsm import FSMField
from django_fsm import FSMKeyField
from django_fsm import transition


class Application(models.Model):
    """
    Student application need to be approved by dept chair and dean.
    Test workflow
    """

    state = FSMField(default="new")

    @transition(field=state, source="new", target="draft")
    def draft(self):
        pass

    @transition(field=state, source=["new", "draft"], target="dept")
    def submitted(self):
        pass

    @transition(field=state, source="dept", target="dean")
    def dept_approved(self):
        pass

    @transition(field=state, source="dept", target="new")
    def dept_rejected(self):
        pass

    @transition(field=state, source="dean", target="done")
    def dean_approved(self):
        pass

    @transition(field=state, source="dean", target="dept")
    def dean_rejected(self):
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

    @transition(field=state, source="new", target="draft")
    def draft(self):
        pass

    @transition(field=state, source=["new", "draft"], target="dept")
    def submitted(self):
        pass

    @transition(field=state, source="dept", target="dean")
    def dept_approved(self):
        pass

    @transition(field=state, source="dept", target="new")
    def dept_rejected(self):
        pass

    @transition(field=state, source="dean", target="done")
    def dean_approved(self):
        pass

    @transition(field=state, source="dean", target="dept")
    def dean_rejected(self):
        pass


class BlogPost(models.Model):
    """
    Test workflow
    """

    state = FSMField(default="new", protected=True)

    class Meta:
        permissions = [
            ("can_publish_post", "Can publish post"),
            ("can_remove_post", "Can remove post"),
        ]

    def can_restore(self, user):
        return user.is_superuser or user.is_staff

    @transition(field=state, source="new", target="published", on_error="failed", permission="testapp.can_publish_post")
    def publish(self):
        pass

    @transition(field=state, source="published")
    def notify_all(self):
        pass

    @transition(
        field=state,
        source="published",
        target="hidden",
        on_error="failed",
    )
    def hide(self):
        pass

    @transition(
        field=state,
        source="new",
        target="removed",
        on_error="failed",
        permission=lambda _, u: u.has_perm("testapp.can_remove_post"),
    )
    def remove(self):
        raise Exception(f"No rights to delete {self}")

    @transition(field=state, source="new", target="restored", on_error="failed", permission=can_restore)
    def restore(self):
        pass

    @transition(field=state, source=["published", "hidden"], target="stolen")
    def steal(self):
        pass

    @transition(field=state, source="*", target="moderated")
    def moderate(self):
        pass


class AdminBlogPostState(models.TextChoices):
    CREATED = "created", "Created"
    REVIEWED = "reviewed", "Reviewed"
    PUBLISHED = "published", "Published"
    HIDDEN = "hidden", "Hidden"


class AdminBlogPostStep(models.TextChoices):
    STEP_1 = "step1", "Step one"
    STEP_2 = "step2", "Step two"
    STEP_3 = "step3", "Step three"


class AdminBlogPost(models.Model):
    title = models.CharField(max_length=50)

    state = FSMField(
        choices=AdminBlogPostState.choices,
        default=AdminBlogPostState.CREATED,
        protected=True,
    )

    step = FSMField(
        choices=AdminBlogPostStep.choices,
        default=AdminBlogPostStep.STEP_1,
        protected=False,
    )

    # state transitions

    @fsm_log_by
    @fsm_log_description
    @transition(
        field=state,
        source="*",
        target=AdminBlogPostState.HIDDEN,
        custom={
            "admin": False,
        },
    )
    def secret_transition(self, by=None, description=None):
        pass

    @fsm_log_by
    @fsm_log_description
    @transition(
        field=state,
        source=[AdminBlogPostState.CREATED],
        target=AdminBlogPostState.REVIEWED,
    )
    def moderate(self, by=None, description=None):
        pass

    @fsm_log_by
    @fsm_log_description
    @transition(
        field=state,
        source=[
            AdminBlogPostState.REVIEWED,
            AdminBlogPostState.HIDDEN,
        ],
        target=AdminBlogPostState.PUBLISHED,
    )
    def publish(self, by=None, description=None):
        pass

    @fsm_log_by
    @fsm_log_description
    @transition(
        field=state,
        source=[
            AdminBlogPostState.REVIEWED,
            AdminBlogPostState.PUBLISHED,
        ],
        target=AdminBlogPostState.HIDDEN,
    )
    def hide(self, by=None, description=None):
        pass

    # step transitions

    @fsm_log_by
    @fsm_log_description
    @transition(
        field=step,
        source=[AdminBlogPostStep.STEP_1],
        target=AdminBlogPostStep.STEP_2,
        custom={
            "label": "Go to Step 2",
        },
    )
    def step_two(self, by=None, description=None):
        pass

    @fsm_log_by
    @fsm_log_description
    @transition(
        field=step,
        source=[AdminBlogPostStep.STEP_2],
        target=AdminBlogPostStep.STEP_3,
    )
    def step_three(self, by=None, description=None):
        pass

    @fsm_log_by
    @fsm_log_description
    @transition(
        field=step,
        source=[
            AdminBlogPostStep.STEP_2,
            AdminBlogPostStep.STEP_3,
        ],
        target=AdminBlogPostStep.STEP_1,
    )
    def step_reset(self, by=None, description=None):
        pass
