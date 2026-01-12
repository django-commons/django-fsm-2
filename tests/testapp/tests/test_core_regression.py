"""
Core regression tests for django-fsm-2.

These tests ensure stability of core FSM functionality.
"""

from __future__ import annotations

import pytest
from django.db import models

from django_fsm_rx import GET_STATE
from django_fsm_rx import RETURN_VALUE
from django_fsm_rx import FSMField
from django_fsm_rx import FSMIntegerField
from django_fsm_rx import FSMModelMixin
from django_fsm_rx import TransitionNotAllowed
from django_fsm_rx import can_proceed
from django_fsm_rx import transition
from django_fsm_rx.signals import post_transition
from django_fsm_rx.signals import pre_transition


class RegressionModel(models.Model):
    """Test model for regression tests."""

    state = FSMField(default="new")

    @transition(field=state, source="new", target="pending")
    def start(self):
        pass

    @transition(field=state, source="pending", target="done")
    def complete(self):
        pass

    @transition(field=state, source="*", target="cancelled")
    def cancel(self):
        pass

    @transition(field=state, source="+", target="new")
    def reset(self):
        pass

    class Meta:
        app_label = "testapp"


class ProtectedRegressionModel(FSMModelMixin, models.Model):
    """Test model with protected FSM field."""

    state = FSMField(default="draft", protected=True)

    @transition(field=state, source="draft", target="published")
    def publish(self):
        pass

    class Meta:
        app_label = "testapp"


class ConditionalRegressionModel(models.Model):
    """Test model with conditions."""

    state = FSMField(default="new")
    is_valid = models.BooleanField(default=False)

    def check_valid(self):
        return self.is_valid

    @transition(field=state, source="new", target="validated", conditions=[check_valid])
    def validate(self):
        pass

    class Meta:
        app_label = "testapp"


class DynamicStateModel(models.Model):
    """Test model with dynamic state resolution."""

    state = FSMField(default="pending")

    @transition(
        field=state,
        source="pending",
        target=RETURN_VALUE("approved", "rejected"),
    )
    def review(self, approved: bool):
        return "approved" if approved else "rejected"

    def determine_state(self, priority: int):
        return "urgent" if priority > 5 else "normal"

    @transition(
        field=state,
        source="pending",
        target=GET_STATE(determine_state, states=["urgent", "normal"]),
    )
    def prioritize(self, priority: int):
        pass

    class Meta:
        app_label = "testapp"


class TestTransitionBasics:
    """Basic transition functionality regression tests."""

    def test_simple_transition(self):
        """Test basic state transition."""
        obj = RegressionModel()
        assert obj.state == "new"

        obj.start()
        assert obj.state == "pending"

    def test_chained_transitions(self):
        """Test multiple transitions in sequence."""
        obj = RegressionModel()
        obj.start()
        obj.complete()
        assert obj.state == "done"

    def test_wildcard_transition(self):
        """Test transition from any state (*)."""
        obj = RegressionModel()
        obj.start()
        assert obj.state == "pending"

        obj.cancel()
        assert obj.state == "cancelled"

    def test_plus_transition_excludes_target(self):
        """Test transition from any except target (+)."""
        obj = RegressionModel()
        obj.start()
        obj.reset()
        assert obj.state == "new"

        # Should not allow reset when already in 'new'
        with pytest.raises(TransitionNotAllowed):
            obj.reset()

    def test_transition_not_allowed_wrong_source(self):
        """Test that transition fails from wrong source state."""
        obj = RegressionModel()
        # complete requires 'pending' source, but we're in 'new'
        with pytest.raises(TransitionNotAllowed):
            obj.complete()


class TestCanProceed:
    """Regression tests for can_proceed function."""

    def test_can_proceed_returns_true(self):
        """Test can_proceed returns True when transition is allowed."""
        obj = RegressionModel()
        assert can_proceed(obj.start) is True

    def test_can_proceed_returns_false(self):
        """Test can_proceed returns False when transition not allowed."""
        obj = RegressionModel()
        # complete requires 'pending'
        assert can_proceed(obj.complete) is False

    def test_can_proceed_with_conditions_met(self):
        """Test can_proceed with conditions that are met."""
        obj = ConditionalRegressionModel()
        obj.is_valid = True
        assert can_proceed(obj.validate) is True

    def test_can_proceed_with_conditions_not_met(self):
        """Test can_proceed with conditions that are not met."""
        obj = ConditionalRegressionModel()
        obj.is_valid = False
        assert can_proceed(obj.validate) is False

    def test_can_proceed_skip_conditions(self):
        """Test can_proceed with check_conditions=False."""
        obj = ConditionalRegressionModel()
        obj.is_valid = False
        # Should return True because we're skipping condition check
        assert can_proceed(obj.validate, check_conditions=False) is True


