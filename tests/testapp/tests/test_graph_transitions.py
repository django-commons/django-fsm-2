from __future__ import annotations

import os
import tempfile
import typing
from io import StringIO
from pathlib import Path

import graphviz
import pytest
from django.core.exceptions import FieldDoesNotExist
from django.core.management import call_command
from django.test import TestCase

from django_fsm.management.commands.graph_transitions import node_label
from django_fsm.management.commands.graph_transitions import node_name
from tests.testapp.models import Application
from tests.testapp.models import BlogPost
from tests.testapp.models import BlogPostState
from tests.testapp.tests.test_model_create_with_generic import Task
from tests.testapp.tests.test_model_create_with_generic import TaskState


class GraphTransitionsCommandTest(TestCase):
    MODELS_TO_TEST = [
        "testapp.Application",
        "testapp.FKApplication",
    ]

    EXTENSIONS_TO_TEST = ["png", "jpg", "jpeg"]

    def test_node_name(self):
        assert node_name(Task.state.field, TaskState.DONE) == "testapp.task.state.done"
        assert node_name(BlogPost.state.field, BlogPostState.NEW) == "testapp.blog_post.state.0"

    def test_node_label(self):
        assert node_label(Application.state.field, "new") == "new"
        assert (
            node_label(BlogPost.state.field, BlogPostState.PUBLISHED.value)
            == BlogPostState.PUBLISHED.label
        )
        # choices is not declared, fallbacking to the value instead
        assert node_label(Task.state.field, TaskState.DONE.value) == TaskState.DONE.value

    def _call_command(self, *args: typing.Any, **kwargs: typing.Any) -> str:
        out = StringIO()
        call_command("graph_transitions", *args, **kwargs, stdout=out)
        return out.getvalue()

    def test_all_models(self):
        self._call_command()

    def test_app(self):
        self._call_command("testapp")

    def test_app_fail(self):
        with pytest.raises(LookupError):
            self._call_command("unknown_app")

    def test_single_model(self):
        for model in self.MODELS_TO_TEST:
            output = self._call_command(model)
            assert model in output
            for excluded_model in self.MODELS_TO_TEST:
                if model != excluded_model:
                    assert excluded_model not in output

    def test_single_model_fail(self):
        with pytest.raises(LookupError):
            self._call_command("testapp.UnknownModel")

    def test_single_model_with_layouts(self):
        for model in self.MODELS_TO_TEST:
            for layout in graphviz.ENGINES:
                self._call_command("-l", layout, model)

    def test_single_model_with_output(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            previous_cwd = os.getcwd()
            try:
                # The command writes relative paths, so isolate it in a temp dir.
                os.chdir(tmp_dir)
                export_dir = Path("exports")
                export_dir.mkdir()
                for model in self.MODELS_TO_TEST:
                    for extension in self.EXTENSIONS_TO_TEST:
                        my_file = export_dir / f"{model}.{extension}"
                        self._call_command("-o", my_file, model)
                        assert my_file.exists()
            finally:
                os.chdir(previous_cwd)

    def test_single_model_exclude(self):
        excluded_transitions = ["standard", "no_target"]
        for model in self.MODELS_TO_TEST:
            output = self._call_command("-e", ",".join(excluded_transitions), model)
            for excluded_t in excluded_transitions:
                assert excluded_t not in output

    def test_single_field(self):
        """Test that specifying app.model.field filters to only that field."""
        output = self._call_command("testapp.MultiStateApplication.another_state")

        assert "testapp.multi_state_application.another_state" in output
        assert "testapp.application.state" not in output

    def test_single_field_fail(self):
        with pytest.raises((LookupError, FieldDoesNotExist)):
            self._call_command("testapp.MultiStateApplication.unknown_field")

        with pytest.raises(LookupError):
            self._call_command("testapp.MultiStateApplication.id")

    def test_output_contains_subgraph_label(self):  # noqa: PLR0915
        output = self._call_command("testapp.Application")

        assert "subgraph cluster_testapp_Application_state {" in output
        assert 'graph [label="testapp.Application.state"]' in output
        assert '"testapp.application.state.new" [label=new shape=circle]' in output
        assert '"testapp.application.state._initial" [label="" shape=point]' in output
        assert '"testapp.application.state._initial" -> "testapp.application.state.new"' in output
        assert '"testapp.application.state.failed" [label=failed shape=circle]' in output
        assert '"testapp.application.state.None" [label=None shape=circle]' in output
        assert '"testapp.application.state.blocked" [label=blocked shape=circle]' in output
        assert '"testapp.application.state.hidden" [label=hidden shape=circle]' in output
        assert '"testapp.application.state.rejected" [label=rejected shape=circle]' in output
        assert '"testapp.application.state.moderated" [label=moderated shape=circle]' in output
        assert '"testapp.application.state.published" [label=published shape=circle]' in output
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.rejected" [label=get_state]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.hidden" -> "testapp.application.state.blocked" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.published" -> "testapp.application.state.rejected" [label=get_state_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.hidden" -> "testapp.application.state.published" [label=get_state_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.published" [label=on_error]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.published" [label=get_state_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.rejected" -> "testapp.application.state.rejected" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.None" -> "testapp.application.state.published" [label=get_state_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.moderated" -> "testapp.application.state.hidden" [label=any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.published" -> "testapp.application.state.blocked" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.moderated" -> "testapp.application.state.moderated" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.moderated" -> "testapp.application.state.rejected" [label=get_state_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.failed" -> "testapp.application.state.blocked" [label=return_value_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.rejected" -> "testapp.application.state.published" [label=get_state_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.failed" -> "testapp.application.state.moderated" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.hidden" -> "testapp.application.state.rejected" [label=get_state_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.hidden" [label=any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.moderated" [label=return_value]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.blocked" -> "testapp.application.state.published" [label=get_state_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.moderated" -> "testapp.application.state.published" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.moderated" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.published" -> "testapp.application.state.moderated" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.blocked" [label=return_value]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.None" -> "testapp.application.state.hidden" [label=any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.failed" -> "testapp.application.state.blocked" [label=any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.blocked" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.failed" -> "testapp.application.state.published" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.None" -> "testapp.application.state.moderated" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.published" -> "testapp.application.state.blocked" [label=return_value_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.published" -> "testapp.application.state.None" [label=no_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.blocked" -> "testapp.application.state.rejected" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.None" -> "testapp.application.state.blocked" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.rejected" -> "testapp.application.state.hidden" [label=any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.published" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.failed" -> "testapp.application.state.moderated" [label=return_value_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.published" -> "testapp.application.state.published" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.moderated" -> "testapp.application.state.blocked" [label=return_value_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.None" -> "testapp.application.state.published" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.blocked" -> "testapp.application.state.hidden" [label=any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.published" -> "testapp.application.state.blocked" [label=any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.failed" [style=dotted]'
            in output
        )
        assert (
            '"testapp.application.state.blocked" -> "testapp.application.state.moderated" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.failed" -> "testapp.application.state.rejected" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.rejected" -> "testapp.application.state.blocked" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.published" -> "testapp.application.state.moderated" [label=return_value_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.rejected" [label=get_state_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.hidden" -> "testapp.application.state.blocked" [label=return_value_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.hidden" -> "testapp.application.state.moderated" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.published" [label=get_state]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.None" -> "testapp.application.state.rejected" [label=get_state_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.blocked" -> "testapp.application.state.blocked" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.moderated" -> "testapp.application.state.blocked" [label=any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.hidden" -> "testapp.application.state.blocked" [label=any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.published" -> "testapp.application.state.rejected" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.hidden" -> "testapp.application.state.published" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.rejected" -> "testapp.application.state.moderated" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.blocked" [label=any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.failed" [style=dotted]'
            in output
        )
        assert (
            '"testapp.application.state.failed" -> "testapp.application.state.published" [label=get_state_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.rejected" -> "testapp.application.state.blocked" [label=return_value_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.blocked" -> "testapp.application.state.rejected" [label=get_state_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.None" -> "testapp.application.state.blocked" [label=any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.hidden" -> "testapp.application.state.moderated" [label=return_value_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.moderated" [label=return_value_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.moderated" -> "testapp.application.state.rejected" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.blocked" [label=return_value_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.None" -> "testapp.application.state.moderated" [label=return_value_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.rejected" -> "testapp.application.state.published" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.published" [label=standard]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.hidden" -> "testapp.application.state.rejected" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.None" -> "testapp.application.state.blocked" [label=return_value_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.rejected" -> "testapp.application.state.blocked" [label=any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.new" -> "testapp.application.state.rejected" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.failed" -> "testapp.application.state.rejected" [label=get_state_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.blocked" -> "testapp.application.state.published" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.rejected" -> "testapp.application.state.moderated" [label=return_value_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.moderated" -> "testapp.application.state.published" [label=get_state_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.failed" -> "testapp.application.state.hidden" [label=any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.None" -> "testapp.application.state.rejected" [label=get_state_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.blocked" -> "testapp.application.state.blocked" [label=any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.failed" -> "testapp.application.state.blocked" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.moderated" -> "testapp.application.state.blocked" [label=return_value_any_source]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.blocked" -> "testapp.application.state.moderated" [label=return_value_any_source_except_target]'  # noqa: E501
            in output
        )
        assert (
            '"testapp.application.state.published" -> "testapp.application.state.hidden" [label=any_source_except_target]'  # noqa: E501
            in output
        )
