"""
Tests for on_success callback edge cases.

These tests verify callback behavior in edge cases:
- Exception handling in callbacks
- Callback execution order relative to signals
- Callbacks with dynamic state resolution (RETURN_VALUE, GET_STATE)
- Database operations in callbacks
- Multiple callbacks and isolation
"""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest
from django.db import models, transaction

from django_fsm_rx import (
    FSMField,
    GET_STATE,
    RETURN_VALUE,
    TransitionNotAllowed,
    can_proceed,
    transition,
)
from django_fsm_rx.signals import post_transition, pre_transition


# Track callback and signal invocations
invocation_log: list[dict] = []


def reset_invocation_log():
    """Reset the invocation log."""
    invocation_log.clear()


def logging_callback(instance, source, target, **kwargs):
    """Callback that logs invocation with timestamp-like ordering."""
    invocation_log.append({
        "type": "callback",
        "source": source,
        "target": target,
        "order": len(invocation_log),
    })


def exception_callback(instance, source, target, **kwargs):
    """Callback that raises an exception."""
    invocation_log.append({"type": "callback_before_error"})
    raise ValueError("Callback error!")


def db_operation_callback(instance, source, target, **kwargs):
    """Callback that performs database operations."""
    # This simulates creating an audit log entry
    invocation_log.append({
        "type": "db_callback",
        "instance_pk": instance.pk,
        "source": source,
        "target": target,
    })


def modifying_callback(instance, source, target, **kwargs):
    """Callback that modifies the instance."""
    instance.modified_by_callback = True
    invocation_log.append({"type": "modifying_callback"})


class CallbackExceptionModel(models.Model):
    """Model for testing callback exceptions."""

    state = FSMField(default="draft")

    @transition(field=state, source="draft", target="published", on_success=exception_callback)
    def publish(self):
        """Transition with callback that raises."""
        pass

    class Meta:
        app_label = "tests"


class CallbackOrderModel(models.Model):
    """Model for testing callback vs signal order."""

    state = FSMField(default="draft")

    @transition(field=state, source="draft", target="published", on_success=logging_callback)
    def publish(self):
        """Transition with callback for order testing."""
        pass

    class Meta:
        app_label = "tests"


class CallbackWithReturnValueModel(models.Model):
    """Model for testing callback with RETURN_VALUE."""

    state = FSMField(default="draft")

    @transition(
        field=state,
        source="draft",
        target=RETURN_VALUE("approved", "rejected"),
        on_success=logging_callback,
    )
    def review(self, approved: bool):
        """Transition with dynamic target."""
        return "approved" if approved else "rejected"

    class Meta:
        app_label = "tests"


class CallbackWithGetStateModel(models.Model):
    """Model for testing callback with GET_STATE."""

    state = FSMField(default="draft")

    @transition(
        field=state,
        source="draft",
        target=GET_STATE(
            lambda self, approved: "approved" if approved else "rejected",
            states=["approved", "rejected"],
        ),
        on_success=logging_callback,
    )
    def review(self, approved: bool):
        """Transition with GET_STATE target."""
        pass

    class Meta:
        app_label = "tests"


class CallbackModifyingModel(models.Model):
    """Model for testing callback that modifies instance."""

    state = FSMField(default="draft")
    modified_by_callback = False

    @transition(field=state, source="draft", target="published", on_success=modifying_callback)
    def publish(self):
        """Transition with modifying callback."""
        pass

    class Meta:
        app_label = "tests"


class MultipleCallbackModel(models.Model):
    """Model for testing multiple callbacks on different transitions."""

    state = FSMField(default="a")

    @transition(field=state, source="a", target="b", on_success=logging_callback)
    def go_to_b(self):
        pass

    @transition(field=state, source="b", target="c", on_success=logging_callback)
    def go_to_c(self):
        pass

    @transition(field=state, source="c", target="d", on_success=logging_callback)
    def go_to_d(self):
        pass

    class Meta:
        app_label = "tests"


class CallbackWithOnErrorModel(models.Model):
    """Model for testing callback interaction with on_error."""

    state = FSMField(default="draft")

    @transition(
        field=state,
        source="draft",
        target="published",
        on_error="failed",
        on_success=logging_callback,
    )
    def publish(self):
        """Transition that might fail."""
        raise ValueError("Publishing failed!")

    class Meta:
        app_label = "tests"


