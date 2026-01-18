from __future__ import annotations

from django.db import models

from django_fsm import GET_STATE
from django_fsm import RETURN_VALUE
from django_fsm import FSMField
from django_fsm import FSMKeyField
from django_fsm import transition


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

    @transition(
        field=state,
        source=[BlogPostState.PUBLISHED, BlogPostState.HIDDEN],
        target=BlogPostState.STOLEN,
    )
    def steal(self):
        pass

    @transition(field=state, source="*", target=BlogPostState.MODERATED)
    def moderate(self):
        pass
