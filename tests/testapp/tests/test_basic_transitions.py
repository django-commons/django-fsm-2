from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

import django_fsm as fsm
from django_fsm.signals import post_transition
from django_fsm.signals import pre_transition

from ..choices import ApplicationState


class SimpleBlogPost(models.Model):
    state = fsm.FSMField(choices=ApplicationState.choices, default=ApplicationState.NEW)

    @fsm.transition(field=state, source=ApplicationState.NEW, target=ApplicationState.PUBLISHED)
    def publish(self):
        pass

    @fsm.transition(source=ApplicationState.PUBLISHED, field=state)
    def notify_all(self):
        pass

    @fsm.transition(source=ApplicationState.PUBLISHED, target=ApplicationState.HIDDEN, field=state)
    def hide(self):
        pass

    @fsm.transition(source=ApplicationState.NEW, target=ApplicationState.REMOVED, field=state)
    def remove(self):
        raise Exception("Upss")

    @fsm.transition(
        source=[ApplicationState.PUBLISHED, ApplicationState.HIDDEN],
        target=ApplicationState.STOLEN,
        field=state,
    )
    def steal(self):
        pass

    @fsm.transition(source=fsm.ANY_STATE, target=ApplicationState.MODERATED, field=state)
    def moderate(self):
        pass

    @fsm.transition(source=fsm.ANY_OTHER_STATE, target=ApplicationState.BLOCKED, field=state)
    def block(self):
        pass

    @fsm.transition(source=fsm.ANY_STATE, target="", field=state)
    def empty(self):
        pass


class AdvancedBlogPost(SimpleBlogPost):
    @fsm.transition(field="state", source=ApplicationState.NEW, target=ApplicationState.PUBLISHED)
    def publish(self):
        pass


class FSMFieldTest(TestCase):
    def setUp(self):
        self.model = SimpleBlogPost()

    def test_initial_state_instantiated(self):
        assert self.model.state == ApplicationState.NEW

    def test_known_transition_should_succeed(self):
        assert fsm.can_proceed(self.model.publish)
        self.model.publish()
        assert self.model.state == ApplicationState.PUBLISHED

        assert fsm.can_proceed(self.model.hide)
        self.model.hide()
        assert self.model.state == ApplicationState.HIDDEN

    def test_unknown_transition_fails(self):
        assert not fsm.can_proceed(self.model.hide)
        with pytest.raises(fsm.TransitionNotAllowed):
            self.model.hide()

    def test_state_non_changed_after_fail(self):
        assert fsm.can_proceed(self.model.remove)
        with pytest.raises(Exception, match="Upss"):
            self.model.remove()
        assert self.model.state == ApplicationState.NEW

    def test_allowed_null_transition_should_succeed(self):
        self.model.publish()
        self.model.notify_all()
        assert self.model.state == ApplicationState.PUBLISHED

    def test_unknown_null_transition_should_fail(self):
        with pytest.raises(fsm.TransitionNotAllowed):
            self.model.notify_all()
        assert self.model.state == ApplicationState.NEW

    def test_multiple_source_support_path_1_works(self):
        self.model.publish()
        self.model.steal()
        assert self.model.state == ApplicationState.STOLEN

    def test_multiple_source_support_path_2_works(self):
        self.model.publish()
        self.model.hide()
        self.model.steal()
        assert self.model.state == ApplicationState.STOLEN

    def test_star_shortcut_succeed(self):
        assert fsm.can_proceed(self.model.moderate)
        self.model.moderate()
        assert self.model.state == ApplicationState.MODERATED

    def test_plus_shortcut_succeeds_for_other_source(self):
        """Tests that the '+' shortcut succeeds for a source
        other than the target.
        """
        assert fsm.can_proceed(self.model.block)
        self.model.block()
        assert self.model.state == ApplicationState.BLOCKED

    def test_plus_shortcut_fails_for_same_source(self):
        """Tests that the '+' shortcut fails if the source
        equals the target.
        """
        self.model.block()
        assert not fsm.can_proceed(self.model.block)
        with pytest.raises(fsm.TransitionNotAllowed):
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

    def tearDown(self):
        pre_transition.disconnect(self.on_pre_transition, sender=SimpleBlogPost)
        post_transition.disconnect(self.on_post_transition, sender=SimpleBlogPost)

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
        with pytest.raises(fsm.TransitionNotAllowed):
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

    def tearDown(self):
        pre_transition.disconnect(self.on_pre_transition, sender="testapp.SimpleBlogPost")
        post_transition.disconnect(self.on_post_transition, sender="testapp.SimpleBlogPost")


class TestFieldTransitionsInspect(TestCase):
    def setUp(self):
        self.model = SimpleBlogPost()

    def test_transition_are_hashable(self) -> None:
        transition = fsm.Transition(
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
                fsm.Transition(
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

        assert fsm.Transition(
            method=AdvancedBlogPost.publish,
            source="new",
            target="published",
            on_error=None,
            conditions=[],
            permission=None,
            custom={},
        ) != fsm.Transition(
            method=SimpleBlogPost.publish,
            source="new",
            target="published",
            on_error=None,
            conditions=[],
            permission=None,
            custom={},
        )

        assert fsm.Transition(
            method=AdvancedBlogPost.empty,
            source=fsm.ANY_STATE,
            target="",
            on_error=None,
            conditions=[],
            permission=None,
            custom={},
        ) == fsm.Transition(
            method=SimpleBlogPost.empty,
            source=fsm.ANY_STATE,
            target="",
            on_error=None,
            conditions=[],
            permission=None,
            custom={},
        )

    def test_in_operator_for_available_transitions(self):
        # store the generator in a list, so we can reuse the generator and do multiple asserts
        transitions = list(self.model.get_available_state_transitions())  # type: ignore[attr-defined]

        assert "publish" in transitions
        assert "xyz" not in transitions

        # inline method for faking the name of the transition
        def publish():
            pass

        obj = fsm.Transition(
            method=publish,
            source="",
            target="",
            on_error="",
            conditions=None,
            permission="",
            custom=None,
        )

        assert obj not in transitions

    def test_available_conditions_from_new(self):
        transitions = self.model.get_available_state_transitions()  # type: ignore[attr-defined]
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
        transitions = self.model.get_available_state_transitions()  # type: ignore[attr-defined]
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
        transitions = self.model.get_available_state_transitions()  # type: ignore[attr-defined]
        actual = {(transition.source, transition.target) for transition in transitions}
        expected = {("*", "moderated"), ("hidden", "stolen"), ("*", ""), ("+", "blocked")}
        assert actual == expected

    def test_available_conditions_from_stolen(self):
        self.model.publish()
        self.model.steal()
        transitions = self.model.get_available_state_transitions()  # type: ignore[attr-defined]
        actual = {(transition.source, transition.target) for transition in transitions}
        expected = {("*", "moderated"), ("*", ""), ("+", "blocked")}
        assert actual == expected

    def test_available_conditions_from_blocked(self):
        self.model.block()
        transitions = self.model.get_available_state_transitions()  # type: ignore[attr-defined]
        actual = {(transition.source, transition.target) for transition in transitions}
        expected = {("*", "moderated"), ("*", "")}
        assert actual == expected

    def test_available_conditions_from_empty(self):
        self.model.empty()
        transitions = self.model.get_available_state_transitions()  # type: ignore[attr-defined]
        actual = {(transition.source, transition.target) for transition in transitions}
        expected = {("*", "moderated"), ("*", ""), ("+", "blocked")}
        assert actual == expected

    def test_all_conditions(self):
        transitions = self.model.get_all_state_transitions()  # type: ignore[attr-defined]

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
