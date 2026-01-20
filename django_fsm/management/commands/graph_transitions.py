from __future__ import annotations

import typing
from itertools import chain

import graphviz
from django.apps import apps
from django.core.management.base import BaseCommand
from django.utils.encoding import force_str

from django_fsm import GET_STATE
from django_fsm import RETURN_VALUE
from django_fsm import FSMFieldMixin

if typing.TYPE_CHECKING:  # pragma: no cover
    from argparse import ArgumentParser
    from collections.abc import Sequence

    from django.db import models

    from django_fsm import _StateValue


def all_fsm_fields_data(
    model: type[models.Model],
) -> list[tuple[FSMFieldMixin, type[models.Model]]]:
    return [
        (field, model) for field in model._meta.get_fields() if isinstance(field, FSMFieldMixin)
    ]


def one_fsm_fields_data(
    model: type[models.Model], field_name: str
) -> tuple[FSMFieldMixin, type[models.Model]]:
    field = model._meta.get_field(field_name)
    assert isinstance(field, FSMFieldMixin)
    return (field, model)


def node_name(field: FSMFieldMixin, state: _StateValue) -> str:
    opts = field.model._meta
    assert opts.verbose_name
    return "{}.{}.{}.{}".format(
        opts.app_label, opts.verbose_name.replace(" ", "_"), field.name, state
    )


def node_label(field: FSMFieldMixin, state: _StateValue | None) -> str:
    if hasattr(field, "choices") and field.choices:
        state = dict(field.choices).get(state)
    return force_str(state)


def generate_dot(  # noqa: C901, PLR0912
    fields_data: Sequence[tuple[FSMFieldMixin, type[models.Model]]],
    ignore_transitions: Sequence[str] | None = None,
) -> graphviz.Digraph:
    ignore_transitions = ignore_transitions or []
    result = graphviz.Digraph()

    for field, model in fields_data:
        sources: set[tuple[(str, str)]] = set()
        targets: set[tuple[str, str]] = set()
        edges: set[tuple[str, str, tuple[tuple[str, ...]]]] = set()
        any_targets: set[tuple[_StateValue, str]] = set()
        any_except_targets: set[tuple[str, str]] = set()

        # dump nodes and edges
        for transition in field.get_all_transitions(model):
            if transition.name in ignore_transitions:
                continue

            _targets = list(
                (state for state in transition.target.allowed_states)
                if isinstance(transition.target, GET_STATE | RETURN_VALUE)
                else (transition.target,)
            )
            source_name_pair = (
                ((state, node_name(field, state)) for state in transition.source.allowed_states)
                if isinstance(transition.source, GET_STATE | RETURN_VALUE)
                else ((transition.source, node_name(field, transition.source)),)
            )
            for source, source_name in source_name_pair:
                if transition.on_error:
                    on_error_name = node_name(field, transition.on_error)
                    targets.add((on_error_name, node_label(field, transition.on_error)))
                    edges.add((source_name, on_error_name, (("style", "dotted"),)))

                for target in _targets:
                    if transition.source == "*":
                        any_targets.add((target, transition.name))
                    elif transition.source == "+":
                        any_except_targets.add((target, transition.name))
                    else:
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
            {
                (node_name(field, target), node_label(field, target))
                for target, _ in chain(any_targets, any_except_targets)
            }
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
            # Adding initial state notation
            if field.default and label == field.default:
                initial_name = node_name(field, "_initial")
                subgraph.node(name=initial_name, label="", shape="point")
                subgraph.edge(initial_name, name)
        for source_name, target_name, attrs in edges:
            subgraph.edge(source_name, target_name, **dict(attrs))

        result.subgraph(subgraph)

    return result


def add_transition(
    transition_source: _StateValue,
    transition_target: _StateValue,
    transition_name: str,
    source_name: str,
    field: FSMFieldMixin,
    sources: set[tuple[str, str]],
    targets: set[tuple[str, str]],
    edges: set[tuple[str, str, tuple[tuple[str, str], ...]]],
) -> None:
    target_name = node_name(field, transition_target)
    sources.add((source_name, node_label(field, transition_source)))
    targets.add((target_name, node_label(field, transition_target)))
    edges.add((source_name, target_name, (("label", transition_name),)))


def get_graphviz_layouts() -> set[str] | Sequence[str]:
    try:
        import graphviz
    except ModuleNotFoundError:
        return {"sfdp", "circo", "twopi", "dot", "neato", "fdp", "osage", "patchwork"}
    else:
        return graphviz.ENGINES  # type: ignore[no-any-return]


class Command(BaseCommand):
    help = "Creates a GraphViz dot file with transitions for selected fields"

    def add_arguments(self, parser: ArgumentParser) -> None:
        parser.add_argument(
            "--output",
            "-o",
            action="store",
            dest="outputfile",
            help="Render output file. Type of output depends on file extensions."
            "Use png or jpg to render graph to image.",
        )
        parser.add_argument(
            "--layout",
            "-l",
            action="store",
            dest="layout",
            default="dot",
            help=f"Layout to be used by GraphViz for visualization: {get_graphviz_layouts()}.",
        )
        parser.add_argument(
            "--exclude",
            "-e",
            action="store",
            dest="exclude",
            default="",
            help="Ignore transitions with this name.",
        )
        parser.add_argument("args", nargs="*", help=("[appname[.model[.field]]]"))

    def render_output(self, graph: graphviz.Digraph, **options: typing.Any) -> None:
        filename, graph_format = options["outputfile"].rsplit(".", 1)

        graph.engine = options["layout"]
        graph.format = graph_format
        graph.render(filename)

    def handle(self, *args: str, **options: typing.Any) -> None:
        fields_data: list[tuple[FSMFieldMixin, type[models.Model]]] = []
        if args:
            for arg in args:
                match arg.split("."):
                    case [app_label]:
                        app = apps.get_app_config(app_label)
                        for model in app.get_models():
                            fields_data += all_fsm_fields_data(model)
                    case [app_label, model_name]:
                        model = apps.get_model(app_label, model_name)
                        fields_data += all_fsm_fields_data(model)
                    case [app_label, model_name, field_name]:
                        model = apps.get_model(app_label, model_name)
                        fields_data += [one_fsm_fields_data(model, field_name)]
        else:
            for model in apps.get_models():
                fields_data += all_fsm_fields_data(model)

        dotdata = generate_dot(fields_data, ignore_transitions=options["exclude"].split(","))

        outputfile = options["outputfile"]
        if outputfile:
            self.render_output(dotdata, **options)
        else:
            self.stdout.write(str(dotdata))
