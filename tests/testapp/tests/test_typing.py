"""
Tests for type hints, type aliases, and public API exports.

These tests ensure that:
1. All public API exports are accessible
2. Type aliases are properly defined and exported
3. Classes have expected type annotations
4. The module is properly typed (py.typed marker exists)
"""

from __future__ import annotations

import os

from django.db import models
from django.test import TestCase

import django_fsm_2
from django_fsm_2 import ConcurrentTransition
from django_fsm_2 import ConcurrentTransitionMixin
from django_fsm_2 import FSMField
from django_fsm_2 import FSMFieldMixin
from django_fsm_2 import FSMIntegerField
from django_fsm_2 import FSMKeyField
from django_fsm_2 import FSMModelMixin
from django_fsm_2 import GET_STATE
from django_fsm_2 import InvalidResultState
from django_fsm_2 import RETURN_VALUE
from django_fsm_2 import State
from django_fsm_2 import Transition
from django_fsm_2 import TransitionNotAllowed
from django_fsm_2 import can_proceed
from django_fsm_2 import has_transition_perm
from django_fsm_2 import transition


# Define models at module level to avoid registration conflicts

class TypingTestTransitionModel(models.Model):
    state = FSMField(default="new")

    @transition(
        field=state,
        source="new",
        target="done",
        conditions=[lambda x: True],
        permission="test.perm",
        custom={"key": "value"},
    )
    def complete(self):
        pass

    class Meta:
        app_label = "testapp"


class TypingTestEqualityModel(models.Model):
    state = FSMField(default="new")

    @transition(field=state, source="new", target="done")
    def complete(self):
        pass

    class Meta:
        app_label = "testapp"


class TypingTestConditionMethodModel(models.Model):
    state = FSMField(default="new")
    approved = models.BooleanField(default=False)

    def is_approved(self):
        return self.approved

    @transition(
        field=state,
        source="new",
        target="done",
        conditions=[is_approved],
    )
    def complete(self):
        pass

    class Meta:
        app_label = "testapp"


class TypingTestConditionLambdaModel(models.Model):
    state = FSMField(default="new")
    value = models.IntegerField(default=0)

    @transition(
        field=state,
        source="new",
        target="done",
        conditions=[lambda x: x.value > 0],
    )
    def complete(self):
        pass

    class Meta:
        app_label = "testapp"


class TypingTestMultipleConditionsModel(models.Model):
    state = FSMField(default="new")
    a = models.BooleanField(default=False)
    b = models.BooleanField(default=False)

    @transition(
        field=state,
        source="new",
        target="done",
        conditions=[lambda x: x.a, lambda x: x.b],
    )
    def complete(self):
        pass

    class Meta:
        app_label = "testapp"


class TypingTestDefaultsModel(models.Model):
    state = FSMField(default="new")

    @transition(field=state, source="new", target="done")
    def complete(self):
        pass

    class Meta:
        app_label = "testapp"


