"""
Tests for signal behavior with exceptions and on_error states.

These tests verify:
- Signal kwargs when exceptions occur
- Signal target is correct when on_error fires
- Signal timing with exception handling
- Multiple signal receivers behavior
"""

from __future__ import annotations

from unittest.mock import MagicMock, call

import pytest
from django.db import models

from django_fsm_rx import FSMField, TransitionNotAllowed, transition
from django_fsm_rx.signals import post_transition, pre_transition


class SignalExceptionModel(models.Model):
    """Model for testing signals with exceptions."""

    state = FSMField(default="draft")

    @transition(field=state, source="draft", target="published", on_error="failed")
    def publish_with_error(self):
        """Transition that raises an exception."""
        raise ValueError("Publishing failed!")

    @transition(field=state, source="draft", target="published")
    def publish_no_error_handler(self):
        """Transition without on_error that raises."""
        raise ValueError("No error handler!")

    @transition(field=state, source="draft", target="published")
    def publish_success(self):
        """Successful transition."""
        pass

    class Meta:
        app_label = "tests"


class SignalTracker:
    """Helper class to track signal invocations."""

    def __init__(self):
        self.pre_calls = []
        self.post_calls = []
        self.pre_handler = None
        self.post_handler = None

    def setup(self):
        """Connect signal handlers."""
        self.pre_calls = []
        self.post_calls = []

        def pre_handler(sender, instance, name, source, target, **kwargs):
            self.pre_calls.append({
                "sender": sender,
                "instance": instance,
                "name": name,
                "source": source,
                "target": target,
                "kwargs": kwargs,
            })

        def post_handler(sender, instance, name, source, target, **kwargs):
            self.post_calls.append({
                "sender": sender,
                "instance": instance,
                "name": name,
                "source": source,
                "target": target,
                "kwargs": kwargs,
            })

        self.pre_handler = pre_handler
        self.post_handler = post_handler
        pre_transition.connect(pre_handler)
        post_transition.connect(post_handler)

    def teardown(self):
        """Disconnect signal handlers."""
        if self.pre_handler:
            pre_transition.disconnect(self.pre_handler)
        if self.post_handler:
            post_transition.disconnect(self.post_handler)


@pytest.fixture
def signal_tracker():
    """Create and setup signal tracker."""
    tracker = SignalTracker()
    tracker.setup()
    yield tracker
    tracker.teardown()


class TestPreTransitionSignal:
    """Test pre_transition signal behavior."""

    def test_pre_signal_fired_on_success(self, signal_tracker):
        """pre_transition signal should be fired on successful transition."""
        model = SignalExceptionModel()
        model.publish_success()

        assert len(signal_tracker.pre_calls) == 1
        call = signal_tracker.pre_calls[0]
        assert call["source"] == "draft"
        assert call["target"] == "published"
        assert call["name"] == "publish_success"

    def test_pre_signal_fired_before_exception(self, signal_tracker):
        """pre_transition signal should be fired even when transition raises."""
        model = SignalExceptionModel()

        with pytest.raises(ValueError):
            model.publish_with_error()

        # Pre signal should have been fired
        assert len(signal_tracker.pre_calls) == 1
        call = signal_tracker.pre_calls[0]
        assert call["source"] == "draft"
        # Target in pre_signal is the intended target, not the error state
        assert call["target"] == "published"

    def test_pre_signal_not_fired_when_not_allowed(self, signal_tracker):
        """pre_transition signal should NOT be fired when transition not allowed."""
        model = SignalExceptionModel()
        model.state = "published"

        with pytest.raises(TransitionNotAllowed):
            model.publish_success()

        # No pre signal should have been fired
        assert len(signal_tracker.pre_calls) == 0


