from __future__ import annotations

from itertools import chain

import graphviz
from django.apps import apps
from django.core.management.base import BaseCommand
from django.utils.encoding import force_str

from django_fsm import GET_STATE
from django_fsm import RETURN_VALUE
from django_fsm import FSMFieldMixin


def all_fsm_fields_data(model):
    return [(field, model) for field in model._meta.get_fields() if isinstance(field, FSMFieldMixin)]


def node_name(field, state) -> str:
    opts = field.model._meta
    return "{}.{}.{}.{}".format(opts.app_label, opts.verbose_name.replace(" ", "_"), field.name, state)


def node_label(field, state: str | None) -> str:
    if isinstance(state, (int, bool)) and hasattr(field, "choices") and field.choices:
        state = dict(field.choices).get(state)
    return force_str(state)


def generate_dot(fields_data, ignore_transitions: list[str] | None = None):  # noqa: C901, PLR0912
    ignore_transitions = ignore_transitions or []
    result = graphviz.Digraph()

    for field, model in fields_data:
        sources, targets, edges, any_targets, any_except_targets = set(), set(), set(), set(), set()

        # dump nodes and edges
        for transition in field.get_all_transitions(model):
            if transition.name in ignore_transitions:
                continue

            _targets = list(
                (state for state in transition.target.allowed_states)
                if isinstance(transition.target, (GET_STATE, RETURN_VALUE))
                else (transition.target,)
            )
            source_name_pair = (
                ((state, node_name(field, state)) for state in transition.source.allowed_states)
                if isinstance(transition.source, (GET_STATE, RETURN_VALUE))
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
                        add_transition(source, target, transition.name, source_name, field, sources, targets, edges)

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
            # Adding initial state notation
            if field.default and label == field.default:
                initial_name = node_name(field, "_initial")
                subgraph.node(name=initial_name, label="", shape="point")
                subgraph.edge(initial_name, name)
        for source_name, target_name, attrs in edges:
            subgraph.edge(source_name, target_name, **dict(attrs))

        result.subgraph(subgraph)

    return result


def add_transition(transition_source, transition_target, transition_name, source_name, field, sources, targets, edges):
    target_name = node_name(field, transition_target)
    sources.add((source_name, node_label(field, transition_source)))
    targets.add((target_name, node_label(field, transition_target)))
    edges.add((source_name, target_name, (("label", transition_name),)))


def get_graphviz_layouts():
    try:
        import graphviz
    except ModuleNotFoundError:
        return {"sfdp", "circo", "twopi", "dot", "neato", "fdp", "osage", "patchwork"}
    else:
        return graphviz.ENGINES


class Command(BaseCommand):
    help = "Creates a GraphViz dot file with transitions for selected fields"

    def add_arguments(self, parser):
        parser.add_argument(
            "--output",
            "-o",
            action="store",
            dest="outputfile",
            help="Render output file. Type of output dependent on file extensions. Use png or jpg to render graph to image.",
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
            help="Ignore transitions with this name.",
        )
        parser.add_argument("args", nargs="*", help=("[appname[.model[.field]]]"))

    def render_output(self, graph, **options):
        filename, graph_format = options["outputfile"].rsplit(".", 1)

        graph.engine = options["layout"]
        graph.format = graph_format
        graph.render(filename)

    def handle(self, *args, **options):
        fields_data = []
        if len(args) != 0:
            for arg in args:
                field_spec = arg.split(".")

                if len(field_spec) == 1:
                    app = apps.get_app_config(field_spec[0])
                    for model in apps.get_models(app):
                        fields_data += all_fsm_fields_data(model)
                if len(field_spec) == 2:  # noqa: PLR2004
                    model = apps.get_model(field_spec[0], field_spec[1])
                    fields_data += all_fsm_fields_data(model)
                if len(field_spec) == 3:  # noqa: PLR2004
                    model = apps.get_model(field_spec[0], field_spec[1])
                    fields_data += all_fsm_fields_data(model)
        else:
            for model in apps.get_models():
                fields_data += all_fsm_fields_data(model)

        dotdata = generate_dot(fields_data, ignore_transitions=options["exclude"].split(","))

        if options["outputfile"]:
            self.render_output(dotdata, **options)
        else:
            print(dotdata)  # noqa: T201
