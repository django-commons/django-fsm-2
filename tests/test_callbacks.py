"""
Tests for on_success callback functionality in transitions.

The on_success callback provides an alternative to signals for executing
side effects after successful transitions.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from django.db import models

from django_fsm_rx import FSMField
from django_fsm_rx import TransitionNotAllowed
from django_fsm_rx import transition

# Track callback invocations for testing
callback_log: list[dict] = []


def reset_callback_log():
    """Reset the callback log before each test."""
    callback_log.clear()


def simple_callback(instance, source, target, **kwargs):
    """Simple callback that logs the transition."""
    callback_log.append(
        {
            "instance": instance,
            "source": source,
            "target": target,
            "kwargs": kwargs,
        }
    )


def callback_with_args(instance, source, target, method_args, method_kwargs, **kwargs):
    """Callback that also captures method arguments."""
    callback_log.append(
        {
            "instance": instance,
            "source": source,
            "target": target,
            "method_args": method_args,
            "method_kwargs": method_kwargs,
        }
    )


class CallbackModel(models.Model):
    """Test model with on_success callbacks."""

    state = FSMField(default="draft")

    @transition(field=state, source="draft", target="published", on_success=simple_callback)
    def publish(self):
        """Publish with callback."""
        pass

    @transition(field=state, source="draft", target="review")
    def submit_for_review(self):
        """Transition without callback."""
        pass

    @transition(field=state, source="review", target="published", on_success=callback_with_args)
    def approve(self, reviewer_name: str, notes: str = ""):
        """Approve with callback that captures arguments."""
        pass

    @transition(field=state, source="*", target="archived", on_success=simple_callback)
    def archive(self):
        """Archive from any state with callback."""
        pass

    class Meta:
        app_label = "tests"


class CallbackErrorModel(models.Model):
    """Test model for callback error scenarios."""

    state = FSMField(default="draft")

    @transition(field=state, source="draft", target="published", on_success=simple_callback, on_error="failed")
    def publish_risky(self):
        """Transition that might fail."""
        raise ValueError("Something went wrong")

    class Meta:
        app_label = "tests"


class TestOnSuccessCallback:
    """Test basic on_success callback functionality."""

    def setup_method(self):
        """Reset callback log before each test."""
        reset_callback_log()

    def test_callback_invoked_on_success(self):
        """Callback should be called after successful transition."""
        model = CallbackModel()
        model.publish()

        assert len(callback_log) == 1
        assert callback_log[0]["source"] == "draft"
        assert callback_log[0]["target"] == "published"
        assert callback_log[0]["instance"] is model

    def test_callback_not_invoked_when_no_callback(self):
        """No callback should be invoked when on_success is not specified."""
        model = CallbackModel()
        model.submit_for_review()

        assert len(callback_log) == 0
        assert model.state == "review"

    def test_callback_receives_method_arguments(self):
        """Callback should receive the method's arguments."""
        model = CallbackModel()
        model.state = "review"
        model.approve("Alice", notes="Looks good!")

        assert len(callback_log) == 1
        assert callback_log[0]["method_args"] == ("Alice",)
        assert callback_log[0]["method_kwargs"] == {"notes": "Looks good!"}

    def test_callback_with_wildcard_source(self):
        """Callback should work with wildcard source transitions."""
        model = CallbackModel()
        model.state = "published"
        model.archive()

        assert len(callback_log) == 1
        assert callback_log[0]["source"] == "published"
        assert callback_log[0]["target"] == "archived"


class TestCallbackNotInvokedOnError:
    """Test that callbacks are not invoked when transition fails."""

    def setup_method(self):
        """Reset callback log before each test."""
        reset_callback_log()

    def test_callback_not_invoked_when_transition_raises(self):
        """Callback should NOT be invoked when transition method raises."""
        model = CallbackErrorModel()

        with pytest.raises(ValueError, match="Something went wrong"):
            model.publish_risky()

        # Callback should not have been called
        assert len(callback_log) == 0
        # State should have changed to on_error state
        assert model.state == "failed"

    def test_callback_not_invoked_on_transition_not_allowed(self):
        """Callback should NOT be invoked when transition is not allowed."""
        model = CallbackModel()
        model.state = "published"

        with pytest.raises(TransitionNotAllowed):
            model.publish()  # Can't publish when already published

        assert len(callback_log) == 0


