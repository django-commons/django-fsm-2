from __future__ import annotations

from django.db import models
from django.test import TestCase

from django_fsm import FSMField
from django_fsm import can_proceed
from django_fsm import transition


class BaseAbstractModel(models.Model):
    state = FSMField(default="new")

    class Meta:
        abstract = True

    @transition(field=state, source="new", target="published")
    def publish(self):
        pass


class AnotherFromAbstractModel(BaseAbstractModel):
    """
    This class exists to trigger a regression when multiple concrete classes
    inherit from a shared abstract class (example: BaseAbstractModel).
    Don't try to remove it.
    """

    @transition(field="state", source="published", target="sticked")
    def stick(self):
        pass


class InheritedFromAbstractModel(BaseAbstractModel):
    @transition(field="state", source="published", target="sticked")
    def stick(self):
        pass


class TestinheritedModel(TestCase):
    def setUp(self):
        self.model = InheritedFromAbstractModel()

    def test_known_transition_should_succeed(self):
        assert can_proceed(self.model.publish)
        self.model.publish()
        assert self.model.state == "published"

        assert can_proceed(self.model.stick)
        self.model.stick()
        assert self.model.state == "sticked"

    def test_field_available_transitions_works(self):
        self.model.publish()
        assert self.model.state == "published"
        transitions = self.model.get_available_state_transitions()  # type: ignore[attr-defined]
        assert [data.target for data in transitions] == ["sticked"]

    def test_field_all_transitions_works(self):
        transitions = self.model.get_all_state_transitions()  # type: ignore[attr-defined]
        assert {("new", "published"), ("published", "sticked")} == {
            (data.source, data.target) for data in transitions
        }
