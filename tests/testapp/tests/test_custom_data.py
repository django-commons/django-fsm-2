from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm

from ..choices import ApplicationState


class BlogPostWithCustomData(models.Model):
    state = fsm.FSMField(choices=ApplicationState.choices, default=ApplicationState.NEW)

    @fsm.transition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.PUBLISHED,
        conditions=[],
        custom={
            "label": "Publish",
            "type": "*",
        },
    )
    def publish(self):
        pass

    @fsm.transition(
        field=state,
        source=ApplicationState.PUBLISHED,
        target=ApplicationState.REMOVED,
        custom={
            "label": "Remove",
            "type": "manual",
        },
    )
    def remove(self):
        pass

    @fsm.transition(
        field=state,
        source=ApplicationState.PUBLISHED,
        target=ApplicationState.MODERATED,
        custom={
            "label": "Periodic review",
            "type": "automated",
        },
    )
    def moderate(self):
        pass


class CustomTransitionDataTest(TestCase):
    def setUp(self):
        self.model = BlogPostWithCustomData()

    def test_initial_state_exposes_custom_data(self):
        assert self.model.state == ApplicationState.NEW

        available_transitions = list(self.model.get_available_state_transitions())  # type: ignore[attr-defined]

        assert len(available_transitions) == 1

        publish_transition = available_transitions[0]
        assert publish_transition.target == ApplicationState.PUBLISHED
        assert publish_transition.custom == {"label": "Publish", "type": "*"}

    def test_all_transitions_have_custom_data(self):
        all_transitions = self.model.get_all_state_transitions()  # type: ignore[attr-defined]

        for transition in all_transitions:
            assert transition.custom["label"] is not None
            assert transition.custom["type"] is not None
