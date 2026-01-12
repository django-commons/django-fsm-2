"""
Management command to generate GraphViz diagrams of FSM transitions.

This command creates visual representations of state machines defined
using django-fsm-2 fields. It outputs GraphViz DOT format which can be
rendered to various image formats.

Usage:
    # Output DOT to stdout for all models
    ./manage.py graph_transitions

    # Render to PNG file
    ./manage.py graph_transitions -o transitions.png

    # Render specific app's models
    ./manage.py graph_transitions myapp -o myapp_transitions.png

    # Render specific model
    ./manage.py graph_transitions myapp.MyModel -o model.png

    # Use different layout algorithm
    ./manage.py graph_transitions -l neato -o transitions.png

Requirements:
    pip install graphviz
"""

from __future__ import annotations

from itertools import chain
from typing import TYPE_CHECKING
from typing import Any

import graphviz
from django.apps import apps
from django.core.management.base import BaseCommand
from django.core.management.base import CommandParser
from django.utils.encoding import force_str

from django_fsm_rx import GET_STATE
from django_fsm_rx import RETURN_VALUE
from django_fsm_rx import FSMFieldMixin

if TYPE_CHECKING:
    from django.db.models import Model


def all_fsm_fields_data(model: type[Model]) -> list[tuple[FSMFieldMixin, type[Model]]]:
    """
    Get all FSM fields defined on a model.

    Args:
        model: The Django model class to inspect.

    Returns:
        List of (field, model) tuples for each FSM field found.
    """
    return [(field, model) for field in model._meta.get_fields() if isinstance(field, FSMFieldMixin)]


def node_name(field: FSMFieldMixin, state: str | int) -> str:
    """
    Generate a unique node name for a state in the graph.

    Args:
        field: The FSM field.
        state: The state value.

    Returns:
        A unique identifier string for the node.
    """
    opts = field.model._meta
    return "{}.{}.{}.{}".format(opts.app_label, opts.verbose_name.replace(" ", "_"), field.name, state)


def node_label(field: FSMFieldMixin, state: str | int) -> str:
    """
    Generate the display label for a state node.

    For integer/boolean states with choices, returns the choice label.
    Otherwise returns the state value as a string.

    Args:
        field: The FSM field.
        state: The state value.

    Returns:
        Human-readable label for the state.
    """
    if isinstance(state, (int, bool)) and hasattr(field, "choices") and field.choices:
        label = dict(field.choices).get(state)
        if label is not None:
            return force_str(label)
    return str(state)


def generate_dot(  # noqa: C901
    fields_data: list[tuple[FSMFieldMixin, type[Model]]],
    exclude: set[str] | None = None,
) -> graphviz.Digraph:
    """
    Generate a GraphViz Digraph from FSM field data.

    Creates a directed graph showing states as nodes and transitions
    as edges. Each FSM field gets its own subgraph cluster.

    Args:
        fields_data: List of (field, model) tuples to visualize.
        exclude: Set of transition names to exclude from the graph.

    Returns:
        A graphviz.Digraph object ready for rendering.
    """
    result = graphviz.Digraph()
    exclude = exclude or set()

    for field, model in fields_data:
        sources: set[tuple[str, str]] = set()
        targets: set[tuple[str, str]] = set()
        edges: set[tuple[str, str, tuple[tuple[str, str], ...]]] = set()
        any_targets: set[tuple[str | int, str]] = set()
        any_except_targets: set[tuple[str | int, str]] = set()

        # dump nodes and edges
        for transition in field.get_all_transitions(model):
            # Skip excluded transitions
            if transition.name in exclude:
                continue
            if transition.source == "*":
                any_targets.add((transition.target, transition.name))
            elif transition.source == "+":
                any_except_targets.add((transition.target, transition.name))
            else:
                # Handle transitions with no target (target=None means state unchanged)
                if transition.target is None:
                    continue
                # Handle GET_STATE/RETURN_VALUE with allowed_states
                if isinstance(transition.target, (GET_STATE, RETURN_VALUE)):
                    if transition.target.allowed_states:
                        _targets: tuple[Any, ...] = tuple(state for state in transition.target.allowed_states)
                    else:
                        # No allowed_states specified - skip graphing dynamic targets
                        continue
                else:
                    _targets = (transition.target,)
                source_name_pair: tuple[tuple[Any, str], ...] = (
                    tuple((state, node_name(field, state)) for state in transition.source.allowed_states)
                    if isinstance(transition.source, (GET_STATE, RETURN_VALUE))
                    else ((transition.source, node_name(field, transition.source)),)
                )
                for source, source_name in source_name_pair:
                    if transition.on_error:
                        on_error_name = node_name(field, transition.on_error)
                        targets.add((on_error_name, node_label(field, transition.on_error)))
                        edges.add((source_name, on_error_name, (("style", "dotted"),)))
                    for target in _targets:
                        add_transition(
                            source,
                            target,
                            transition.name,
                            source_name,
                            field,
                            sources,
                            targets,
                            edges,
                        )

        targets.update(
            {(node_name(field, target), node_label(field, target)) for target, _ in chain(any_targets, any_except_targets)}
        )
        for target, name in any_targets:
            target_name = node_name(field, target)
            all_nodes = sources | targets
            for source_name, label in all_nodes:
                sources.add((source_name, label))
                edges.add((source_name, target_name, (("label", name),)))

        for target, name in any_except_targets:
            target_name = node_name(field, target)
            all_nodes = sources | targets
            all_nodes.remove((target_name, node_label(field, target)))
            for source_name, label in all_nodes:
                sources.add((source_name, label))
                edges.add((source_name, target_name, (("label", name),)))

        # construct subgraph
        opts = field.model._meta
        subgraph = graphviz.Digraph(
            name=f"cluster_{opts.app_label}_{opts.object_name}_{field.name}",
            graph_attr={"label": f"{opts.app_label}.{opts.object_name}.{field.name}"},
        )

        final_states = targets - sources
        for name, label in final_states:
            subgraph.node(name, label=label, shape="doublecircle")
        for name, label in (sources | targets) - final_states:
            subgraph.node(name, label=label, shape="circle")
            if field.default:  # Adding initial state notation
                if label == field.default:
                    initial_name = node_name(field, "_initial")
                    subgraph.node(name=initial_name, label="", shape="point")
                    subgraph.edge(initial_name, name)
        for source_name, target_name, attrs in edges:
            subgraph.edge(source_name, target_name, **dict(attrs))

        result.subgraph(subgraph)

    return result