class TestProtectedFields:
    """Regression tests for protected FSM fields."""

    def test_protected_field_blocks_direct_assignment(self):
        """Test that protected fields block direct assignment."""
        obj = ProtectedRegressionModel()
        with pytest.raises(AttributeError):
            obj.state = "published"

    def test_protected_field_allows_transition(self):
        """Test that protected fields allow transition method."""
        obj = ProtectedRegressionModel()
        obj.publish()
        assert obj.state == "published"


class TestDynamicStateResolution:
    """Regression tests for dynamic state resolution."""

    def test_return_value_approved(self):
        """Test RETURN_VALUE with approved outcome."""
        obj = DynamicStateModel()
        obj.review(approved=True)
        assert obj.state == "approved"

    def test_return_value_rejected(self):
        """Test RETURN_VALUE with rejected outcome."""
        obj = DynamicStateModel()
        obj.review(approved=False)
        assert obj.state == "rejected"

    def test_get_state_urgent(self):
        """Test GET_STATE with high priority."""
        obj = DynamicStateModel()
        obj.prioritize(priority=10)
        assert obj.state == "urgent"

    def test_get_state_normal(self):
        """Test GET_STATE with low priority."""
        obj = DynamicStateModel()
        obj.prioritize(priority=3)
        assert obj.state == "normal"


class TestTransitionMethods:
    """Regression tests for model transition helper methods."""

    def test_get_all_transitions(self):
        """Test get_all_state_transitions returns all transitions."""
        obj = RegressionModel()
        all_transitions = list(obj.get_all_state_transitions())
        names = [t.name for t in all_transitions]

        assert "start" in names
        assert "complete" in names
        assert "cancel" in names
        assert "reset" in names

    def test_get_available_transitions_from_new(self):
        """Test get_available_state_transitions from 'new' state."""
        obj = RegressionModel()
        available = list(obj.get_available_state_transitions())
        names = [t.name for t in available]

        assert "start" in names  # new -> pending
        assert "cancel" in names  # * -> cancelled
        assert "reset" not in names  # + excludes target, we're in 'new'
        assert "complete" not in names  # pending -> done, not available

    def test_get_available_transitions_from_pending(self):
        """Test get_available_state_transitions from 'pending' state."""
        obj = RegressionModel()
        obj.start()

        available = list(obj.get_available_state_transitions())
        names = [t.name for t in available]

        assert "complete" in names  # pending -> done
        assert "cancel" in names  # * -> cancelled
        assert "reset" in names  # + -> new (not in 'new')
        assert "start" not in names  # new -> pending, not available


class TestSignals:
    """Regression tests for FSM signals."""

    def test_pre_transition_signal_fired(self):
        """Test that pre_transition signal is fired."""
        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        pre_transition.connect(handler, sender=RegressionModel)
        try:
            obj = RegressionModel()
            obj.start()

            assert len(received) == 1
            assert received[0]["name"] == "start"
            assert received[0]["source"] == "new"
            assert received[0]["target"] == "pending"
        finally:
            pre_transition.disconnect(handler, sender=RegressionModel)

    def test_post_transition_signal_fired(self):
        """Test that post_transition signal is fired."""
        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        post_transition.connect(handler, sender=RegressionModel)
        try:
            obj = RegressionModel()
            obj.start()

            assert len(received) == 1
            assert received[0]["name"] == "start"
            assert received[0]["source"] == "new"
            assert received[0]["target"] == "pending"
        finally:
            post_transition.disconnect(handler, sender=RegressionModel)

    def test_signal_receives_method_args(self):
        """Test that signals receive method arguments."""
        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        post_transition.connect(handler, sender=DynamicStateModel)
        try:
            obj = DynamicStateModel()
            obj.review(approved=True)

            assert len(received) == 1
            assert received[0]["method_kwargs"] == {"approved": True}
        finally:
            post_transition.disconnect(handler, sender=DynamicStateModel)


class TestTransitionCustomData:
    """Regression tests for transition custom data."""

    def test_transition_custom_data_accessible(self):
        """Test that custom data is accessible from transitions."""

        class CustomModel(models.Model):
            state = FSMField(default="new")

            @transition(
                field=state,
                source="new",
                target="done",
                custom={"label": "Complete", "icon": "check"},
            )
            def complete(self):
                pass

            class Meta:
                app_label = "testapp"

        obj = CustomModel()
        transitions = list(obj.get_available_state_transitions())
        complete_transition = next(t for t in transitions if t.name == "complete")

        assert complete_transition.custom["label"] == "Complete"
        assert complete_transition.custom["icon"] == "check"


