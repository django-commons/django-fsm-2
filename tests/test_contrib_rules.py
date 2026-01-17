"""
Tests for django-rules integration in django_fsm_rx.contrib.rules.

These tests verify the rules_permission and rules_predicate adapters
work correctly to integrate django-rules with FSM transitions.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from django_fsm_rx.contrib.rules import rules_permission, rules_predicate


class TestRulesPermission:
    """Test rules_permission adapter."""

    def test_rules_permission_returns_callable(self):
        """rules_permission should return a callable."""
        perm_checker = rules_permission("app.some_permission")
        assert callable(perm_checker)

    def test_rules_permission_has_descriptive_name(self):
        """The returned callable should have a descriptive name."""
        perm_checker = rules_permission("blog.publish_post")
        assert "rules_permission" in perm_checker.__name__
        assert "blog.publish_post" in perm_checker.__name__

    def test_rules_permission_has_docstring(self):
        """The returned callable should have a docstring."""
        perm_checker = rules_permission("blog.publish_post")
        assert perm_checker.__doc__ is not None
        assert "blog.publish_post" in perm_checker.__doc__

    def test_rules_permission_raises_import_error_without_rules(self):
        """Should raise ImportError with helpful message if rules not installed."""
        perm_checker = rules_permission("app.some_permission")

        mock_instance = MagicMock()
        mock_user = MagicMock()

        # Mock the import to simulate rules not being installed
        with patch.dict("sys.modules", {"rules": None}):
            # Force reimport by removing from cache
            import sys

            if "rules" in sys.modules:
                del sys.modules["rules"]

            with pytest.raises(ImportError) as exc_info:
                perm_checker(mock_instance, mock_user)

            assert "django-rules is required" in str(exc_info.value)
            assert "pip install rules" in str(exc_info.value)

    def test_rules_permission_calls_test_rule(self):
        """Should call rules.test_rule with correct arguments."""
        perm_checker = rules_permission("blog.can_publish")

        mock_instance = MagicMock()
        mock_user = MagicMock()

        # Mock the rules module
        mock_rules = MagicMock()
        mock_rules.test_rule.return_value = True

        with patch.dict("sys.modules", {"rules": mock_rules}):
            result = perm_checker(mock_instance, mock_user)

        assert result is True
        mock_rules.test_rule.assert_called_once_with(
            "blog.can_publish", mock_user, mock_instance
        )

    def test_rules_permission_returns_false_when_denied(self):
        """Should return False when rules.test_rule returns False."""
        perm_checker = rules_permission("blog.can_publish")

        mock_instance = MagicMock()
        mock_user = MagicMock()

        mock_rules = MagicMock()
        mock_rules.test_rule.return_value = False

        with patch.dict("sys.modules", {"rules": mock_rules}):
            result = perm_checker(mock_instance, mock_user)

        assert result is False


class TestRulesPredicate:
    """Test rules_predicate adapter."""

    def test_rules_predicate_returns_callable(self):
        """rules_predicate should return a callable."""

        def my_predicate(user, obj):
            return True

        wrapped = rules_predicate(my_predicate)
        assert callable(wrapped)

    def test_rules_predicate_has_descriptive_name(self):
        """The returned callable should have a descriptive name."""

        def is_owner(user, obj):
            return obj.owner == user

        wrapped = rules_predicate(is_owner)
        assert "rules_predicate" in wrapped.__name__
        assert "is_owner" in wrapped.__name__

    def test_rules_predicate_preserves_docstring(self):
        """The returned callable should preserve the predicate's docstring."""

        def is_admin(user, obj):
            """Check if user is an admin."""
            return user.is_admin

        wrapped = rules_predicate(is_admin)
        assert wrapped.__doc__ == "Check if user is an admin."

    def test_rules_predicate_swaps_arguments(self):
        """The wrapper should swap (instance, user) to (user, obj) for the predicate."""
        call_log = []

        def tracking_predicate(user, obj):
            call_log.append({"user": user, "obj": obj})
            return True

        wrapped = rules_predicate(tracking_predicate)

        mock_instance = MagicMock(name="instance")
        mock_user = MagicMock(name="user")

        # FSM calls with (instance, user)
        wrapped(mock_instance, mock_user)

        # Predicate should receive (user, obj)
        assert len(call_log) == 1
        assert call_log[0]["user"] is mock_user
        assert call_log[0]["obj"] is mock_instance

    def test_rules_predicate_returns_true(self):
        """Should return True when predicate returns True."""

        def always_true(user, obj):
            return True

        wrapped = rules_predicate(always_true)
        result = wrapped(MagicMock(), MagicMock())
        assert result is True

    def test_rules_predicate_returns_false(self):
        """Should return False when predicate returns False."""

        def always_false(user, obj):
            return False

        wrapped = rules_predicate(always_false)
        result = wrapped(MagicMock(), MagicMock())
        assert result is False

    def test_rules_predicate_coerces_to_bool(self):
        """Should coerce predicate result to boolean."""

        def returns_string(user, obj):
            return "truthy"

        def returns_none(user, obj):
            return None

        def returns_zero(user, obj):
            return 0

        wrapped_truthy = rules_predicate(returns_string)
        wrapped_none = rules_predicate(returns_none)
        wrapped_zero = rules_predicate(returns_zero)

        assert wrapped_truthy(MagicMock(), MagicMock()) is True
        assert wrapped_none(MagicMock(), MagicMock()) is False
        assert wrapped_zero(MagicMock(), MagicMock()) is False

    def test_rules_predicate_with_lambda(self):
        """Should work with lambda predicates."""
        wrapped = rules_predicate(lambda user, obj: user.is_staff)

        staff_user = MagicMock(is_staff=True)
        regular_user = MagicMock(is_staff=False)
        mock_obj = MagicMock()

        assert wrapped(mock_obj, staff_user) is True
        assert wrapped(mock_obj, regular_user) is False

    def test_rules_predicate_handles_unnamed_callable(self):
        """Should handle callables without __name__."""

        class CallableClass:
            def __call__(self, user, obj):
                return True

        wrapped = rules_predicate(CallableClass())
        assert "rules_predicate" in wrapped.__name__
        # Should not raise even without __name__
        assert wrapped(MagicMock(), MagicMock()) is True


