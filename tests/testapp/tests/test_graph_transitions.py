from __future__ import annotations

from django.core.management import call_command
from django.test import TestCase

from django_fsm.management.commands.graph_transitions import get_graphviz_layouts


class GraphTransitionsCommandTest(TestCase):
    def test_dummy(self):
        call_command("graph_transitions", "testapp.Application")

    def test_layouts(self):
        for layout in get_graphviz_layouts():
            call_command("graph_transitions", "-l", layout, "testapp.Application")

    def test_fk_dummy(self):
        call_command("graph_transitions", "testapp.FKApplication")

    def test_fk_layouts(self):
        for layout in get_graphviz_layouts():
            call_command("graph_transitions", "-l", layout, "testapp.FKApplication")
