from __future__ import annotations

from django.db import models
from django.db.models.signals import class_prepared
from django.test import TestCase
from django.test.utils import isolate_apps

import django_fsm as fsm


def make_model(name: str) -> type[models.Model]:
    def publish(self: models.Model) -> None:
        pass

    meta = type("Meta", (), {"app_label": "testapp"})
    attrs = {
        "__module__": __name__,
        "Meta": meta,
        "state": fsm.FSMField(default="new"),
        "publish": fsm.transition(field="state", source="new", target="published")(publish),
    }
    return type(name, (models.Model,), attrs)


@isolate_apps("tests.testapp")
class ClassPreparedReceiversTest(TestCase):
    def test_new_model_classes_do_not_add_class_prepared_receivers(self) -> None:
        created = [make_model("ReceiverModel0")]
        receivers = len(class_prepared.receivers)

        created.extend(make_model(f"ReceiverModel{index}") for index in range(1, 6))

        assert len(class_prepared.receivers) == receivers

    def test_transitions_collected_for_model_created_at_runtime(self) -> None:
        model = make_model("RuntimeModel")

        transitions = list(model().get_all_state_transitions())  # type: ignore[attr-defined]

        assert [transition.name for transition in transitions] == ["publish"]
