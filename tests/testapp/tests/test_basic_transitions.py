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

    def test_known_transitions_succeed(self):
        assert fsm.can_proceed(self.model.publish)
        self.model.publish()

        assert self.model.state == ApplicationState.PUBLISHED

        assert fsm.can_proceed(self.model.hide)
        self.model.hide()

        assert self.model.state == ApplicationState.HIDDEN

    def test_unavailable_transition_fails(self):
        assert not fsm.can_proceed(self.model.hide)
        with pytest.raises(fsm.InvalidTransition):
            self.model.hide()

    def test_state_unchanged_when_transition_raises(self):
        assert fsm.can_proceed(self.model.remove)
        with pytest.raises(Exception, match="Upss"):
            self.model.remove()

        assert self.model.state == ApplicationState.NEW

    def test_available_transition_with_empty_target_keeps_state(self):
        self.model.publish()
        self.model.notify_all()

        assert self.model.state == ApplicationState.PUBLISHED

    def test_unavailable_transition_with_empty_target_keeps_state(self):
        with pytest.raises(fsm.InvalidTransition):
            self.model.notify_all()

        assert self.model.state == ApplicationState.NEW

    def test_multi_source_transition_from_published(self):
        self.model.publish()
        self.model.steal()

        assert self.model.state == ApplicationState.STOLEN

    def test_multi_source_transition_from_hidden(self):
        self.model.publish()
        self.model.hide()
        self.model.steal()

        assert self.model.state == ApplicationState.STOLEN

    def test_any_state_transition_succeeds(self):
        assert fsm.can_proceed(self.model.moderate)
        self.model.moderate()

        assert self.model.state == ApplicationState.MODERATED

    def test_any_other_state_transition_succeeds(self):
        """Tests that the '+' shortcut succeeds for a source
        other than the target.
        """
        assert fsm.can_proceed(self.model.block)
        self.model.block()

        assert self.model.state == ApplicationState.BLOCKED

    def test_any_other_state_transition_fails_when_same_source(self):
        """Tests that the '+' shortcut fails if the source
        equals the target.
        """
        self.model.block()

        assert not fsm.can_proceed(self.model.block)
        with pytest.raises(fsm.InvalidTransition):
            self.model.block()

    def test_empty_string_target_sets_blank_state(self):
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

    def test_signals_fire_on_valid_transition(self):
        self.model.publish()

        assert self.pre_transition_called
        assert self.post_transition_called

    def test_signals_do_not_fire_on_invalid_transition(self):
        with pytest.raises(fsm.InvalidTransition):
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

    def test_transitions_are_hashable(self) -> None:
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

    def test_transition_equality_compares_method(self) -> None:
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

        # overridden transitions have different hash
        overridden_transition = fsm.Transition(
            method=AdvancedBlogPost.publish,
            source="new",
            target="published",
            on_error=None,
            conditions=[],
            permission=None,
            custom={},
        )
        original_transition = fsm.Transition(
            method=SimpleBlogPost.publish,
            source="new",
            target="published",
            on_error=None,
            conditions=[],
            permission=None,
            custom={},
        )
        assert overridden_transition != original_transition

        # inherited transitions have original hash
        original_transition = fsm.Transition(
            method=AdvancedBlogPost.empty,
            source=fsm.ANY_STATE,
            target="",
            on_error=None,
            conditions=[],
            permission=None,
            custom={},
        )
        inherited_transition = fsm.Transition(
            method=SimpleBlogPost.empty,
            source=fsm.ANY_STATE,
            target="",
            on_error=None,
            conditions=[],
            permission=None,
            custom={},
        )
        assert inherited_transition == original_transition

    def test_transition_name_membership(self):
        # store the generator in a list, so we can reuse the generator and do multiple asserts
        available_transitions = list(self.model.get_available_state_transitions())  # type: ignore[attr-defined]

        assert "publish" in available_transitions
        assert "xyz" not in available_transitions

        # inline method for faking the name of the transition
        def publish():
            pass

        transition_with_same_name = fsm.Transition(
            method=publish,
            source="",
            target="",
            on_error="",
            conditions=None,
            permission="",
            custom=None,
        )

        assert transition_with_same_name not in available_transitions

    def test_all_transitions_reported(self):
        transitions = self.model.get_all_state_transitions()  # type: ignore[attr-defined]

        available_transitions = {
            (transition.source, transition.target) for transition in transitions
        }
        assert available_transitions == {
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


@pytest.mark.parametrize(
    ("setup_state", "expected_transitions"),
    [
        pytest.param(
            ApplicationState.NEW,
            {
                ("*", "moderated"),
                ("new", "published"),
                ("new", "removed"),
                ("*", ""),
                ("+", "blocked"),
            },
            id="new",
        ),
        pytest.param(
            ApplicationState.PUBLISHED,
            {
                ("*", "moderated"),
                ("published", None),
                ("published", "hidden"),
                ("published", "stolen"),
                ("*", ""),
                ("+", "blocked"),
            },
            id="published",
        ),
        pytest.param(
            ApplicationState.HIDDEN,
            {("*", "moderated"), ("hidden", "stolen"), ("*", ""), ("+", "blocked")},
            id="hidden",
        ),
        pytest.param(
            ApplicationState.STOLEN,
            {("*", "moderated"), ("*", ""), ("+", "blocked")},
            id="stolen",
        ),
        pytest.param(
            ApplicationState.BLOCKED,
            {("*", "moderated"), ("*", "")},
            id="blocked",
        ),
    ],
)
def test_available_conditions_by_state(setup_state, expected_transitions):
    model = SimpleBlogPost(state=setup_state)

    available_transitions = {
        (transition.source, transition.target)
        for transition in model.get_available_state_transitions()  # type: ignore[attr-defined]
    }

    assert available_transitions == expected_transitions
