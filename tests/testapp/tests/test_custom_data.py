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

    def test_initial_state(self):
        assert self.model.state == ApplicationState.NEW
        transitions = list(self.model.get_available_state_transitions())  # type: ignore[attr-defined]
        assert len(transitions) == 1
        assert transitions[0].target == ApplicationState.PUBLISHED
        assert transitions[0].custom == {"label": "Publish", "type": "*"}

    def test_all_transitions_have_custom_data(self):
        transitions = self.model.get_all_state_transitions()  # type: ignore[attr-defined]
        for t in transitions:
            assert t.custom["label"] is not None
            assert t.custom["type"] is not None