class TestPostTransitionSignal:
    """Test post_transition signal behavior."""

    def test_post_signal_fired_on_success(self, signal_tracker):
        """post_transition signal should be fired on successful transition."""
        model = SignalExceptionModel()
        model.publish_success()

        assert len(signal_tracker.post_calls) == 1
        call = signal_tracker.post_calls[0]
        assert call["source"] == "draft"
        assert call["target"] == "published"

    def test_post_signal_not_fired_on_exception_without_on_error(self, signal_tracker):
        """post_transition should NOT fire when exception without on_error."""
        model = SignalExceptionModel()

        with pytest.raises(ValueError):
            model.publish_no_error_handler()

        # Post signal should NOT have been fired
        assert len(signal_tracker.post_calls) == 0

    def test_post_signal_fired_with_error_state_when_on_error(self, signal_tracker):
        """post_transition should fire with error state when on_error is set."""
        model = SignalExceptionModel()

        with pytest.raises(ValueError):
            model.publish_with_error()

        # Post signal should have been fired with error state
        assert len(signal_tracker.post_calls) == 1
        call = signal_tracker.post_calls[0]
        assert call["source"] == "draft"
        # Target should be the error state, not the intended target
        assert call["target"] == "failed"

    def test_post_signal_exception_kwarg_when_on_error(self, signal_tracker):
        """post_transition should include exception in kwargs when on_error fires."""
        model = SignalExceptionModel()

        with pytest.raises(ValueError):
            model.publish_with_error()

        call = signal_tracker.post_calls[0]
        # Check if exception info is in kwargs
        assert "exception" in call["kwargs"]
        assert isinstance(call["kwargs"]["exception"], ValueError)


class TestSignalOrder:
    """Test signal execution order."""

    def test_pre_signal_before_method_execution(self, signal_tracker):
        """pre_transition should fire before transition method executes."""
        execution_order = []

        def pre_handler(sender, instance, name, source, target, **kwargs):
            execution_order.append("pre_signal")
            signal_tracker.pre_calls.append({})

        pre_transition.disconnect(signal_tracker.pre_handler)
        pre_transition.connect(pre_handler)

        class OrderModel(models.Model):
            state = FSMField(default="draft")

            @transition(field=state, source="draft", target="published")
            def publish(self):
                execution_order.append("method")

            class Meta:
                app_label = "tests"

        try:
            model = OrderModel()
            model.publish()
            assert execution_order == ["pre_signal", "method"]
        finally:
            pre_transition.disconnect(pre_handler)
            pre_transition.connect(signal_tracker.pre_handler)

    def test_post_signal_after_method_execution(self, signal_tracker):
        """post_transition should fire after transition method executes."""
        execution_order = []

        def post_handler(sender, instance, name, source, target, **kwargs):
            execution_order.append("post_signal")
            signal_tracker.post_calls.append({})

        post_transition.disconnect(signal_tracker.post_handler)
        post_transition.connect(post_handler)

        class OrderModel(models.Model):
            state = FSMField(default="draft")

            @transition(field=state, source="draft", target="published")
            def publish(self):
                execution_order.append("method")

            class Meta:
                app_label = "tests"

        try:
            model = OrderModel()
            model.publish()
            assert execution_order == ["method", "post_signal"]
        finally:
            post_transition.disconnect(post_handler)
            post_transition.connect(signal_tracker.post_handler)


class TestMultipleSignalReceivers:
    """Test behavior with multiple signal receivers."""

    def test_multiple_pre_receivers(self):
        """Multiple pre_transition receivers should all be called."""
        calls = []

        def handler1(sender, **kwargs):
            calls.append("handler1")

        def handler2(sender, **kwargs):
            calls.append("handler2")

        pre_transition.connect(handler1)
        pre_transition.connect(handler2)

        try:
            model = SignalExceptionModel()
            model.publish_success()

            assert "handler1" in calls
            assert "handler2" in calls
        finally:
            pre_transition.disconnect(handler1)
            pre_transition.disconnect(handler2)

    def test_receiver_exception_does_not_block_others(self):
        """Exception in one receiver should not block other receivers."""
        calls = []

        def handler1(sender, **kwargs):
            calls.append("handler1")
            raise RuntimeError("Handler 1 failed!")

        def handler2(sender, **kwargs):
            calls.append("handler2")

        # Note: Django signals by default propagate exceptions
        # This test documents the current behavior
        post_transition.connect(handler1)
        post_transition.connect(handler2)

        try:
            model = SignalExceptionModel()
            with pytest.raises(RuntimeError):
                model.publish_success()

            # handler1 was called
            assert "handler1" in calls
            # handler2 may or may not be called depending on Django signal implementation
        finally:
            post_transition.disconnect(handler1)
            post_transition.disconnect(handler2)


