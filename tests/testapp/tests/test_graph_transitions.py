from __future__ import annotations

from io import StringIO

import pytest
from django.core.exceptions import FieldDoesNotExist
from django.core.management import call_command
from django.test import TestCase

from django_fsm.management.commands.graph_transitions import get_graphviz_layouts
from django_fsm.management.commands.graph_transitions import node_label
from tests.testapp.models import BlogPost
from tests.testapp.models import BlogPostState


class GraphTransitionsCommandTest(TestCase):
    MODELS_TO_TEST = [
        "testapp.Application",
        "testapp.FKApplication",
    ]

    def test_node_label(self):
        assert node_label(BlogPost.state.field, BlogPostState.PUBLISHED.value) == BlogPostState.PUBLISHED.label

    def test_app(self):
        call_command("graph_transitions", "testapp")

    def test_app_fail(self):
        with pytest.raises(LookupError):
            call_command("graph_transitions", "unknown_app")

    def test_single_model(self):
        for model in self.MODELS_TO_TEST:
            call_command("graph_transitions", model)

    def test_single_model_fail(self):
        with pytest.raises(LookupError):
            call_command("graph_transitions", "testapp.UnknownModel")

    def test_single_model_with_layouts(self):
        for model in self.MODELS_TO_TEST:
            for layout in get_graphviz_layouts():
                call_command("graph_transitions", "-l", layout, model)

    def test_exclude(self):
        for model in self.MODELS_TO_TEST:
            call_command("graph_transitions", "-e", "standard,no_target", model)

    def test_single_field(self):
        """Test that specifying app.model.field filters to only that field."""
        out = StringIO()
        call_command("graph_transitions", "testapp.MultiStateApplication.another_state", stdout=out)
        output = out.getvalue()

        assert "testapp.multi_state_application.another_state" in output
        assert "testapp.application.state" not in output

    def test_single_field_fail(self):
        with pytest.raises((LookupError, FieldDoesNotExist)):
            call_command("graph_transitions", "testapp.MultiStateApplication.unknown_field")
