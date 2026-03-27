from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm


class StateChoice(models.TextChoices):
    NEW = "NEW", "new"
    PUBLISHED = "PUBLISHED", "published"
    STICKED = "STICKED", "sticked"


class BaseAbstractModel(models.Model):
    state = fsm.FSMField(choices=StateChoice.choices, default=StateChoice.NEW)

    class Meta:
        abstract = True

    @fsm.transition(field=state, source=StateChoice.NEW, target=StateChoice.PUBLISHED)
    def publish(self):
        pass


class AnotherFromAbstractModel(BaseAbstractModel):
    """
    This class exists to trigger a regression when multiple concrete classes
    inherit from a shared abstract class (example: BaseAbstractModel).
    Don't try to remove it.
    """

    @fsm.transition(field="state", source=StateChoice.PUBLISHED, target=StateChoice.STICKED)
    def stick(self):
        pass


class InheritedFromAbstractModel(BaseAbstractModel):
    @fsm.transition(field="state", source=StateChoice.PUBLISHED, target=StateChoice.STICKED)
    def stick(self):
        pass


class TestinheritedModel(TestCase):
    def setUp(self):
        self.model = InheritedFromAbstractModel()

    def test_known_transition_should_succeed(self):
        assert fsm.can_proceed(self.model.publish)
        self.model.publish()
        assert self.model.state == StateChoice.PUBLISHED

        assert fsm.can_proceed(self.model.stick)
        self.model.stick()
        assert self.model.state == StateChoice.STICKED

    def test_field_available_transitions_works(self):
        self.model.publish()
        assert self.model.state == StateChoice.PUBLISHED
        transitions = self.model.get_available_state_transitions()  # type: ignore[attr-defined]
        assert [data.target for data in transitions] == [StateChoice.STICKED]

    def test_field_all_transitions_works(self):
        transitions = self.model.get_all_state_transitions()  # type: ignore[attr-defined]
        assert {
            (StateChoice.NEW, StateChoice.PUBLISHED),
            (StateChoice.PUBLISHED, StateChoice.STICKED),
        } == {(data.source, data.target) for data in transitions}
