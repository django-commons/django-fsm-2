"""
Edge case tests for django-fsm-2.

These tests cover edge cases and ensure robustness of the FSM implementation.
"""

from __future__ import annotations

from django.contrib.auth import get_user_model
from django.db import models
from django.test import TestCase

from django_fsm_rx import GET_STATE
from django_fsm_rx import RETURN_VALUE
from django_fsm_rx import FSMField
from django_fsm_rx import FSMIntegerField
from django_fsm_rx import FSMModelMixin
from django_fsm_rx import can_proceed
from django_fsm_rx import has_transition_perm
from django_fsm_rx import transition

User = get_user_model()


# Define all models at module level to avoid Django model registration conflicts


class MultiSourceListModel(models.Model):
    state = FSMField(default="a")

    @transition(field=state, source=["a", "b", "c"], target="done")
    def complete(self):
        pass

    class Meta:
        app_label = "testapp"


class MultiSourceTupleModel(models.Model):
    state = FSMField(default="a")

    @transition(field=state, source=("a", "b"), target="done")
    def complete(self):
        pass

    class Meta:
        app_label = "testapp"


class MultiSourceSetModel(models.Model):
    state = FSMField(default="a")

    @transition(field=state, source={"a", "b"}, target="done")
    def complete(self):
        pass

    class Meta:
        app_label = "testapp"


class StarWildcardModel(models.Model):
    state = FSMField(default="initial")

    @transition(field=state, source="*", target="cancelled")
    def cancel(self):
        pass

    class Meta:
        app_label = "testapp"


class PlusWildcardModel(models.Model):
    state = FSMField(default="initial")

    @transition(field=state, source="+", target="reset")
    def reset(self):
        pass

    class Meta:
        app_label = "testapp"


class ProtectedFieldModel(models.Model):
    state = FSMField(default="new", protected=True)

    @transition(field=state, source="new", target="done")
    def complete(self):
        pass

    class Meta:
        app_label = "testapp"


class FSMMixinNoProtectedModel(FSMModelMixin, models.Model):
    state = FSMField(default="new", protected=False)

    class Meta:
        app_label = "testapp"


class FSMMixinMixedFieldsModel(FSMModelMixin, models.Model):
    state1 = FSMField(default="new", protected=True)
    state2 = FSMField(default="new", protected=False)

    class Meta:
        app_label = "testapp"


class IntState:
    NEW = 1
    PROCESSING = 2
    DONE = 3


class IntegerStatesModel(models.Model):
    state = FSMIntegerField(default=IntState.NEW)

    @transition(field=state, source=IntState.NEW, target=IntState.PROCESSING)
    def start(self):
        pass

    @transition(field=state, source=IntState.PROCESSING, target=IntState.DONE)
    def finish(self):
        pass

    class Meta:
        app_label = "testapp"


class IntegerWildcardModel(models.Model):
    state = FSMIntegerField(default=1)

    @transition(field=state, source="*", target=0)
    def reset(self):
        pass

    class Meta:
        app_label = "testapp"


class CustomError(Exception):
    pass


class OnErrorModel(models.Model):
    state = FSMField(default="new")

    @transition(field=state, source="new", target="done", on_error="failed")
    def complete_with_error_handler(self):
        pass

    @transition(field=state, source="new", target="done", on_error="failed")
    def complete_raises(self):
        raise CustomError("Something went wrong")

    @transition(field=state, source="new", target="done")
    def complete_no_error_handler(self):
        raise CustomError("Something went wrong")

    class Meta:
        app_label = "testapp"


class ReturnValueAnyModel(models.Model):
    state = FSMField(default="new")

    @transition(field=state, source="new", target=RETURN_VALUE())
    def change(self, new_state):
        return new_state

    class Meta:
        app_label = "testapp"


class GetStateKwargsModel(models.Model):
    state = FSMField(default="new")

    @staticmethod
    def compute_state(instance, **kwargs):
        return kwargs.get("target", "default")

    @transition(field=state, source="new", target=GET_STATE(compute_state.__func__))
    def change(self, target=None):
        pass

    class Meta:
        app_label = "testapp"


class ReturnValueModel(models.Model):
    state = FSMField(default="new")

    @transition(field=state, source="new", target="done")
    def complete_simple(self):
        return "success"

    @transition(field=state, source="new", target="done")
    def complete_complex(self):
        return {"status": "ok", "data": [1, 2, 3]}

    class Meta:
        app_label = "testapp"


class ConditionModel(models.Model):
    state = FSMField(default="new")

    @transition(
        field=state,
        source="new",
        target="done",
        conditions=[lambda x: False],  # Always fails
    )
    def complete(self):
        pass

    class Meta:
        app_label = "testapp"


class RegularMethodModel(models.Model):
    state = FSMField(default="new")

    def regular_method(self):
        pass

    class Meta:
        app_label = "testapp"


