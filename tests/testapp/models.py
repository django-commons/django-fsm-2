from __future__ import annotations

import typing
import uuid

from django.contrib.auth.models import AbstractUser
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.fields import GenericRelation
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django_fsm_log.decorators import fsm_log_by
from django_fsm_log.decorators import fsm_log_description

import django_fsm as fsm
from django_fsm.log import track as fsm_track
from django_fsm.models import TransitionLogBase

from .choices import AdminBlogPostState
from .choices import AdminBlogPostStep
from .choices import ApplicationState
from .choices import BlogPostState


class StateLogQuerySet(models.QuerySet["StateLog"]):
    def _get_content_type(self, obj: models.Model) -> ContentType:
        return ContentType.objects.get_for_model(obj)

    def for_(self, obj: models.Model) -> typing.Self:
        return self.filter(content_type=self._get_content_type(obj), object_id=obj.pk)


class StateLog(TransitionLogBase):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.TextField()
    content_object = GenericForeignKey("content_type", "object_id")

    objects = StateLogQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=["source_state", "state"]),
            models.Index(fields=["content_type", "object_id"]),
        ]


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
    def return_value(self) -> ApplicationState:
        return ApplicationState.PUBLISHED

    @fsm.transition(
        field=state,
        source=fsm.ANY_STATE,
        target=fsm.RETURN_VALUE(ApplicationState.MODERATED, ApplicationState.BLOCKED),
    )
    def return_value_any_source(self) -> ApplicationState:
        return ApplicationState.PUBLISHED

    @fsm.transition(
        field=state,
        source=fsm.ANY_OTHER_STATE,
        target=fsm.RETURN_VALUE(ApplicationState.MODERATED, ApplicationState.BLOCKED),
    )
    def return_value_any_source_except_target(self) -> ApplicationState:
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
    def return_value(self) -> ApplicationState:
        return ApplicationState.MODERATED

    @fsm.transition(
        field=state,
        source=fsm.ANY_STATE,
        target=fsm.RETURN_VALUE(ApplicationState.MODERATED, ApplicationState.BLOCKED),
    )
    def return_value_any_source(self) -> ApplicationState:
        return ApplicationState.MODERATED

    @fsm.transition(
        field=state,
        source=fsm.ANY_OTHER_STATE,
        target=fsm.RETURN_VALUE(ApplicationState.MODERATED, ApplicationState.BLOCKED),
    )
    def return_value_any_source_except_target(self) -> ApplicationState:
        return ApplicationState.MODERATED

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

    def can_restore(self, user: fsm.UserWithPermissions) -> bool:
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


class TrackedPostStateLog(TransitionLogBase):
    post = models.ForeignKey(
        "TrackedPost",
        on_delete=models.CASCADE,
        related_name="transition_logs",
    )


@fsm_track(log_model=StateLog)
class CharPkTrackedPost(models.Model):
    id = models.CharField(primary_key=True, max_length=36)
    state = fsm.FSMField(default="new")

    logs = GenericRelation(to=StateLog)

    @fsm.transition(field=state, source="new", target="published")
    def publish(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass


@fsm_track(log_model=StateLog)
class IntegerPkTrackedPost(models.Model):
    id = models.IntegerField(primary_key=True)
    state = fsm.FSMField(default="new")

    logs = GenericRelation(to=StateLog)

    @fsm.transition(field=state, source="new", target="published")
    def publish(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass


@fsm_track(log_model=StateLog)
class UUIDPkTrackedPost(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    state = fsm.FSMField(default="new")

    logs = GenericRelation(to=StateLog)

    @fsm.transition(field=state, source="new", target="published")
    def publish(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass


@fsm_track(log_model=TrackedPostStateLog, relation_field="post")
class TrackedPost(models.Model):
    state = fsm.FSMField(default="new")

    @fsm.transition(field=state, source="new", target="published")
    def publish(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass


@fsm_track(log_model=StateLog)
class GenericTrackedPost(models.Model):
    state = fsm.FSMField(default="new")

    @fsm.transition(field=state, source="new", target="published")
    def publish(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass


class FSMLogBlogPost(models.Model):
    """Tracked by django-fsm-log only."""

    state = fsm.FSMField(default="new")

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(field=state, source="new", target="published")
    def publish(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass


@fsm_track(log_model=StateLog)
class FSMLogAndTrackedBlogPost(models.Model):
    """Tracked by both django-fsm-log and django_fsm.log."""

    state = fsm.FSMField(default="new")

    @fsm_log_by
    @fsm_log_description
    @fsm.transition(field=state, source="new", target="published")
    def publish(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass


@fsm_track(log_model=StateLog)
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

    key_state = fsm.FSMKeyField(
        # See tests/testapp/fixtures/test_states_data.json
        DbState,
        default="_NEW_",
        on_delete=models.CASCADE,
    )

    # state transitions
    def __str__(self) -> str:
        return f"{self.title} ({self.state})"

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

    @fsm.transition(
        field=state,
        source=AdminBlogPostState.CREATED,
        target=AdminBlogPostState.REVIEWED,
    )
    def moderate(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass

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

    @fsm.transition(
        field=state,
        source=fsm.ANY_STATE,
        target=None,
    )
    def invalid_without_forms(
        self, by: AbstractUser | None = None, description: str | None = None
    ) -> None:
        raise Exception("You shall not pass!")

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

    @fsm.transition(field=state, source=fsm.ANY_STATE, target=None, conditions=[lambda _obj: False])
    def conditions_unmet(
        self, by: AbstractUser | None = None, description: str | None = None
    ) -> None:
        pass

    @fsm.transition(
        field=state, source=fsm.ANY_STATE, target=None, permission=lambda _obj, _user: False
    )
    def permission_denied(
        self, by: AbstractUser | None = None, description: str | None = None
    ) -> None:
        pass

    # step transitions

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

    @fsm.transition(
        field=step,
        source=[AdminBlogPostStep.STEP_2],
        target=AdminBlogPostStep.STEP_3,
    )
    def step_three(self, by: AbstractUser | None = None, description: str | None = None) -> None:
        pass

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