class TestCallbackExceptionHandling:
    """Test callback exception handling."""

    def setup_method(self):
        reset_invocation_log()

    def test_callback_exception_propagates(self):
        """Exception in callback should propagate to caller."""
        model = CallbackExceptionModel()

        with pytest.raises(ValueError, match="Callback error!"):
            model.publish()

        # Callback was invoked (logged before error)
        assert len(invocation_log) == 1
        assert invocation_log[0]["type"] == "callback_before_error"

    def test_state_changed_before_callback_exception(self):
        """State should be changed even if callback raises."""
        model = CallbackExceptionModel()

        with pytest.raises(ValueError):
            model.publish()

        # State was changed before callback raised
        assert model.state == "published"

    def test_callback_exception_does_not_rollback_state(self):
        """Callback exception should not rollback state change."""
        model = CallbackExceptionModel()

        try:
            model.publish()
        except ValueError:
            pass

        assert model.state == "published"


class TestCallbackSignalOrder:
    """Test callback execution order relative to signals."""

    def setup_method(self):
        reset_invocation_log()
        # Connect signal handlers
        self.pre_handler = MagicMock()
        self.post_handler = MagicMock()

        def pre_signal_handler(sender, instance, name, source, target, **kwargs):
            invocation_log.append({
                "type": "pre_signal",
                "source": source,
                "target": target,
                "order": len(invocation_log),
            })

        def post_signal_handler(sender, instance, name, source, target, **kwargs):
            invocation_log.append({
                "type": "post_signal",
                "source": source,
                "target": target,
                "order": len(invocation_log),
            })

        self.pre_signal_handler = pre_signal_handler
        self.post_signal_handler = post_signal_handler
        pre_transition.connect(pre_signal_handler)
        post_transition.connect(post_signal_handler)

    def teardown_method(self):
        pre_transition.disconnect(self.pre_signal_handler)
        post_transition.disconnect(self.post_signal_handler)

    def test_callback_called_after_post_transition_signal(self):
        """on_success callback should be called after post_transition signal."""
        model = CallbackOrderModel()
        model.publish()

        # Check order: pre_signal -> post_signal -> callback
        types = [entry["type"] for entry in invocation_log]
        assert "pre_signal" in types
        assert "post_signal" in types
        assert "callback" in types

        pre_idx = types.index("pre_signal")
        post_idx = types.index("post_signal")
        callback_idx = types.index("callback")

        assert pre_idx < post_idx < callback_idx


class TestCallbackWithDynamicStates:
    """Test callbacks with dynamic state resolution."""

    def setup_method(self):
        reset_invocation_log()

    def test_callback_receives_correct_target_with_return_value(self):
        """Callback should receive the actual resolved target state."""
        model = CallbackWithReturnValueModel()

        model.review(approved=True)

        assert len(invocation_log) == 1
        assert invocation_log[0]["target"] == "approved"
        assert model.state == "approved"

    def test_callback_receives_rejected_target_with_return_value(self):
        """Callback should receive rejected target when returned."""
        model = CallbackWithReturnValueModel()

        model.review(approved=False)

        assert len(invocation_log) == 1
        assert invocation_log[0]["target"] == "rejected"
        assert model.state == "rejected"

    def test_callback_receives_correct_target_with_get_state(self):
        """Callback should receive correct target with GET_STATE."""
        model = CallbackWithGetStateModel()

        model.review(approved=True)

        assert len(invocation_log) == 1
        assert invocation_log[0]["target"] == "approved"

    def test_callback_receives_correct_target_with_get_state_rejected(self):
        """Callback should receive rejected target with GET_STATE."""
        model = CallbackWithGetStateModel()

        model.review(approved=False)

        assert len(invocation_log) == 1
        assert invocation_log[0]["target"] == "rejected"


class TestCallbackModifyingInstance:
    """Test callbacks that modify the instance."""

    def setup_method(self):
        reset_invocation_log()

    def test_callback_can_modify_instance(self):
        """Callback should be able to modify instance attributes."""
        model = CallbackModifyingModel()
        assert model.modified_by_callback is False

        model.publish()

        assert model.modified_by_callback is True
        assert model.state == "published"


class TestMultipleCallbacks:
    """Test multiple callbacks on different transitions."""

    def setup_method(self):
        reset_invocation_log()

    def test_each_transition_invokes_its_callback(self):
        """Each transition should invoke its own callback."""
        model = MultipleCallbackModel()

        model.go_to_b()
        model.go_to_c()
        model.go_to_d()

        assert len(invocation_log) == 3
        assert invocation_log[0]["source"] == "a"
        assert invocation_log[0]["target"] == "b"
        assert invocation_log[1]["source"] == "b"
        assert invocation_log[1]["target"] == "c"
        assert invocation_log[2]["source"] == "c"
        assert invocation_log[2]["target"] == "d"

    def test_callbacks_isolated_between_instances(self):
        """Callbacks on different instances should not interfere."""
        reset_invocation_log()

        model1 = MultipleCallbackModel()
        model2 = MultipleCallbackModel()

        model1.go_to_b()
        model2.go_to_b()

        assert len(invocation_log) == 2
        # Both should have same source/target but be separate invocations
        assert all(entry["source"] == "a" and entry["target"] == "b" for entry in invocation_log)