class NoPermissionModel(models.Model):
    state = FSMField(default="new")

    @transition(field=state, source="new", target="done")
    def complete(self):
        pass

    class Meta:
        app_label = "testapp"


class TargetNoneModel(models.Model):
    state = FSMField(default="active")

    @transition(field=state, source="active", target=None)
    def validate(self):
        return "validated"

    class Meta:
        app_label = "testapp"


class MultiDecoratorModel(models.Model):
    state = FSMField(default="a")

    @transition(field=state, source="a", target="result_a")
    @transition(field=state, source="b", target="result_b")
    def process(self):
        pass

    class Meta:
        app_label = "testapp"


class StringFieldNameModel(models.Model):
    state = FSMField(default="new")

    @transition(field="state", source="new", target="done")
    def complete(self):
        pass

    class Meta:
        app_label = "testapp"


# Test classes


class TestMultipleSourceStates(TestCase):
    """Test transitions from multiple source states."""

    def test_list_of_sources(self):
        """Transition with list of source states should work."""
        # From 'a'
        instance = MultiSourceListModel()
        self.assertTrue(can_proceed(instance.complete))
        instance.complete()
        self.assertEqual(instance.state, "done")

        # From 'b'
        instance = MultiSourceListModel()
        instance.state = "b"
        self.assertTrue(can_proceed(instance.complete))
        instance.complete()
        self.assertEqual(instance.state, "done")

        # From 'c'
        instance = MultiSourceListModel()
        instance.state = "c"
        self.assertTrue(can_proceed(instance.complete))

        # From invalid state
        instance = MultiSourceListModel()
        instance.state = "invalid"
        self.assertFalse(can_proceed(instance.complete))

    def test_tuple_of_sources(self):
        """Transition with tuple of source states should work."""
        instance = MultiSourceTupleModel()
        self.assertTrue(can_proceed(instance.complete))

    def test_set_of_sources(self):
        """Transition with set of source states should work."""
        instance = MultiSourceSetModel()
        self.assertTrue(can_proceed(instance.complete))


class TestWildcardTransitions(TestCase):
    """Test wildcard source transitions."""

    def test_star_wildcard(self):
        """'*' wildcard should match any state."""
        for state in ["initial", "processing", "done", "anything"]:
            instance = StarWildcardModel()
            instance.state = state
            self.assertTrue(can_proceed(instance.cancel))
            instance.cancel()
            self.assertEqual(instance.state, "cancelled")

    def test_plus_wildcard_excludes_target(self):
        """'+' wildcard should match any state except target."""
        # Should work from any state except 'reset'
        for state in ["initial", "processing", "done"]:
            instance = PlusWildcardModel()
            instance.state = state
            self.assertTrue(can_proceed(instance.reset))

        # Should NOT work from 'reset' state
        instance = PlusWildcardModel()
        instance.state = "reset"
        self.assertFalse(can_proceed(instance.reset))


class TestProtectedFieldEdgeCases(TestCase):
    """Test protected field edge cases."""

    def test_protected_field_initial_set(self):
        """Protected field should allow initial value set."""
        instance = ProtectedFieldModel()
        self.assertEqual(instance.state, "new")

    def test_protected_field_blocks_direct_change(self):
        """Protected field should block direct modification after initial set."""
        instance = ProtectedFieldModel()
        # This sets the initial value
        _ = instance.state

        # Direct modification should raise
        with self.assertRaises(AttributeError):
            instance.state = "hacked"

    def test_protected_field_allows_transition(self):
        """Protected field should allow state change via transition."""
        instance = ProtectedFieldModel()
        instance.complete()  # Should work
        self.assertEqual(instance.state, "done")


class TestFSMModelMixinEdgeCases(TestCase):
    """Test FSMModelMixin edge cases."""

    def test_mixin_with_no_protected_fields(self):
        """FSMModelMixin should work with non-protected FSM fields."""
        instance = FSMMixinNoProtectedModel()
        protected = instance._get_protected_fsm_fields()
        self.assertEqual(protected, set())

    def test_mixin_with_mixed_fields(self):
        """FSMModelMixin should handle multiple FSM fields."""
        instance = FSMMixinMixedFieldsModel()
        protected = instance._get_protected_fsm_fields()
        self.assertIn("state1", protected)
        self.assertNotIn("state2", protected)


class TestIntegerFieldStates(TestCase):
    """Test FSMIntegerField edge cases."""

    def test_integer_states(self):
        """FSMIntegerField should work with integer states."""
        instance = IntegerStatesModel()
        self.assertEqual(instance.state, 1)

        instance.start()
        self.assertEqual(instance.state, 2)

        instance.finish()
        self.assertEqual(instance.state, 3)

    def test_integer_wildcard(self):
        """Wildcard should work with integer states."""
        for state in [1, 2, 3, 100]:
            instance = IntegerWildcardModel()
            instance.state = state
            self.assertTrue(can_proceed(instance.reset))
            instance.reset()
            self.assertEqual(instance.state, 0)