class TestRulesIntegrationWithFSM:
    """Test rules adapters work correctly with FSM transitions."""

    def test_rules_permission_signature_matches_fsm(self):
        """rules_permission output should match FSM permission signature."""
        perm_checker = rules_permission("app.perm")

        # FSM permissions are called with (instance, user)
        # Verify it accepts these arguments
        import inspect

        sig = inspect.signature(perm_checker)
        params = list(sig.parameters.keys())
        assert len(params) == 2
        assert params[0] == "instance"
        assert params[1] == "user"

    def test_rules_predicate_signature_matches_fsm(self):
        """rules_predicate output should match FSM permission signature."""

        def predicate(user, obj):
            return True

        wrapped = rules_predicate(predicate)

        import inspect

        sig = inspect.signature(wrapped)
        params = list(sig.parameters.keys())
        assert len(params) == 2
        assert params[0] == "instance"
        assert params[1] == "user"


class TestModuleExports:
    """Test module exports."""

    def test_all_exports(self):
        """__all__ should contain expected exports."""
        from django_fsm_rx.contrib import rules as rules_module

        assert hasattr(rules_module, "__all__")
        assert "rules_permission" in rules_module.__all__
        assert "rules_predicate" in rules_module.__all__

    def test_can_import_from_module(self):
        """Should be able to import functions from module."""
        from django_fsm_rx.contrib.rules import rules_permission, rules_predicate

        assert callable(rules_permission)
        assert callable(rules_predicate)
