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

    def test_transitions_collected_through_inheritance(self) -> None:
        class Base(models.Model):
            state = fsm.FSMField(default="new")

            class Meta:
                app_label = "testapp"

            @fsm.transition(field=state, source="new", target="a")
            def to_a(self) -> None:
                pass

        class MultiTable(Base):
            class Meta:
                app_label = "testapp"

            @fsm.transition(field="state", source="a", target="b")
            def to_b(self) -> None:
                pass

        class Proxy(Base):
            class Meta:
                app_label = "testapp"
                proxy = True

            @fsm.transition(field="state", source="a", target="c")
            def to_c(self) -> None:
                pass

        class Abstract(models.Model):
            state = fsm.FSMField(default="new")

            class Meta:
                app_label = "testapp"
                abstract = True

            @fsm.transition(field=state, source="new", target="a")
            def to_a(self) -> None:
                pass

        class Child(Abstract):
            class Meta:
                app_label = "testapp"

        class ChildWithTransition(Abstract):
            class Meta:
                app_label = "testapp"

            @fsm.transition(field="state", source="a", target="d")
            def to_d(self) -> None:
                pass

        expected = {
            Base: (["to_a"], []),
            MultiTable: (["to_a", "to_b"], ["to_b"]),
            Proxy: (["to_a", "to_c"], ["to_c"]),
            Child: (["to_a"], []),
            ChildWithTransition: (["to_a", "to_d"], ["to_d"]),
        }
        for model, (all_names, available_names) in expected.items():
            all_transitions = model().get_all_state_transitions()  # type: ignore[attr-defined]
            available = model(state="a").get_available_state_transitions()  # type: ignore[attr-defined]

            assert sorted(transition.name for transition in all_transitions) == all_names, model
            assert sorted(transition.name for transition in available) == available_names, model
