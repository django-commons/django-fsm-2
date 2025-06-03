from __future__ import annotations

import typing

from django.db import models
from django_fsm_log.decorators import fsm_log_by
from django_fsm_log.decorators import fsm_log_description

from django_fsm import GET_STATE
from django_fsm import RETURN_VALUE
from django_fsm import FSMField
from django_fsm import FSMKeyField
from django_fsm import transition

if typing.TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser


class Application(models.Model):
    """
    Student application need to be approved by dept chair and dean.
    Test workflow
    """

    state = FSMField(default="new")

    @transition(field=state, source="new", target="published", on_error="failed")
    def standard(self) -> None:
        pass

    @transition(field=state, source="published")
    def no_target(self) -> None:
        pass

    @transition(field=state, source="*", target="blocked")
    def any_source(self) -> None:
        pass

    @transition(field=state, source="+", target="hidden")
    def any_source_except_target(self) -> None:
        pass

    @transition(
        field=state,
        source="new",
        target=GET_STATE(
            lambda _, allowed: "published" if allowed else "rejected",
            states=["published", "rejected"],
        ),
    )
    def get_state(self, *, allowed: bool) -> None:
        pass

    @transition(
        field=state,
        source="*",
        target=GET_STATE(
            lambda _, allowed: "published" if allowed else "rejected",
            states=["published", "rejected"],
        ),
    )
    def get_state_any_source(self, *, allowed: bool) -> None:
        pass

    @transition(
        field=state,
        source="+",
        target=GET_STATE(
            lambda _, allowed: "published" if allowed else "rejected",
            states=["published", "rejected"],
        ),
    )
    def get_state_any_source_except_target(self, *, allowed: bool) -> None:
        pass

    @transition(field=state, source="new", target=RETURN_VALUE("moderated", "blocked"))
    def return_value(self) -> str:
        return "published"

    @transition(field=state, source="*", target=RETURN_VALUE("moderated", "blocked"))
    def return_value_any_source(self) -> str:
        return "published"

    @transition(field=state, source="+", target=RETURN_VALUE("moderated", "blocked"))
    def return_value_any_source_except_target(self) -> str:
        return "published"

    @transition(field=state, source="new", target="published", on_error="failed")
    def on_error(self) -> None:
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
    def standard(self) -> None:
        pass

    @transition(field=state, source="published")
    def no_target(self) -> None:
        pass

    @transition(field=state, source="*", target="blocked")
    def any_source(self) -> None:
        pass

    @transition(field=state, source="+", target="hidden")
    def any_source_except_target(self) -> None:
        pass

    @transition(
        field=state,
        source="new",
        target=GET_STATE(
            lambda _, allowed: "published" if allowed else "rejected",
            states=["published", "rejected"],
        ),
    )
    def get_state(self, *, allowed: bool) -> None:
        pass

    @transition(
        field=state,
        source="*",
        target=GET_STATE(
            lambda _, allowed: "published" if allowed else "rejected",
            states=["published", "rejected"],
        ),
    )
    def get_state_any_source(self, *, allowed: bool) -> None:
        pass

    @transition(
        field=state,
        source="+",
        target=GET_STATE(
            lambda _, allowed: "published" if allowed else "rejected",
            states=["published", "rejected"],
        ),
    )
    def get_state_any_source_except_target(self, *, allowed: bool) -> None:
        pass

    @transition(field=state, source="new", target=RETURN_VALUE("moderated", "blocked"))
    def return_value(self) -> str:
        return "published"

    @transition(field=state, source="*", target=RETURN_VALUE("moderated", "blocked"))
    def return_value_any_source(self) -> str:
        return "published"

    @transition(field=state, source="+", target=RETURN_VALUE("moderated", "blocked"))
    def return_value_any_source_except_target(self) -> str:
        return "published"

    @transition(field=state, source="new", target="published", on_error="failed")
    def on_error(self) -> None:
        pass


class MultiStateApplication(Application):
    another_state = FSMKeyField(DbState, default="new", on_delete=models.CASCADE)

    @transition(field=another_state, source="new", target="published")
    def another_state_standard(self) -> None:
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

    def can_restore(self: models.Model, user: AbstractUser) -> bool:
        return bool(user.is_superuser or user.is_staff)

    @transition(
        field=state,
        source=BlogPostState.NEW,
        target=BlogPostState.PUBLISHED,
        on_error=BlogPostState.FAILED,
        permission="testapp.can_publish_post",
    )
    def publish(self) -> None:
        pass

    @transition(field=state, source=BlogPostState.PUBLISHED)
    def notify_all(self) -> None:
        pass

    @transition(
        field=state,
        source=BlogPostState.PUBLISHED,
        target=BlogPostState.HIDDEN,
        on_error=BlogPostState.FAILED,
    )
    def hide(self) -> None:
        pass

    @transition(
        field=state,
        source=BlogPostState.NEW,
        target=BlogPostState.REMOVED,
        on_error=BlogPostState.FAILED,
        permission=lambda _, u: u.has_perm("testapp.can_remove_post"),
    )
    def remove(self) -> None:
        raise Exception(f"No rights to delete {self}")

    @transition(
        field=state,
        source=BlogPostState.NEW,
        target=BlogPostState.RESTORED,
        on_error=BlogPostState.FAILED,
        permission=can_restore,
    )
    def restore(self) -> None:
        pass

    @transition(
        field=state,
        source=[BlogPostState.PUBLISHED, BlogPostState.HIDDEN],
        target=BlogPostState.STOLEN,
    )
    def steal(self) -> None:
        pass

    @transition(field=state, source="*", target=BlogPostState.MODERATED)
    def moderate(self) -> None:
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