def add_transition(
    transition_source: str | int,
    transition_target: str | int,
    transition_name: str,
    source_name: str,
    field: FSMFieldMixin,
    sources: set[tuple[str, str]],
    targets: set[tuple[str, str]],
    edges: set[tuple[str, str, tuple[tuple[str, str], ...]]],
) -> None:
    """
    Add a transition edge to the graph data structures.

    Args:
        transition_source: The source state value.
        transition_target: The target state value.
        transition_name: The name of the transition method.
        source_name: The graph node name for the source.
        field: The FSM field being graphed.
        sources: Set of source nodes to update.
        targets: Set of target nodes to update.
        edges: Set of edges to update.
    """
    target_name = node_name(field, transition_target)
    sources.add((source_name, node_label(field, transition_source)))
    targets.add((target_name, node_label(field, transition_target)))
    edges.add((source_name, target_name, (("label", transition_name),)))


def get_graphviz_layouts() -> set[str]:
    """
    Get available GraphViz layout engines.

    Returns:
        Set of available layout engine names.
    """
    try:
        import graphviz

        return graphviz.backend.ENGINES  # type: ignore[return-value]
    except Exception:
        return {"sfdp", "circo", "twopi", "dot", "neato", "fdp", "osage", "patchwork"}


class Command(BaseCommand):
    """
    Django management command to generate FSM transition graphs.

    Creates GraphViz visualizations of state machines defined using
    django-fsm-2. Supports filtering by app, model, or field and can
    output to various image formats.

    Examples:
        # Print DOT to stdout
        ./manage.py graph_transitions

        # Generate PNG
        ./manage.py graph_transitions -o states.png

        # Specific app
        ./manage.py graph_transitions myapp -o myapp.png

        # Specific model
        ./manage.py graph_transitions myapp.Order -o order.png
    """

    help = "Creates a GraphViz dot file with transitions for selected fields"

    def add_arguments(self, parser: CommandParser) -> None:
        """Add command arguments."""
        parser.add_argument(
            "--output",
            "-o",
            action="store",
            dest="outputfile",
            help=("Render output file. Type of output dependent on file extensions. Use png or jpg to render graph to image."),
        )
        parser.add_argument(
            "--layout",
            "-l",
            action="store",
            dest="layout",
            default="dot",
            help=f"Layout to be used by GraphViz for visualization. Layouts: {get_graphviz_layouts()}.",
        )
        parser.add_argument(
            "--exclude",
            "-e",
            action="store",
            dest="exclude",
            default="",
            help="Comma-separated list of transition names to exclude from the graph.",
        )
        parser.add_argument("args", nargs="*", help=("[appname[.model[.field]]]"))

    def render_output(self, graph: graphviz.Digraph, **options: Any) -> None:
        """
        Render the graph to a file.

        Args:
            graph: The GraphViz graph to render.
            **options: Command options including 'outputfile' and 'layout'.
        """
        filename, format = options["outputfile"].rsplit(".", 1)

        graph.engine = options["layout"]
        graph.format = format
        graph.render(filename)

    def handle(self, *args: Any, **options: Any) -> None:
        """
        Execute the command.

        Args:
            *args: Positional arguments (app.model.field specifications).
            **options: Command options.
        """
        # Parse exclude option
        exclude: set[str] = set()
        if options.get("exclude"):
            exclude = {t.strip() for t in options["exclude"].split(",") if t.strip()}

        fields_data: list[tuple[FSMFieldMixin, type[Model]]] = []
        if len(args) != 0:
            for arg in args:
                field_spec = arg.split(".")

                if len(field_spec) == 1:
                    app = apps.get_app_config(field_spec[0])
                    models = app.get_models()
                    for model in models:
                        fields_data += all_fsm_fields_data(model)
                elif len(field_spec) == 2:
                    model = apps.get_model(field_spec[0], field_spec[1])
                    fields_data += all_fsm_fields_data(model)
                elif len(field_spec) == 3:
                    model = apps.get_model(field_spec[0], field_spec[1])
                    field_name = field_spec[2]
                    # Filter to only the specified field
                    found = False
                    for field, mdl in all_fsm_fields_data(model):
                        if field.name == field_name:
                            fields_data.append((field, mdl))
                            found = True
                            break
                    if not found:
                        # Field not found - this will raise FieldDoesNotExist
                        model._meta.get_field(field_name)
        else:
            for model in apps.get_models():
                fields_data += all_fsm_fields_data(model)
        dotdata = generate_dot(fields_data, exclude=exclude)

        if options["outputfile"]:
            self.render_output(dotdata, **options)
        else:
            self.stdout.write(str(dotdata))