class TestMultipleSourceStates:
    """Regression tests for transitions with multiple source states."""

    def test_transition_from_multiple_sources(self):
        """Test transition that accepts multiple source states."""

        class MultiSourceModel(models.Model):
            state = FSMField(default="new")

            @transition(field=state, source=["new", "pending"], target="done")
            def finish(self):
                pass

            @transition(field=state, source="new", target="pending")
            def start(self):
                pass

            class Meta:
                app_label = "testapp"

        # From 'new'
        obj1 = MultiSourceModel()
        obj1.finish()
        assert obj1.state == "done"

        # From 'pending'
        obj2 = MultiSourceModel()
        obj2.start()
        obj2.finish()
        assert obj2.state == "done"


class TestOnError:
    """Regression tests for on_error handling."""

    def test_on_error_changes_state_on_exception(self):
        """Test that on_error state is set when exception occurs."""

        class ErrorModel(models.Model):
            state = FSMField(default="new")

            @transition(field=state, source="new", target="done", on_error="failed")
            def process(self):
                raise ValueError("Processing failed")

            class Meta:
                app_label = "testapp"

        obj = ErrorModel()
        with pytest.raises(ValueError):
            obj.process()

        # State should be 'failed', not 'done'
        assert obj.state == "failed"

    def test_on_error_signal_includes_exception(self):
        """Test that post_transition signal includes exception on error."""

        class ErrorModel(models.Model):
            state = FSMField(default="new")

            @transition(field=state, source="new", target="done", on_error="failed")
            def process(self):
                raise ValueError("Test error")

            class Meta:
                app_label = "testapp"

        received = []

        def handler(sender, **kwargs):
            received.append(kwargs)

        post_transition.connect(handler, sender=ErrorModel)
        try:
            obj = ErrorModel()
            with pytest.raises(ValueError):
                obj.process()

            assert len(received) == 1
            assert "exception" in received[0]
            assert isinstance(received[0]["exception"], ValueError)
        finally:
            post_transition.disconnect(handler, sender=ErrorModel)


class TestFSMIntegerField:
    """Regression tests for FSMIntegerField."""

    def test_integer_field_transitions(self):
        """Test transitions with integer states."""

        class IntStateModel(models.Model):
            class State:
                NEW = 1
                PENDING = 2
                DONE = 3

            state = FSMIntegerField(default=State.NEW)

            @transition(field=state, source=State.NEW, target=State.PENDING)
            def start(self):
                pass

            @transition(field=state, source=State.PENDING, target=State.DONE)
            def complete(self):
                pass

            class Meta:
                app_label = "testapp"

        obj = IntStateModel()
        assert obj.state == IntStateModel.State.NEW

        obj.start()
        assert obj.state == IntStateModel.State.PENDING

        obj.complete()
        assert obj.state == IntStateModel.State.DONE


class TestExportedSymbols:
    """Regression tests to ensure all public symbols are exported."""

    def test_core_exports(self):
        """Test that core symbols are exported from django_fsm_rx."""
        import django_fsm_rx

        # Exceptions
        assert hasattr(django_fsm_rx, "TransitionNotAllowed")
        assert hasattr(django_fsm_rx, "ConcurrentTransition")
        assert hasattr(django_fsm_rx, "InvalidResultState")

        # Fields
        assert hasattr(django_fsm_rx, "FSMField")
        assert hasattr(django_fsm_rx, "FSMIntegerField")
        assert hasattr(django_fsm_rx, "FSMKeyField")
        assert hasattr(django_fsm_rx, "FSMFieldMixin")

        # Mixins
        assert hasattr(django_fsm_rx, "FSMModelMixin")
        assert hasattr(django_fsm_rx, "ConcurrentTransitionMixin")

        # Decorators and functions
        assert hasattr(django_fsm_rx, "transition")
        assert hasattr(django_fsm_rx, "can_proceed")
        assert hasattr(django_fsm_rx, "has_transition_perm")

        # Dynamic state resolution
        assert hasattr(django_fsm_rx, "GET_STATE")
        assert hasattr(django_fsm_rx, "RETURN_VALUE")

        # Classes for introspection
        assert hasattr(django_fsm_rx, "Transition")
        assert hasattr(django_fsm_rx, "FSMMeta")

    def test_signals_exports(self):
        """Test that signals are exported from django_fsm_rx.signals."""
        from django_fsm_rx import signals

        assert hasattr(signals, "pre_transition")
        assert hasattr(signals, "post_transition")

    def test_admin_exports(self):
        """Test that admin classes are exported from django_fsm_rx.admin."""
        from django_fsm_rx import admin

        assert hasattr(admin, "FSMAdminMixin")
        assert hasattr(admin, "FSMObjectTransitions")

    def test_log_exports(self):
        """Test that log utilities are exported from django_fsm_rx.log."""
        from django_fsm_rx import log

        assert hasattr(log, "fsm_log_by")
        assert hasattr(log, "fsm_log_description")
        assert hasattr(log, "FSMLogDescriptor")
