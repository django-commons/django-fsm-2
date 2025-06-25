from __future__ import annotations

from django.core.management import call_command
from django.test import TestCase

from django_fsm.management.commands.graph_transitions import get_graphviz_layouts


class GraphTransitionsCommandTest(TestCase):
    MODELS_TO_TEST = [
        "testapp.Application",
        "testapp.FKApplication",
    ]

    def test_app(self):
        call_command("graph_transitions", "testapp")

    def test_single_model(self):
        for model in self.MODELS_TO_TEST:
            call_command("graph_transitions", model)

    def test_single_model_with_layouts(self):
        for model in self.MODELS_TO_TEST:
            for layout in get_graphviz_layouts():
                call_command("graph_transitions", "-l", layout, model)

    def test_exclude(self):
        for model in self.MODELS_TO_TEST:
            call_command("graph_transitions", "-e", "standard,no_target", model)
