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