class TestOnErrorEdgeCases(TestCase):
    """Test on_error state handling edge cases."""

    def test_on_error_with_no_exception(self):
        """Normal transition should not use on_error state."""
        instance = OnErrorModel()
        instance.complete_with_error_handler()
        self.assertEqual(instance.state, "done")

    def test_on_error_with_exception(self):
        """Exception should transition to on_error state."""
        instance = OnErrorModel()
        with self.assertRaises(CustomError):
            instance.complete_raises()

        self.assertEqual(instance.state, "failed")

    def test_on_error_not_defined(self):
        """Without on_error, exception should not change state."""
        instance = OnErrorModel()
        with self.assertRaises(CustomError):
            instance.complete_no_error_handler()

        # State unchanged
        self.assertEqual(instance.state, "new")


class TestDynamicStateEdgeCases(TestCase):
    """Test RETURN_VALUE and GET_STATE edge cases."""

    def test_return_value_with_none_result(self):
        """RETURN_VALUE without allowed_states should accept any value."""
        instance = ReturnValueAnyModel()
        instance.change("anything")
        self.assertEqual(instance.state, "anything")

    def test_get_state_with_kwargs(self):
        """GET_STATE should pass kwargs to func."""
        instance = GetStateKwargsModel()
        instance.change(target="custom")
        self.assertEqual(instance.state, "custom")


class TestTransitionWithReturnValue(TestCase):
    """Test that transition methods can return values."""

    def test_transition_returns_value(self):
        """Transition method return value should be preserved."""
        instance = ReturnValueModel()
        result = instance.complete_simple()
        self.assertEqual(result, "success")
        self.assertEqual(instance.state, "done")

    def test_transition_returns_complex_value(self):
        """Transition can return complex values."""
        instance = ReturnValueModel()
        result = instance.complete_complex()
        self.assertEqual(result, {"status": "ok", "data": [1, 2, 3]})


class TestCanProceedEdgeCases(TestCase):
    """Test can_proceed edge cases."""

    def test_can_proceed_skip_conditions(self):
        """can_proceed with check_conditions=False should skip conditions."""
        instance = ConditionModel()

        # With conditions checked, should return False
        self.assertFalse(can_proceed(instance.complete))

        # Without conditions, should return True (transition exists)
        self.assertTrue(can_proceed(instance.complete, check_conditions=False))

    def test_can_proceed_non_transition_raises(self):
        """can_proceed on non-transition method should raise TypeError."""
        instance = RegularMethodModel()
        with self.assertRaises(TypeError) as ctx:
            can_proceed(instance.regular_method)

        self.assertIn("not transition", str(ctx.exception))


class TestHasTransitionPermEdgeCases(TestCase):
    """Test has_transition_perm edge cases."""

    def test_has_transition_perm_non_transition_raises(self):
        """has_transition_perm on non-transition method should raise."""
        instance = RegularMethodModel()
        user = User(username="test")

        with self.assertRaises(TypeError) as ctx:
            has_transition_perm(instance.regular_method, user)

        self.assertIn("not transition", str(ctx.exception))

    def test_has_transition_perm_no_permission_required(self):
        """Transition without permission should allow any user."""
        instance = NoPermissionModel()
        user = User(username="test")

        self.assertTrue(has_transition_perm(instance.complete, user))


class TestTargetNone(TestCase):
    """Test transition with target=None (validation only)."""

    def test_target_none_no_state_change(self):
        """Transition with target=None should validate but not change state."""
        instance = TargetNoneModel()
        result = instance.validate()

        # State should not change
        self.assertEqual(instance.state, "active")
        self.assertEqual(result, "validated")

    def test_target_none_validates_source(self):
        """Transition with target=None should still validate source state."""
        instance = TargetNoneModel()
        instance.state = "inactive"
        # Should not be allowed from 'inactive'
        self.assertFalse(can_proceed(instance.validate))


class TestMultipleTransitionsOnSameMethod(TestCase):
    """Test stacking multiple @transition decorators."""

    def test_multiple_transitions_different_sources(self):
        """Multiple @transition decorators on same method should work."""
        # From 'a'
        instance = MultiDecoratorModel()
        instance.process()
        self.assertEqual(instance.state, "result_a")

        # From 'b'
        instance = MultiDecoratorModel()
        instance.state = "b"
        instance.process()
        self.assertEqual(instance.state, "result_b")

        # From invalid
        instance = MultiDecoratorModel()
        instance.state = "c"
        self.assertFalse(can_proceed(instance.process))


class TestFieldByName(TestCase):
    """Test referencing FSM field by name (string)."""

    def test_field_by_string_name(self):
        """Transition should work with field name as string."""
        instance = StringFieldNameModel()
        self.assertTrue(can_proceed(instance.complete))
        instance.complete()
        self.assertEqual(instance.state, "done")