class TestPublicAPIExports(TestCase):
    """Test that all public API exports are accessible."""

    def test_exception_classes_exported(self):
        """All exception classes should be exported."""
        self.assertTrue(issubclass(TransitionNotAllowed, Exception))
        self.assertTrue(issubclass(ConcurrentTransition, Exception))
        self.assertTrue(issubclass(InvalidResultState, Exception))

    def test_field_classes_exported(self):
        """All field classes should be exported."""
        self.assertTrue(issubclass(FSMField, FSMFieldMixin))
        self.assertTrue(issubclass(FSMIntegerField, FSMFieldMixin))
        self.assertTrue(issubclass(FSMKeyField, FSMFieldMixin))

    def test_mixin_classes_exported(self):
        """All mixin classes should be exported."""
        self.assertTrue(FSMModelMixin is not None)
        self.assertTrue(ConcurrentTransitionMixin is not None)
        self.assertTrue(FSMFieldMixin is not None)

    def test_state_classes_exported(self):
        """State resolution classes should be exported."""
        self.assertTrue(issubclass(RETURN_VALUE, State))
        self.assertTrue(issubclass(GET_STATE, State))
        self.assertTrue(State is not None)

    def test_transition_class_exported(self):
        """Transition class should be exported."""
        self.assertTrue(Transition is not None)

    def test_decorator_exported(self):
        """Transition decorator should be exported."""
        self.assertTrue(callable(transition))

    def test_helper_functions_exported(self):
        """Helper functions should be exported."""
        self.assertTrue(callable(can_proceed))
        self.assertTrue(callable(has_transition_perm))

    def test_all_exports_in_dunder_all(self):
        """All exports should be in __all__."""
        expected = {
            "TransitionNotAllowed",
            "ConcurrentTransition",
            "InvalidResultState",
            "FSMFieldMixin",
            "FSMField",
            "FSMIntegerField",
            "FSMKeyField",
            "FSMModelMixin",
            "ConcurrentTransitionMixin",
            "transition",
            "can_proceed",
            "has_transition_perm",
            "GET_STATE",
            "RETURN_VALUE",
            "State",
            "Transition",
            "FSMMeta",
        }
        actual = set(django_fsm_2.__all__)
        # Check all expected are present (may have more)
        self.assertTrue(expected.issubset(actual), f"Missing: {expected - actual}")


class TestTypeAliasesExist(TestCase):
    """Test that type aliases are properly defined in the module."""

    def test_state_value_type_alias(self):
        """StateValue type alias should be accessible."""
        from django_fsm_2 import StateValue
        self.assertIsNotNone(StateValue)

    def test_condition_func_type_alias(self):
        """ConditionFunc type alias should be accessible."""
        from django_fsm_2 import ConditionFunc
        self.assertIsNotNone(ConditionFunc)

    def test_permission_func_type_alias(self):
        """PermissionFunc type alias should be accessible."""
        from django_fsm_2 import PermissionFunc
        self.assertIsNotNone(PermissionFunc)

    def test_permission_type_alias(self):
        """PermissionType type alias should be accessible."""
        from django_fsm_2 import PermissionType
        self.assertIsNotNone(PermissionType)

    def test_state_target_type_alias(self):
        """StateTarget type alias should be accessible."""
        from django_fsm_2 import StateTarget
        self.assertIsNotNone(StateTarget)

    def test_state_source_type_alias(self):
        """StateSource type alias should be accessible."""
        from django_fsm_2 import StateSource
        self.assertIsNotNone(StateSource)

    def test_custom_dict_type_alias(self):
        """CustomDict type alias should be accessible."""
        from django_fsm_2 import CustomDict
        self.assertIsNotNone(CustomDict)


class TestPEP561Compliance(TestCase):
    """Test PEP 561 compliance (py.typed marker)."""

    def test_py_typed_marker_exists(self):
        """py.typed marker file should exist for PEP 561."""
        package_dir = os.path.dirname(django_fsm_2.__file__)
        py_typed_path = os.path.join(package_dir, "py.typed")
        self.assertTrue(
            os.path.exists(py_typed_path),
            f"py.typed marker not found at {py_typed_path}"
        )


class TestTransitionClassTyping(TestCase):
    """Test Transition class has proper typing."""

    def test_transition_attributes(self):
        """Transition instances should have typed attributes."""
        instance = TypingTestTransitionModel()
        transitions = list(instance.get_all_state_transitions())
        self.assertEqual(len(transitions), 1)

        t = transitions[0]
        # Check attributes exist and have expected types
        self.assertIsInstance(t.name, str)
        self.assertEqual(t.name, "complete")
        self.assertEqual(t.source, "new")
        self.assertEqual(t.target, "done")
        self.assertIsNone(t.on_error)
        self.assertIsInstance(t.conditions, list)
        self.assertEqual(t.permission, "test.perm")
        self.assertIsInstance(t.custom, dict)
        self.assertEqual(t.custom["key"], "value")

    def test_transition_equality(self):
        """Transition __eq__ should work with strings and Transitions."""
        instance = TypingTestEqualityModel()
        t = list(instance.get_all_state_transitions())[0]

        # Test equality with string
        self.assertEqual(t, "complete")
        self.assertNotEqual(t, "other")

        # Test equality with self
        self.assertEqual(t, t)

    def test_transition_hash(self):
        """Transition should be hashable."""
        instance = TypingTestEqualityModel()
        t = list(instance.get_all_state_transitions())[0]

        # Should be hashable
        self.assertIsInstance(hash(t), int)

        # Should be usable in sets/dicts
        s = {t}
        self.assertIn(t, s)


