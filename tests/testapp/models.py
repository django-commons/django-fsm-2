from __future__ import annotations

from django.contrib.auth.models import AbstractUser
from django.db import models
from django_fsm_log.decorators import fsm_log_by
from django_fsm_log.decorators import fsm_log_description

import django_fsm as fsm

from .choices import ApplicationState
from .choices import BlogPostState


class Application(models.Model):
    """
    Student application need to be approved by dept chair and dean.
    Test workflow
    """

    state = fsm.FSMField(default=ApplicationState.NEW)

    @fsm.transition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.PUBLISHED,
        on_error=ApplicationState.FAILED,
    )
    def standard(self) -> None:
        pass

    @fsm.transition(field=state, source=ApplicationState.PUBLISHED)
    def no_target(self) -> None:
        pass

    @fsm.transition(field=state, source=fsm.ANY_STATE, target=ApplicationState.BLOCKED)
    def any_source(self) -> None:
        pass

    @fsm.transition(field=state, source=fsm.ANY_OTHER_STATE, target=ApplicationState.HIDDEN)
    def any_source_except_target(self) -> None:
        pass

    @fsm.transition(
        field=state,
        source=ApplicationState.NEW,
        target=fsm.GET_STATE(
            lambda _, allowed: ApplicationState.PUBLISHED if allowed else ApplicationState.REJECTED,
            states=[ApplicationState.PUBLISHED, ApplicationState.REJECTED],
        ),
    )
    def get_state(self, *, allowed: bool) -> None:
        pass

    @fsm.transition(
        field=state,
        source=fsm.ANY_STATE,
        target=fsm.GET_STATE(
            lambda _, allowed: ApplicationState.PUBLISHED if allowed else ApplicationState.REJECTED,
            states=[ApplicationState.PUBLISHED, ApplicationState.REJECTED],
        ),
    )
    def get_state_any_source(self, *, allowed: bool) -> None:
        pass

    @fsm.transition(
        field=state,
        source=fsm.ANY_OTHER_STATE,
        target=fsm.GET_STATE(
            lambda _, allowed: ApplicationState.PUBLISHED if allowed else ApplicationState.REJECTED,
            states=[ApplicationState.PUBLISHED, ApplicationState.REJECTED],
        ),
    )
    def get_state_any_source_except_target(self, *, allowed: bool) -> None:
        pass

    @fsm.transition(
        field=state,
        source=ApplicationState.NEW,
        target=fsm.RETURN_VALUE(ApplicationState.MODERATED, ApplicationState.BLOCKED),
    )
    def return_value(self) -> str:
        return ApplicationState.PUBLISHED

    @fsm.transition(
        field=state,
        source=fsm.ANY_STATE,
        target=fsm.RETURN_VALUE(ApplicationState.MODERATED, ApplicationState.BLOCKED),
    )
    def return_value_any_source(self) -> str:
        return ApplicationState.PUBLISHED

    @fsm.transition(
        field=state,
        source=fsm.ANY_OTHER_STATE,
        target=fsm.RETURN_VALUE(ApplicationState.MODERATED, ApplicationState.BLOCKED),
    )
    def return_value_any_source_except_target(self) -> str:
        return ApplicationState.PUBLISHED

    @fsm.transition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.PUBLISHED,
        on_error=ApplicationState.FAILED,
    )
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


class DbStateAutoPk(models.Model):
    """
    States in DB
    """

    name = models.CharField(unique=True, max_length=10)


