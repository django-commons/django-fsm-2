from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

from django_fsm import FSMField
from django_fsm import Transition
from django_fsm import TransitionNotAllowed
from django_fsm import can_proceed
from django_fsm import transition
from django_fsm.signals import post_transition
from django_fsm.signals import pre_transition


class SimpleBlogPost(models.Model):
    state = FSMField(default="new")

    @transition(field=state, source="new", target="published")
    def publish(self):
        pass

    @transition(source="published", field=state)
    def notify_all(self):
        pass

    @transition(source="published", target="hidden", field=state)
    def hide(self):
        pass

    @transition(source="new", target="removed", field=state)
    def remove(self):
        raise Exception("Upss")

    @transition(source=["published", "hidden"], target="stolen", field=state)
    def steal(self):
        pass

    @transition(source="*", target="moderated", field=state)
    def moderate(self):
        pass

    @transition(source="+", target="blocked", field=state)
    def block(self):
        pass

    @transition(source="*", target="", field=state)
    def empty(self):
        pass


class AdvancedBlogPost(SimpleBlogPost):
    @transition(field="state", source="new", target="published")
    def publish(self):
        pass


class FSMFieldTest(TestCase):
    def setUp(self):
        self.model = SimpleBlogPost()

    def test_initial_state_instantiated(self):
        assert self.model.state == "new"

    def test_known_transition_should_succeed(self):
        assert can_proceed(self.model.publish)
        self.model.publish()
        assert self.model.state == "published"

        assert can_proceed(self.model.hide)
        self.model.hide()
        assert self.model.state == "hidden"

    def test_unknown_transition_fails(self):
        assert not can_proceed(self.model.hide)
        with pytest.raises(TransitionNotAllowed):
            self.model.hide()

    def test_state_non_changed_after_fail(self):
        assert can_proceed(self.model.remove)
        with pytest.raises(Exception, match="Upss"):
            self.model.remove()
        assert self.model.state == "new"

    def test_allowed_null_transition_should_succeed(self):
        self.model.publish()
        self.model.notify_all()
        assert self.model.state == "published"

    def test_unknown_null_transition_should_fail(self):
        with pytest.raises(TransitionNotAllowed):
            self.model.notify_all()
        assert self.model.state == "new"

    def test_multiple_source_support_path_1_works(self):
        self.model.publish()
        self.model.steal()
        assert self.model.state == "stolen"

    def test_multiple_source_support_path_2_works(self):
        self.model.publish()
        self.model.hide()
        self.model.steal()
        assert self.model.state == "stolen"

    def test_star_shortcut_succeed(self):
        assert can_proceed(self.model.moderate)
        self.model.moderate()
        assert self.model.state == "moderated"

    def test_plus_shortcut_succeeds_for_other_source(self):
        """Tests that the '+' shortcut succeeds for a source
        other than the target.
        """
        assert can_proceed(self.model.block)
        self.model.block()
        assert self.model.state == "blocked"

    def test_plus_shortcut_fails_for_same_source(self):
        """Tests that the '+' shortcut fails if the source
        equals the target.
        """
        self.model.block()
        assert not can_proceed(self.model.block)
        with pytest.raises(TransitionNotAllowed):
            self.model.block()

    def test_empty_string_target(self):
        self.model.empty()
        assert self.model.state == ""


class StateSignalsTests(TestCase):
    def setUp(self):
        self.model = SimpleBlogPost()
        self.pre_transition_called = False
        self.post_transition_called = False
        pre_transition.connect(self.on_pre_transition, sender=SimpleBlogPost)
        post_transition.connect(self.on_post_transition, sender=SimpleBlogPost)

    def on_pre_transition(self, sender, instance, name, source, target, **kwargs):
        assert instance.state == source
        self.pre_transition_called = True

    def on_post_transition(self, sender, instance, name, source, target, **kwargs):
        assert instance.state == target
        self.post_transition_called = True

    def test_signals_called_on_valid_transition(self):
        self.model.publish()
        assert self.pre_transition_called
        assert self.post_transition_called

    def test_signals_not_called_on_invalid_transition(self):
        with pytest.raises(TransitionNotAllowed):
            self.model.hide()
        assert not self.pre_transition_called
        assert not self.post_transition_called


