from __future__ import annotations

from django.db import models
from django.test import TestCase

from django_fsm import FSMField
from django_fsm import can_proceed
from django_fsm import transition


class BaseModel(models.Model):
    state = FSMField(default="new")

    @transition(field=state, source="new", target="published")
    def publish(self):
        pass


class InheritedModel(BaseModel):
    class Meta:
        proxy = True

    @transition(field="state", source="published", target="sticked")
    def stick(self):
        pass


class TestinheritedModel(TestCase):
    def setUp(self):
        self.model = InheritedModel()

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
        transitions = self.model.get_available_state_transitions()
        assert [data.target for data in transitions] == ["sticked"]

    def test_field_all_transitions_base_model(self):
        transitions = BaseModel().get_all_state_transitions()
        assert {("new", "published")} == {(data.source, data.target) for data in transitions}

    def test_field_all_transitions_works(self):
        transitions = self.model.get_all_state_transitions()
        assert {("new", "published"), ("published", "sticked")} == {(data.source, data.target) for data in transitions}