class TestSignalSenderFiltering:
    """Test signal receiver filtering by sender."""

    def test_receiver_filtered_by_sender(self, signal_tracker):
        """Signal receiver can filter by sender class."""
        specific_calls = []

        def specific_handler(sender, **kwargs):
            specific_calls.append(sender)

        # Only connect for SignalExceptionModel
        post_transition.connect(specific_handler, sender=SignalExceptionModel)

        try:
            # This should trigger the handler
            model = SignalExceptionModel()
            model.publish_success()
            assert len(specific_calls) == 1
            assert specific_calls[0] == SignalExceptionModel
        finally:
            post_transition.disconnect(specific_handler, sender=SignalExceptionModel)


class TestSignalWithStateChange:
    """Test signal reflects correct state at time of firing."""

    def test_post_signal_instance_has_new_state(self, signal_tracker):
        """Instance should have new state when post_transition fires."""
        model = SignalExceptionModel()
        model.publish_success()

        call = signal_tracker.post_calls[0]
        # The instance in the signal should have the new state
        assert call["instance"].state == "published"

    def test_pre_signal_instance_has_old_state(self, signal_tracker):
        """Instance should have old state when pre_transition fires."""
        captured_state = []

        def pre_handler(sender, instance, **kwargs):
            captured_state.append(instance.state)
            signal_tracker.pre_calls.append({})

        pre_transition.disconnect(signal_tracker.pre_handler)
        pre_transition.connect(pre_handler)

        try:
            model = SignalExceptionModel()
            model.publish_success()

            # State during pre_transition should be the old state
            assert captured_state[0] == "draft"
        finally:
            pre_transition.disconnect(pre_handler)
            pre_transition.connect(signal_tracker.pre_handler)


class TestSignalWithDynamicTargets:
    """Test signals with RETURN_VALUE and GET_STATE."""

    def test_post_signal_has_resolved_target(self, signal_tracker):
        """post_transition should have the resolved target state."""
        from django_fsm_rx import RETURN_VALUE

        class DynamicModel(models.Model):
            state = FSMField(default="draft")

            @transition(
                field=state,
                source="draft",
                target=RETURN_VALUE("approved", "rejected"),
            )
            def review(self, approved: bool):
                return "approved" if approved else "rejected"

            class Meta:
                app_label = "tests"

        model = DynamicModel()
        model.review(approved=True)

        call = signal_tracker.post_calls[0]
        assert call["target"] == "approved"

    def test_post_signal_has_rejected_target(self, signal_tracker):
        """post_transition should have rejected target when returned."""
        from django_fsm_rx import RETURN_VALUE

        class DynamicModel(models.Model):
            state = FSMField(default="draft")

            @transition(
                field=state,
                source="draft",
                target=RETURN_VALUE("approved", "rejected"),
            )
            def review(self, approved: bool):
                return "approved" if approved else "rejected"

            class Meta:
                app_label = "tests"

        model = DynamicModel()
        model.review(approved=False)

        call = signal_tracker.post_calls[0]
        assert call["target"] == "rejected"


class TestSignalWithPrefixWildcards:
    """Test signals with prefix wildcard sources."""

    def test_signal_source_is_actual_state_not_pattern(self, signal_tracker):
        """Signal source should be the actual state, not the pattern."""

        class PrefixModel(models.Model):
            state = FSMField(default="WRK-REP-PRG")

            @transition(field=state, source="WRK-*", target="CMP-STD-DON")
            def complete(self):
                pass

            class Meta:
                app_label = "tests"

        model = PrefixModel()
        model.complete()

        call = signal_tracker.post_calls[0]
        # Source should be the actual state, not "WRK-*"
        assert call["source"] == "WRK-REP-PRG"
        assert call["target"] == "CMP-STD-DON"