class TestExceptionTyping(TestCase):
    """Test exception classes have proper typing."""

    def test_transition_not_allowed_attributes(self):
        """TransitionNotAllowed should have object and method attributes."""
        exc = TransitionNotAllowed("test message", object="obj", method="meth")
        self.assertEqual(exc.object, "obj")
        self.assertEqual(exc.method, "meth")
        self.assertEqual(str(exc), "test message")

    def test_transition_not_allowed_without_kwargs(self):
        """TransitionNotAllowed should work without object/method kwargs."""
        exc = TransitionNotAllowed("test message")
        self.assertIsNone(exc.object)
        self.assertIsNone(exc.method)


class TestStateClassTyping(TestCase):
    """Test State classes have proper typing."""

    def test_return_value_with_allowed_states(self):
        """RETURN_VALUE should store allowed_states."""
        rv = RETURN_VALUE("a", "b", "c")
        self.assertEqual(rv.allowed_states, ("a", "b", "c"))

    def test_return_value_without_allowed_states(self):
        """RETURN_VALUE without args should have None allowed_states."""
        rv = RETURN_VALUE()
        self.assertIsNone(rv.allowed_states)

    def test_return_value_get_state(self):
        """RETURN_VALUE.get_state should return the result."""
        rv = RETURN_VALUE("a", "b")
        state = rv.get_state(None, None, "a")
        self.assertEqual(state, "a")

    def test_return_value_invalid_state(self):
        """RETURN_VALUE.get_state should raise for invalid states."""
        rv = RETURN_VALUE("a", "b")
        with self.assertRaises(InvalidResultState):
            rv.get_state(None, None, "c")

    def test_get_state_with_func(self):
        """GET_STATE should call func to determine state."""
        def compute(instance, *args, **kwargs):
            return "computed"

        gs = GET_STATE(compute, states=["computed", "other"])
        state = gs.get_state(None, None, None)
        self.assertEqual(state, "computed")

    def test_get_state_with_args(self):
        """GET_STATE should pass args to func."""
        def compute(instance, x, y):
            return f"{x}_{y}"

        gs = GET_STATE(compute)
        state = gs.get_state(None, None, None, args=(1, 2))
        self.assertEqual(state, "1_2")

    def test_get_state_invalid_result(self):
        """GET_STATE should raise for invalid computed states."""
        def compute(instance):
            return "invalid"

        gs = GET_STATE(compute, states=["valid"])
        with self.assertRaises(InvalidResultState):
            gs.get_state(None, None, None)