class FKApplication(models.Model):
    """
    Student application need to be approved by dept chair and dean.
    Test workflow for FSMKeyField
    """

    state = fsm.FSMKeyField(DbState, default=ApplicationState.NEW, on_delete=models.CASCADE)

    @fsm.transition(field=state, source=ApplicationState.NEW, target=ApplicationState.PUBLISHED)
    def standard(self) -> None:
        pass

    @fsm.transition(field=state, source=ApplicationState.PUBLISHED)
    def no_target(self) -> None:
        pass

    @fsm.transition(field=state, source=fsm.ANY_STATE, target=ApplicationState.BLOCKED)
    def any_source(self) -> None:
        pass

    @fsm.transition(field=state, source=fsm.ANY_OTHER_STATE, target=ApplicationState.HIDDEN)
    def any_source_except_target(self) -> None:
        pass

    @fsm.transition(
        field=state,
        source=ApplicationState.NEW,
        target=fsm.GET_STATE(
            lambda _, allowed: ApplicationState.PUBLISHED if allowed else ApplicationState.REJECTED,
            states=[ApplicationState.PUBLISHED, ApplicationState.REJECTED],
        ),
    )
    def get_state(self, *, allowed: bool) -> None:
        pass

    @fsm.transition(
        field=state,
        source=fsm.ANY_STATE,
        target=fsm.GET_STATE(
            lambda _, allowed: ApplicationState.PUBLISHED if allowed else ApplicationState.REJECTED,
            states=[ApplicationState.PUBLISHED, ApplicationState.REJECTED],
        ),
    )
    def get_state_any_source(self, *, allowed: bool) -> None:
        pass

    @fsm.transition(
        field=state,
        source=fsm.ANY_OTHER_STATE,
        target=fsm.GET_STATE(
            lambda _, allowed: ApplicationState.PUBLISHED if allowed else ApplicationState.REJECTED,
            states=[ApplicationState.PUBLISHED, ApplicationState.REJECTED],
        ),
    )
    def get_state_any_source_except_target(self, *, allowed: bool) -> None:
        pass

    @fsm.transition(
        field=state,
        source=ApplicationState.NEW,
        target=fsm.RETURN_VALUE(ApplicationState.MODERATED, ApplicationState.BLOCKED),
    )
    def return_value(self) -> str:
        return "published"

    @fsm.transition(
        field=state,
        source=fsm.ANY_STATE,
        target=fsm.RETURN_VALUE(ApplicationState.MODERATED, ApplicationState.BLOCKED),
    )
    def return_value_any_source(self) -> str:
        return "published"

    @fsm.transition(
        field=state,
        source=fsm.ANY_OTHER_STATE,
        target=fsm.RETURN_VALUE(ApplicationState.MODERATED, ApplicationState.BLOCKED),
    )
    def return_value_any_source_except_target(self) -> str:
        return "published"

    @fsm.transition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.PUBLISHED,
        on_error=ApplicationState.FAILED,
    )
    def on_error(self) -> None:
        pass


class MultiStateApplication(Application):
    another_state = fsm.FSMKeyField(DbState, default=ApplicationState.NEW, on_delete=models.CASCADE)

    @fsm.transition(
        field=another_state, source=ApplicationState.NEW, target=ApplicationState.PUBLISHED
    )
    def another_state_standard(self) -> None:
        pass


class BlogPost(models.Model):
    """
    Test workflow
    """

    state = fsm.FSMField(choices=BlogPostState.choices, default=BlogPostState.NEW, protected=True)

    class Meta:
        permissions = [
            ("can_publish_post", "Can publish post"),
            ("can_remove_post", "Can remove post"),
        ]

    def can_restore(self: models.Model, user: fsm.UserWithPermissions) -> bool:
        if isinstance(user, AbstractUser):
            return bool(user.is_superuser or user.is_staff)
        return False

    @fsm.transition(
        field=state,
        source=BlogPostState.NEW,
        target=BlogPostState.PUBLISHED,
        on_error=BlogPostState.FAILED,
        permission="testapp.can_publish_post",
    )
    def publish(self) -> None:
        pass

    @fsm.transition(field=state, source=BlogPostState.PUBLISHED)
    def notify_all(self) -> None:
        pass

    @fsm.transition(
        field=state,
        source=BlogPostState.PUBLISHED,
        target=BlogPostState.HIDDEN,
        on_error=BlogPostState.FAILED,
    )
    def hide(self) -> None:
        pass

    @fsm.transition(
        field=state,
        source=BlogPostState.NEW,
        target=BlogPostState.REMOVED,
        on_error=BlogPostState.FAILED,
        permission=lambda _, u: u.has_perm("testapp.can_remove_post"),
    )
    def remove(self) -> None:
        raise Exception(f"No rights to delete {self}")

    @fsm.transition(
        field=state,
        source=BlogPostState.NEW,
        target=BlogPostState.RESTORED,
        on_error=BlogPostState.FAILED,
        permission=can_restore,
    )
    def restore(self) -> None:
        pass

    @fsm.transition(
        field=state,
        source=[BlogPostState.PUBLISHED, BlogPostState.HIDDEN],
        target=BlogPostState.STOLEN,
    )
    def steal(self) -> None:
        pass

    @fsm.transition(field=state, source=fsm.ANY_STATE, target=BlogPostState.MODERATED)
    def moderate(self) -> None:
        pass


