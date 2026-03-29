from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm

from ..choices import ApplicationState


class BaseAbstractModel(models.Model):
    state = fsm.FSMField(choices=ApplicationState.choices, default=ApplicationState.NEW)

    class Meta:
        abstract = True

    @fsm.transition(field=state, source=ApplicationState.NEW, target=ApplicationState.PUBLISHED)
    def publish(self):
        pass


class AnotherFromAbstractModel(BaseAbstractModel):
    """
    This class exists to trigger a regression when multiple concrete classes
    inherit from a shared abstract class (example: BaseAbstractModel).
    Don't try to remove it.
    """

    @fsm.transition(
        field="state", source=ApplicationState.PUBLISHED, target=ApplicationState.STICKED
    )
    def stick(self):
        pass


class InheritedFromAbstractModel(BaseAbstractModel):
    @fsm.transition(
        field="state", source=ApplicationState.PUBLISHED, target=ApplicationState.STICKED
    )
    def stick(self):
        pass


class AbstractInheritanceTests(TestCase):
    def setUp(self):
        self.model = InheritedFromAbstractModel()

    def test_known_transition_should_succeed(self):
        assert fsm.can_proceed(self.model.publish)

        self.model.publish()
        assert self.model.state == ApplicationState.PUBLISHED

        assert fsm.can_proceed(self.model.stick)

        self.model.stick()
        assert self.model.state == ApplicationState.STICKED

    def test_available_transitions_from_inherited_model(self):
        self.model.publish()
        assert self.model.state == ApplicationState.PUBLISHED

        transitions = self.model.get_available_state_transitions()  # type: ignore[attr-defined]
        transition_targets = [data.target for data in transitions]

        assert transition_targets == [ApplicationState.STICKED]

    def test_all_transitions_from_inherited_model(self):
        transitions = self.model.get_all_state_transitions()  # type: ignore[attr-defined]
        transition_pairs = {(data.source, data.target) for data in transitions}

        assert {
            (ApplicationState.NEW, ApplicationState.PUBLISHED),
            (ApplicationState.PUBLISHED, ApplicationState.STICKED),
        } == transition_pairs