class TestFSMMetaTyping(TestCase):
    """Test FSMMeta class functionality."""

    def test_fsm_meta_exported(self):
        """FSMMeta should be exported."""
        from django_fsm_2 import FSMMeta
        self.assertIsNotNone(FSMMeta)

    def test_fsm_meta_transitions_dict(self):
        """FSMMeta should maintain transitions dict."""
        from django_fsm_2 import FSMMeta

        meta = FSMMeta(field="test", method=lambda: None)
        self.assertIsInstance(meta.transitions, dict)
        self.assertEqual(len(meta.transitions), 0)

    def test_fsm_meta_add_transition(self):
        """FSMMeta.add_transition should add transitions."""
        from django_fsm_2 import FSMMeta

        meta = FSMMeta(field="test", method=lambda: None)
        meta.add_transition(
            method=lambda: None,
            source="new",
            target="done",
        )
        self.assertIn("new", meta.transitions)

    def test_fsm_meta_duplicate_transition_raises(self):
        """FSMMeta should raise on duplicate source transitions."""
        from django_fsm_2 import FSMMeta

        meta = FSMMeta(field="test", method=lambda: None)
        meta.add_transition(method=lambda: None, source="new", target="done")

        with self.assertRaises(AssertionError):
            meta.add_transition(method=lambda: None, source="new", target="other")

    def test_fsm_meta_has_transition(self):
        """FSMMeta.has_transition should check state availability."""
        from django_fsm_2 import FSMMeta

        meta = FSMMeta(field="test", method=lambda: None)
        meta.add_transition(method=lambda: None, source="new", target="done")

        self.assertTrue(meta.has_transition("new"))
        self.assertFalse(meta.has_transition("other"))

    def test_fsm_meta_wildcard_transition(self):
        """FSMMeta should handle wildcard '*' transitions."""
        from django_fsm_2 import FSMMeta

        meta = FSMMeta(field="test", method=lambda: None)
        meta.add_transition(method=lambda: None, source="*", target="done")

        self.assertTrue(meta.has_transition("any_state"))
        self.assertTrue(meta.has_transition("another"))

    def test_fsm_meta_plus_transition(self):
        """FSMMeta should handle '+' (any except target) transitions."""
        from django_fsm_2 import FSMMeta

        meta = FSMMeta(field="test", method=lambda: None)
        meta.add_transition(method=lambda: None, source="+", target="done")

        self.assertTrue(meta.has_transition("any_state"))
        self.assertFalse(meta.has_transition("done"))  # target excluded


class TestConditionTyping(TestCase):
    """Test condition functions work with proper typing."""

    def test_condition_with_model_method(self):
        """Model method conditions should work."""
        instance = TypingTestConditionMethodModel()
        self.assertFalse(can_proceed(instance.complete))

        instance.approved = True
        self.assertTrue(can_proceed(instance.complete))

    def test_condition_with_lambda(self):
        """Lambda conditions should work."""
        instance = TypingTestConditionLambdaModel()
        self.assertFalse(can_proceed(instance.complete))

        instance.value = 10
        self.assertTrue(can_proceed(instance.complete))

    def test_multiple_conditions(self):
        """Multiple conditions should all be checked."""
        instance = TypingTestMultipleConditionsModel()
        self.assertFalse(can_proceed(instance.complete))

        instance.a = True
        self.assertFalse(can_proceed(instance.complete))

        instance.b = True
        self.assertTrue(can_proceed(instance.complete))


class TestTransitionDecoratorDefaults(TestCase):
    """Test transition decorator handles None defaults properly."""

    def test_conditions_default_empty_list(self):
        """Conditions should default to empty list, not None."""
        instance = TypingTestDefaultsModel()
        t = list(instance.get_all_state_transitions())[0]
        # Should be empty list, not None
        self.assertIsInstance(t.conditions, list)
        self.assertEqual(len(t.conditions), 0)

    def test_custom_default_empty_dict(self):
        """Custom should default to empty dict, not None."""
        instance = TypingTestDefaultsModel()
        t = list(instance.get_all_state_transitions())[0]
        # Should be empty dict, not None
        self.assertIsInstance(t.custom, dict)
        self.assertEqual(len(t.custom), 0)


class TestSignalsTyping(TestCase):
    """Test signals module typing."""

    def test_signals_are_signal_instances(self):
        """Signals should be Django Signal instances."""
        from django.dispatch import Signal
        from django_fsm_2.signals import post_transition
        from django_fsm_2.signals import pre_transition

        self.assertIsInstance(pre_transition, Signal)
        self.assertIsInstance(post_transition, Signal)
