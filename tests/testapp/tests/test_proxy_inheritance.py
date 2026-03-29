from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm

from ..choices import ApplicationState


class BaseModel(models.Model):
    state = fsm.FSMField(choices=ApplicationState.choices, default=ApplicationState.NEW)

    @fsm.transition(field=state, source=ApplicationState.NEW, target=ApplicationState.PUBLISHED)
    def publish(self):
        pass


class InheritedModel(BaseModel):
    class Meta:
        proxy = True

    @fsm.transition(
        field="state", source=ApplicationState.PUBLISHED, target=ApplicationState.STICKED
    )
    def stick(self):
        pass


class ProxyInheritanceTests(TestCase):
    def setUp(self):
        self.model = InheritedModel()

    def test_known_transition_should_succeed(self):
        assert fsm.can_proceed(self.model.publish)

        self.model.publish()
        assert self.model.state == ApplicationState.PUBLISHED

        assert fsm.can_proceed(self.model.stick)

        self.model.stick()
        assert self.model.state == ApplicationState.STICKED

    def test_available_transitions_from_proxy(self):
        self.model.publish()
        assert self.model.state == ApplicationState.PUBLISHED

        transitions = self.model.get_available_state_transitions()  # type: ignore[attr-defined]
        assert [data.target for data in transitions] == [ApplicationState.STICKED]

    def test_all_transitions_for_base_model(self):
        transitions = BaseModel().get_all_state_transitions()  # type: ignore[attr-defined]

        assert {(data.source, data.target) for data in transitions} == {
            (ApplicationState.NEW, ApplicationState.PUBLISHED)
        }

    def test_all_transitions_for_proxy(self):
        transitions = self.model.get_all_state_transitions()  # type: ignore[attr-defined]

        assert {(data.source, data.target) for data in transitions} == {
            (ApplicationState.NEW, ApplicationState.PUBLISHED),
            (ApplicationState.PUBLISHED, ApplicationState.STICKED),
        }
