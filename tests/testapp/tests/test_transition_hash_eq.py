from __future__ import annotations

from django.db import models

import django_fsm as fsm


def test_transition_eq_matches_name_and_transition() -> None:
    def publish() -> None:
        pass

    publish_transition = fsm.Transition(
        method=publish,
        source="new",
        target="published",
        on_error=None,
        conditions=[],
        permission=None,
        custom={},
    )

    def other() -> None:
        pass

    other.__name__ = "publish"
    other_transition = fsm.Transition(
        method=other,
        source="new",
        target="published",
        on_error=None,
        conditions=[],
        permission=None,
        custom={},
    )

    assert publish_transition == "publish"
    assert publish_transition != other_transition
    assert publish_transition != "other"
    assert publish_transition != object()


def test_transition_same_name_different_models_not_equal() -> None:
    class First(models.Model):
        def publish(self) -> None:
            pass

    class Second(models.Model):
        def publish(self) -> None:
            pass

    first_transition = fsm.Transition(
        method=First.publish,
        source="new",
        target="published",
        on_error=None,
        conditions=[],
        permission=None,
        custom={},
    )
    second_transition = fsm.Transition(
        method=Second.publish,
        source="new",
        target="published",
        on_error=None,
        conditions=[],
        permission=None,
        custom={},
    )

    assert first_transition != second_transition
    assert hash(first_transition) != hash(second_transition)
