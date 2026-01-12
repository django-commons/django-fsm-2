from __future__ import annotations

from django.db import models
from django.test import TestCase

from django_fsm_rx import FSMField
from django_fsm_rx import transition


class BlogPostWithCustomData(models.Model):
    state = FSMField(default="new")

    @transition(
        field=state,
        source="new",
        target="published",
        conditions=[],
        custom={"label": "Publish", "type": "*"},
    )
    def publish(self):
        pass

    @transition(
        field=state,
        source="published",
        target="destroyed",
        custom={"label": "Destroy", "type": "manual"},
    )
    def destroy(self):
        pass

    @transition(
        field=state,
        source="published",
        target="review",
        custom={"label": "Periodic review", "type": "automated"},
    )
    def review(self):
        pass


class CustomTransitionDataTest(TestCase):
    def setUp(self):
        self.model = BlogPostWithCustomData()

    def test_initial_state(self):
        assert self.model.state == "new"
        transitions = list(self.model.get_available_state_transitions())
        assert len(transitions) == 1
        assert transitions[0].target == "published"
        assert transitions[0].custom == {"label": "Publish", "type": "*"}

    def test_all_transitions_have_custom_data(self):
        transitions = self.model.get_all_state_transitions()
        for t in transitions:
            assert t.custom["label"] is not None
            assert t.custom["type"] is not None