class TestCallbackWithMock:
    """Test callbacks using mock objects for verification."""

    def test_callback_called_with_correct_signature(self):
        """Verify callback is called with expected keyword arguments."""
        mock_callback = MagicMock()

        class MockCallbackModel(models.Model):
            state = FSMField(default="draft")

            @transition(field=state, source="draft", target="published", on_success=mock_callback)
            def publish(self, message: str):
                pass

            class Meta:
                app_label = "tests"

        model = MockCallbackModel()
        model.publish("Hello world")

        mock_callback.assert_called_once()
        call_kwargs = mock_callback.call_args.kwargs
        assert call_kwargs["instance"] is model
        assert call_kwargs["source"] == "draft"
        assert call_kwargs["target"] == "published"
        assert call_kwargs["method_args"] == ("Hello world",)
        assert call_kwargs["method_kwargs"] == {}

    def test_multiple_transitions_each_callback(self):
        """Each transition should invoke its own callback."""
        mock1 = MagicMock()
        mock2 = MagicMock()

        class MultiCallbackModel(models.Model):
            state = FSMField(default="a")

            @transition(field=state, source="a", target="b", on_success=mock1)
            def go_to_b(self):
                pass

            @transition(field=state, source="b", target="c", on_success=mock2)
            def go_to_c(self):
                pass

            class Meta:
                app_label = "tests"

        model = MultiCallbackModel()
        model.go_to_b()
        model.go_to_c()

        assert mock1.call_count == 1
        assert mock2.call_count == 1
        assert mock1.call_args.kwargs["target"] == "b"
        assert mock2.call_args.kwargs["target"] == "c"


class TestCallbackWithPrefixWildcard:
    """Test callbacks with prefix wildcard transitions."""

    def setup_method(self):
        """Reset callback log before each test."""
        reset_callback_log()

    def test_callback_with_prefix_wildcard_source(self):
        """Callback should work with prefix wildcard sources like 'WRK-*'."""

        class HierarchicalCallbackModel(models.Model):
            state = FSMField(default="DRF-NEW-CRT")

            @transition(field=state, source="DRF-*", target="WRK-INS-PRG")
            def start(self):
                pass

            @transition(field=state, source="WRK-*", target="CMP-STD-DON", on_success=simple_callback)
            def complete(self):
                pass

            class Meta:
                app_label = "tests"

        model = HierarchicalCallbackModel()
        model.start()
        assert model.state == "WRK-INS-PRG"

        model.complete()
        assert model.state == "CMP-STD-DON"
        assert len(callback_log) == 1
        assert callback_log[0]["source"] == "WRK-INS-PRG"
        assert callback_log[0]["target"] == "CMP-STD-DON"


class TestCallbackWithMultipleSources:
    """Test callbacks with multiple source states."""

    def setup_method(self):
        """Reset callback log before each test."""
        reset_callback_log()

    def test_callback_works_for_each_source_in_list(self):
        """Callback should be invoked regardless of which source state was used."""

        class MultiSourceModel(models.Model):
            state = FSMField(default="draft")

            @transition(field=state, source=["draft", "review"], target="published", on_success=simple_callback)
            def publish(self):
                pass

            class Meta:
                app_label = "tests"

        # From draft
        model1 = MultiSourceModel()
        model1.publish()
        assert callback_log[-1]["source"] == "draft"

        # From review
        model2 = MultiSourceModel()
        model2.state = "review"
        model2.publish()
        assert callback_log[-1]["source"] == "review"

        assert len(callback_log) == 2