class AdminBlogPostState(models.TextChoices):
    CREATED = "created", "Created"
    REVIEWED = "reviewed", "Reviewed"
    PUBLISHED = "published", "Published"
    HIDDEN = "hidden", "Hidden"


class AdminBlogPostStep(models.IntegerChoices):
    STEP_1 = 1, "Step one"
    STEP_2 = 2, "Step two"
    STEP_3 = 3, "Step three"


class AdminBlogPost(fsm.FSMModelMixin, models.Model):
    title = models.CharField(max_length=50)

    state = fsm.FSMField(
        choices=AdminBlogPostState.choices,
        default=AdminBlogPostState.CREATED,
        protected=True,
    )

    step = fsm.FSMIntegerField(
        choices=AdminBlogPostStep.choices,
        default=AdminBlogPostStep.STEP_1,
        protected=False,
    )

    key_state = fsm.FSMKeyField(DbState, default="new", on_delete=models.CASCADE)

    # state transitions
    def __str__(self) -> str:
        return f"{self.title} ({self.state})"

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(
        field=state,
        source=fsm.ANY_STATE,
        target=fsm.RETURN_VALUE(*AdminBlogPostState),
    )
    def force_state(
        self,
        state: AdminBlogPostState,
        by: AbstractUser | None = None,
        description: str | None = None,
    ) -> AdminBlogPostState:
        return state

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(
        field=state,
        source=fsm.ANY_STATE,
        target=AdminBlogPostState.HIDDEN,
        custom={
            "admin": False,
        },
    )
    def secret_transition(
        self, by: AbstractUser | None = None, description: str | None = None
    ) -> None:
        pass

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(
        field=state,
        source=AdminBlogPostState.CREATED,
        target=AdminBlogPostState.REVIEWED,
    )
    def moderate(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(
        field=state,
        source=[
            AdminBlogPostState.REVIEWED,
            AdminBlogPostState.HIDDEN,
        ],
        target=AdminBlogPostState.PUBLISHED,
    )
    def publish(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(
        field=state,
        source=[
            AdminBlogPostState.REVIEWED,
            AdminBlogPostState.PUBLISHED,
        ],
        target=AdminBlogPostState.HIDDEN,
    )
    def hide(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(
        field=state,
        source=fsm.ANY_STATE,
        target=None,
    )
    def invalid(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        raise Exception("You shall not pass!")

    @fsm.transition(
        field=state,
        source=fsm.ANY_STATE,
        target=None,
    )
    def non_fsm_log_invalid(self) -> None:
        raise Exception("Domain-raised exception")

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(
        field=state,
        source=fsm.ANY_STATE,
        target=None,
    )
    def invalid_without_forms(
        self, by: AbstractUser | None = None, description: str | None = None
    ) -> None:
        raise Exception("You shall not pass!")

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(
        field=state,
        source=fsm.ANY_STATE,
        target=AdminBlogPostState.CREATED,
        custom={
            "label": "Rename *",
            "form": "tests.testapp.admin_forms.AdminBlogPostRenameForm",
            "help_text": "Do it wisely!",
        },
    )
    def complex_transition(
        self,
        *,
        title: str,
        comment: str | None = None,
        by: AbstractUser | None = None,
        description: str | None = None,
    ) -> None:
        self.title = title
        if comment:
            ...
            # Do something with the comment

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(field=state, source=fsm.ANY_STATE, target=None, conditions=[lambda _obj: False])
    def conditions_unmet(
        self, by: AbstractUser | None = None, description: str | None = None
    ) -> None:
        pass

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(
        field=state, source=fsm.ANY_STATE, target=None, permission=lambda _obj, _user: False
    )
    def permission_denied(
        self, by: AbstractUser | None = None, description: str | None = None
    ) -> None:
        pass

    # step transitions

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(
        field=step,
        source=[AdminBlogPostStep.STEP_1],
        target=AdminBlogPostStep.STEP_2,
        custom={
            "label": "Go to Step 2",
        },
    )
    def step_two(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(
        field=step,
        source=[AdminBlogPostStep.STEP_2],
        target=AdminBlogPostStep.STEP_3,
    )
    def step_three(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(
        field=step,
        source=[
            AdminBlogPostStep.STEP_2,
            AdminBlogPostStep.STEP_3,
        ],
        target=AdminBlogPostStep.STEP_1,
    )
    def step_reset(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass

    def normal_function(self):
        raise NotImplementedError

    @property
    def name_property(self):
        return "name"
