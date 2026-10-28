from __future__ import annotations

import typing
from itertools import chain

import graphviz
from django.apps import apps
from django.core.management.base import BaseCommand
from django.utils.encoding import force_str

import django_fsm as fsm

if typing.TYPE_CHECKING:  # pragma: no cover
    from argparse import ArgumentParser
    from collections.abc import Sequence

    from django.db import models


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
            help=f"Layout to be used by GraphViz for visualization: {graphviz.ENGINES}.",
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

    def handle(self, *args: str, **options: typing.Any) -> None:
        fields_data: list[tuple[fsm.FSMFieldMixin, type[models.Model]]] = []
        if args:
            for arg in args:
                match arg.split("."):
                    case [app_label]:
                        app = apps.get_app_config(app_label)
                        for model in app.get_models():
                            fields_data += self.all_fsm_fields_data(model)
                    case [app_label, model_name]:
                        model = apps.get_model(app_label, model_name)
                        fields_data += self.all_fsm_fields_data(model)
                    case [app_label, model_name, field_name]:
                        model = apps.get_model(app_label, model_name)
                        fields_data += [self.one_fsm_fields_data(model, field_name)]
        else:
            for model in apps.get_models():
                fields_data += self.all_fsm_fields_data(model)

        dotdata = self.generate_dot(fields_data, ignore_transitions=options["exclude"].split(","))

        if outputfile := options["outputfile"]:
            filename, graph_format = outputfile.rsplit(".", 1)

            dotdata.engine = options["layout"]
            dotdata.format = graph_format
            dotdata.render(filename)
        else:
            self.stdout.write(str(dotdata))

    def generate_dot(  # noqa: C901, PLR0912, PLR0915
        self,
        fields_data: Sequence[tuple[fsm.FSMFieldMixin, type[models.Model]]],
        ignore_transitions: Sequence[str] | None = None,
    ) -> graphviz.Digraph:
        ignore_transitions = ignore_transitions or []
        result = graphviz.Digraph()

        for field, model in fields_data:
            sources: set[tuple[str, fsm._StateValue, str]] = set()
            targets: set[tuple[str, fsm._StateValue, str]] = set()
            edges: set[tuple[str, str, tuple[tuple[str, str], ...]]] = set()
            any_targets: set[tuple[fsm._StateValue, fsm.Transition]] = set()
            any_except_targets: set[tuple[fsm._StateValue, fsm.Transition]] = set()

            # dump nodes and edges
            for transition in field.get_all_transitions(model):
                if transition.name in ignore_transitions:
                    continue

                _targets = list(
                    (state for state in transition.target.allowed_states)
                    if isinstance(transition.target, fsm.GET_STATE | fsm.RETURN_VALUE)
                    else (transition.target,)
                )
                source_name_pair = (
                    (
                        (state, self.node_name(field, state))
                        for state in transition.source.allowed_states
                    )
                    if isinstance(transition.source, fsm.GET_STATE | fsm.RETURN_VALUE)
                    else ((transition.source, self.node_name(field, transition.source)),)
                )

                for source, source_name in source_name_pair:
                    if transition.on_error:
                        on_error_name = self.node_name(field, transition.on_error)
                        targets.add(
                            (
                                on_error_name,
                                transition.on_error,
                                self.node_label(field, transition.on_error),
                            )
                        )
                        on_error_attrs = {
                            "style": "dotted",
                            **self.get_transition_edge_attrs(transition),
                        }
                        edges.add(
                            (source_name, on_error_name, tuple(sorted(on_error_attrs.items())))
                        )

                    for target in _targets:
                        if transition.source == fsm.ANY_STATE:
                            any_targets.add((target, transition))
                        elif transition.source == fsm.ANY_OTHER_STATE:
                            any_except_targets.add((target, transition))
                        else:
                            target_name = self.node_name(field, target)
                            sources.add((source_name, source, self.node_label(field, source)))
                            targets.add((target_name, target, self.node_label(field, target)))
                            edge_attrs = {
                                "label": transition.name,
                                **self.get_transition_edge_attrs(transition),
                            }
                            edges.add((source_name, target_name, tuple(sorted(edge_attrs.items()))))

            targets.update(
                {
                    (self.node_name(field, target), target, self.node_label(field, target))
                    for target, _transition in chain(any_targets, any_except_targets)
                }
            )
            for target, transition in any_targets:
                target_name = self.node_name(field, target)
                all_nodes = sources | targets
                for source_name, source_state, label in all_nodes:
                    sources.add((source_name, source_state, label))
                    edge_attrs = {
                        "label": transition.name,
                        **self.get_transition_edge_attrs(transition),
                    }
                    edges.add((source_name, target_name, tuple(sorted(edge_attrs.items()))))

            for target, transition in any_except_targets:
                target_name = self.node_name(field, target)
                all_nodes = sources | targets
                all_nodes.remove((target_name, target, self.node_label(field, target)))
                for source_name, source_state, label in all_nodes:
                    sources.add((source_name, source_state, label))
                    edge_attrs = {
                        "label": transition.name,
                        **self.get_transition_edge_attrs(transition),
                    }
                    edges.add((source_name, target_name, tuple(sorted(edge_attrs.items()))))

            # construct subgraph
            opts = field.model._meta
            subgraph = graphviz.Digraph(
                name=f"cluster_{opts.app_label}_{opts.object_name}_{field.name}",
                graph_attr={"label": f"{opts.app_label}.{opts.object_name}.{field.name}"},
            )

            final_states = targets - sources
            for name, state, label in final_states:
                node_attrs = {
                    "shape": "doublecircle",
                    **self.get_state_node_attrs(field, state, label),
                }
                subgraph.node(name, label=label, **node_attrs)

            for name, state, label in (sources | targets) - final_states:
                node_attrs = {"shape": "circle", **self.get_state_node_attrs(field, state, label)}
                subgraph.node(name, label=label, **node_attrs)
                # Adding initial state notation
                if field.default and label == field.default:
                    initial_name = self.node_name(field, "_initial")
                    subgraph.node(name=initial_name, label="", shape="point")
                    subgraph.edge(tail_name=initial_name, head_name=name)

            for source_name, target_name, attrs in edges:
                subgraph.edge(tail_name=source_name, head_name=target_name, **dict(attrs))

            result.subgraph(subgraph)

        return result

    @staticmethod
    def all_fsm_fields_data(
        model: type[models.Model],
    ) -> list[tuple[fsm.FSMFieldMixin, type[models.Model]]]:
        return [
            (field, model)
            for field in model._meta.get_fields()
            if isinstance(field, fsm.FSMFieldMixin)
        ]

    @staticmethod
    def one_fsm_fields_data(
        model: type[models.Model], field_name: str
    ) -> tuple[fsm.FSMFieldMixin, type[models.Model]]:
        field = model._meta.get_field(field_name)
        if not isinstance(field, fsm.FSMFieldMixin):
            raise LookupError(f"{field_name} is not an FSMField")  # noqa: TRY004
        return (field, model)

    # Public extension points
    @staticmethod
    def node_name(field: fsm.FSMFieldMixin, state: fsm._StateValue) -> str:
        opts = field.model._meta
        assert opts.verbose_name
        return "{}.{}.{}.{}".format(
            opts.app_label, opts.verbose_name.replace(" ", "_"), field.name, state
        )

    @staticmethod
    def node_label(field: fsm.FSMFieldMixin, state: fsm._StateValue | None) -> str:
        if hasattr(field, "choices") and field.choices:
            state = dict(field.choices).get(state)
        return force_str(state)

    @staticmethod
    def get_transition_edge_attrs(transition: fsm.Transition) -> dict[str, str]:  # noqa: ARG004
        """Extra GraphViz edge attrs for a transition's arrow(s).

        No default styling is provided. Override this method in a Command
        subclass - e.g. from an app listed before django_fsm in
        INSTALLED_APPS - to color/style edges, e.g. by `transition.name`.
        """
        return {}

    @staticmethod
    def get_state_node_attrs(
        field: fsm.FSMFieldMixin,  # noqa: ARG004
        state: fsm._StateValue,  # noqa: ARG004
        label: str,  # noqa: ARG004
    ) -> dict[str, str]:
        """Extra GraphViz node attrs for a state's node.

        No default styling is provided: a state can be the target of several
        transitions, so there is no single transition to derive its styling
        from automatically. Override this method to color/shape nodes, e.g.
        by looking `state` up in your own color map.
        """
        return {}