class LazySenderTests(StateSignalsTests):
    def setUp(self):
        self.model = SimpleBlogPost()
        self.pre_transition_called = False
        self.post_transition_called = False
        pre_transition.connect(self.on_pre_transition, sender="testapp.SimpleBlogPost")
        post_transition.connect(self.on_post_transition, sender="testapp.SimpleBlogPost")


class TestFieldTransitionsInspect(TestCase):
    def setUp(self):
        self.model = SimpleBlogPost()

    def test_transition_are_hashable(self) -> None:
        transition = Transition(
            method=self.model.publish,
            source="new",
            target="published",
            on_error=None,
            conditions=[],
            permission=None,
            custom={},
        )

        assert hash(transition) is not None

    def test_transition_equality(self) -> None:
        for wrong_value in [0, 1, True, False, None]:
            assert (
                Transition(
                    method=AdvancedBlogPost.publish,
                    source="new",
                    target="published",
                    on_error=None,
                    conditions=[],
                    permission=None,
                    custom={},
                )
                != wrong_value
            )

        assert Transition(
            method=AdvancedBlogPost.publish,
            source="new",
            target="published",
            on_error=None,
            conditions=[],
            permission=None,
            custom={},
        ) != Transition(
            method=SimpleBlogPost.publish,
            source="new",
            target="published",
            on_error=None,
            conditions=[],
            permission=None,
            custom={},
        )

        assert Transition(
            method=AdvancedBlogPost.empty,
            source="*",
            target="",
            on_error=None,
            conditions=[],
            permission=None,
            custom={},
        ) == Transition(
            method=SimpleBlogPost.empty,
            source="*",
            target="",
            on_error=None,
            conditions=[],
            permission=None,
            custom={},
        )

    def test_in_operator_for_available_transitions(self):
        # store the generator in a list, so we can reuse the generator and do multiple asserts
        transitions = list(self.model.get_available_state_transitions())

        assert "publish" in transitions
        assert "xyz" not in transitions

        # inline method for faking the name of the transition
        def publish():
            pass

        obj = Transition(
            method=publish,
            source="",
            target="",
            on_error="",
            conditions="",
            permission="",
            custom="",
        )

        assert obj not in transitions

    def test_available_conditions_from_new(self):
        transitions = self.model.get_available_state_transitions()
        actual = {(transition.source, transition.target) for transition in transitions}
        expected = {
            ("*", "moderated"),
            ("new", "published"),
            ("new", "removed"),
            ("*", ""),
            ("+", "blocked"),
        }
        assert actual == expected

    def test_available_conditions_from_published(self):
        self.model.publish()
        transitions = self.model.get_available_state_transitions()
        actual = {(transition.source, transition.target) for transition in transitions}
        expected = {
            ("*", "moderated"),
            ("published", None),
            ("published", "hidden"),
            ("published", "stolen"),
            ("*", ""),
            ("+", "blocked"),
        }
        assert actual == expected

    def test_available_conditions_from_hidden(self):
        self.model.publish()
        self.model.hide()
        transitions = self.model.get_available_state_transitions()
        actual = {(transition.source, transition.target) for transition in transitions}
        expected = {("*", "moderated"), ("hidden", "stolen"), ("*", ""), ("+", "blocked")}
        assert actual == expected

    def test_available_conditions_from_stolen(self):
        self.model.publish()
        self.model.steal()
        transitions = self.model.get_available_state_transitions()
        actual = {(transition.source, transition.target) for transition in transitions}
        expected = {("*", "moderated"), ("*", ""), ("+", "blocked")}
        assert actual == expected

    def test_available_conditions_from_blocked(self):
        self.model.block()
        transitions = self.model.get_available_state_transitions()
        actual = {(transition.source, transition.target) for transition in transitions}
        expected = {("*", "moderated"), ("*", "")}
        assert actual == expected

    def test_available_conditions_from_empty(self):
        self.model.empty()
        transitions = self.model.get_available_state_transitions()
        actual = {(transition.source, transition.target) for transition in transitions}
        expected = {("*", "moderated"), ("*", ""), ("+", "blocked")}
        assert actual == expected

    def test_all_conditions(self):
        transitions = self.model.get_all_state_transitions()

        actual = {(transition.source, transition.target) for transition in transitions}
        expected = {
            ("*", "moderated"),
            ("new", "published"),
            ("new", "removed"),
            ("published", None),
            ("published", "hidden"),
            ("published", "stolen"),
            ("hidden", "stolen"),
            ("*", ""),
            ("+", "blocked"),
        }
        assert actual == expected