class TestCallbackWithOnError:
    """Test callback not invoked when on_error fires."""

    def setup_method(self):
        reset_invocation_log()

    def test_callback_not_invoked_when_on_error_fires(self):
        """Callback should NOT be invoked when transition raises and on_error is set."""
        model = CallbackWithOnErrorModel()

        with pytest.raises(ValueError, match="Publishing failed!"):
            model.publish()

        # Callback should NOT have been invoked
        assert len(invocation_log) == 0

        # State should be the error state
        assert model.state == "failed"


class TestCallbackIdempotency:
    """Test callback idempotency and repeated calls."""

    def setup_method(self):
        reset_invocation_log()

    def test_callback_not_called_when_transition_not_allowed(self):
        """Callback should not be called when transition is not allowed."""
        model = CallbackOrderModel()
        model.state = "published"  # Already published

        with pytest.raises(TransitionNotAllowed):
            model.publish()

        assert len(invocation_log) == 0

    def test_can_proceed_does_not_invoke_callback(self):
        """can_proceed should not invoke callback."""
        model = CallbackOrderModel()

        result = can_proceed(model.publish)

        assert result is True
        assert len(invocation_log) == 0


class TestCallbackWithArguments:
    """Test callbacks receive method arguments correctly."""

    def setup_method(self):
        reset_invocation_log()

    def test_callback_receives_positional_args(self):
        """Callback should receive positional arguments in method_args."""
        args_log = []

        def capturing_callback(instance, source, target, method_args=None, method_kwargs=None, **kwargs):
            args_log.append({
                "method_args": method_args,
                "method_kwargs": method_kwargs,
            })

        class ArgsModel(models.Model):
            state = FSMField(default="draft")

            @transition(field=state, source="draft", target="published", on_success=capturing_callback)
            def publish(self, reviewer, notes=""):
                pass

            class Meta:
                app_label = "tests"

        model = ArgsModel()
        model.publish("Alice", notes="Good work")

        assert len(args_log) == 1
        assert args_log[0]["method_args"] == ("Alice",)
        assert args_log[0]["method_kwargs"] == {"notes": "Good work"}

    def test_callback_receives_kwargs_only(self):
        """Callback should receive keyword-only arguments."""
        args_log = []

        def capturing_callback(instance, source, target, method_args=None, method_kwargs=None, **kwargs):
            args_log.append({
                "method_args": method_args,
                "method_kwargs": method_kwargs,
            })

        class KwargsModel(models.Model):
            state = FSMField(default="draft")

            @transition(field=state, source="draft", target="published", on_success=capturing_callback)
            def publish(self, *, reviewer, priority=1):
                pass

            class Meta:
                app_label = "tests"

        model = KwargsModel()
        model.publish(reviewer="Bob", priority=5)

        assert len(args_log) == 1
        assert args_log[0]["method_args"] == ()
        assert args_log[0]["method_kwargs"] == {"reviewer": "Bob", "priority": 5}


class TestCallbackWithConditions:
    """Test callbacks when transition has conditions."""

    def setup_method(self):
        reset_invocation_log()

    def test_callback_invoked_when_conditions_pass(self):
        """Callback should be invoked when conditions pass."""

        def always_true(instance):
            return True

        class ConditionModel(models.Model):
            state = FSMField(default="draft")

            @transition(
                field=state,
                source="draft",
                target="published",
                conditions=[always_true],
                on_success=logging_callback,
            )
            def publish(self):
                pass

            class Meta:
                app_label = "tests"

        model = ConditionModel()
        model.publish()

        assert len(invocation_log) == 1
        assert model.state == "published"

    def test_callback_not_invoked_when_conditions_fail(self):
        """Callback should NOT be invoked when conditions fail."""

        def always_false(instance):
            return False

        class ConditionModel(models.Model):
            state = FSMField(default="draft")

            @transition(
                field=state,
                source="draft",
                target="published",
                conditions=[always_false],
                on_success=logging_callback,
            )
            def publish(self):
                pass

            class Meta:
                app_label = "tests"

        model = ConditionModel()

        with pytest.raises(TransitionNotAllowed):
            model.publish()

        assert len(invocation_log) == 0
        assert model.state == "draft"
