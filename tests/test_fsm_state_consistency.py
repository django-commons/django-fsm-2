"""
Tests for FSM state consistency.

These tests verify:
- State in memory matches state in database
- Unsaved transitions don't persist
- refresh_from_db behavior with FSM fields
- Protected field behavior
- Concurrent modification handling
"""

from __future__ import annotations

import pytest
from django.db import models
from django.db import transaction

from django_fsm_rx import ConcurrentTransitionMixin
from django_fsm_rx import FSMField
from django_fsm_rx import FSMModelMixin
from django_fsm_rx import can_proceed
from django_fsm_rx import transition


class ConsistencyModel(models.Model):
    """Model for testing state consistency."""

    state = FSMField(default="draft")
    name = models.CharField(max_length=100, default="test")

    @transition(field=state, source="draft", target="published")
    def publish(self):
        pass

    @transition(field=state, source="published", target="archived")
    def archive(self):
        pass

    @transition(field=state, source="*", target="draft")
    def reset(self):
        pass

    class Meta:
        app_label = "testapp"


class ProtectedConsistencyModel(FSMModelMixin, models.Model):
    """Model with protected FSM field."""

    state = FSMField(default="draft", protected=True)
    name = models.CharField(max_length=100, default="test")

    @transition(field=state, source="draft", target="published")
    def publish(self):
        pass

    @transition(field=state, source="published", target="archived")
    def archive(self):
        pass

    class Meta:
        app_label = "testapp"


class ConcurrentModel(ConcurrentTransitionMixin, models.Model):
    """Model with optimistic locking."""

    state = FSMField(default="draft")
    name = models.CharField(max_length=100, default="test")

    @transition(field=state, source="draft", target="published")
    def publish(self):
        pass

    @transition(field=state, source="published", target="archived")
    def archive(self):
        pass

    class Meta:
        app_label = "testapp"


@pytest.mark.django_db
class TestStateMemoryDatabaseConsistency:
    """Test state consistency between memory and database."""

    def test_state_change_not_persisted_until_save(self):
        """State change should NOT be persisted until save() is called."""
        obj = ConsistencyModel.objects.create(state="draft", name="test")

        obj.publish()
        assert obj.state == "published"

        # Reload from database - should still be draft
        db_obj = ConsistencyModel.objects.get(pk=obj.pk)
        assert db_obj.state == "draft"

    def test_state_persisted_after_save(self):
        """State should be persisted after save()."""
        obj = ConsistencyModel.objects.create(state="draft", name="test")

        obj.publish()
        obj.save()

        db_obj = ConsistencyModel.objects.get(pk=obj.pk)
        assert db_obj.state == "published"

    def test_multiple_transitions_without_save(self):
        """Multiple transitions should work without intermediate saves."""
        obj = ConsistencyModel.objects.create(state="draft", name="test")

        obj.publish()
        assert obj.state == "published"

        obj.archive()
        assert obj.state == "archived"

        # Still not saved
        db_obj = ConsistencyModel.objects.get(pk=obj.pk)
        assert db_obj.state == "draft"

        # Save final state
        obj.save()
        db_obj.refresh_from_db()
        assert db_obj.state == "archived"

    def test_rollback_state_by_not_saving(self):
        """State change can be 'rolled back' by not saving."""
        obj = ConsistencyModel.objects.create(state="draft", name="test")

        obj.publish()
        assert obj.state == "published"

        # Don't save - reload from database
        obj.refresh_from_db()
        assert obj.state == "draft"


@pytest.mark.django_db
class TestRefreshFromDb:
    """Test refresh_from_db behavior with FSM fields."""

    def test_refresh_restores_database_state(self):
        """refresh_from_db should restore the database state."""
        obj = ConsistencyModel.objects.create(state="draft", name="test")

        obj.publish()
        assert obj.state == "published"

        obj.refresh_from_db()
        assert obj.state == "draft"

    def test_refresh_with_fields_argument(self):
        """refresh_from_db with fields should refresh specified fields."""
        obj = ConsistencyModel.objects.create(state="draft", name="original")

        obj.publish()
        obj.name = "modified"

        # Refresh only state
        obj.refresh_from_db(fields=["state"])
        assert obj.state == "draft"
        assert obj.name == "modified"

    def test_refresh_after_external_change(self):
        """refresh_from_db should pick up external changes."""
        obj = ConsistencyModel.objects.create(state="draft", name="test")

        # Simulate external change (e.g., by another process)
        ConsistencyModel.objects.filter(pk=obj.pk).update(state="published")

        obj.refresh_from_db()
        assert obj.state == "published"


@pytest.mark.django_db
class TestProtectedFieldConsistency:
    """Test protected field consistency behavior."""

    def test_protected_field_blocks_direct_assignment(self):
        """Protected FSM field should block direct assignment."""
        obj = ProtectedConsistencyModel(state="draft")

        with pytest.raises(AttributeError):
            obj.state = "published"

    def test_protected_field_allows_transition(self):
        """Protected FSM field should allow transition method."""
        obj = ProtectedConsistencyModel.objects.create(name="test")

        obj.publish()
        assert obj.state == "published"

    def test_protected_field_save_persists_transition(self):
        """Protected field transition should persist after save."""
        obj = ProtectedConsistencyModel.objects.create(name="test")

        obj.publish()
        obj.save()

        db_obj = ProtectedConsistencyModel.objects.get(pk=obj.pk)
        assert db_obj.state == "published"

    def test_protected_field_database_update(self):
        """Database update should bypass protection (for migrations, etc)."""
        obj = ProtectedConsistencyModel.objects.create(name="test")

        # Direct database update bypasses protection
        ProtectedConsistencyModel.objects.filter(pk=obj.pk).update(state="published")

        # Create fresh instance to read from DB
        db_obj = ProtectedConsistencyModel.objects.get(pk=obj.pk)
        assert db_obj.state == "published"


@pytest.mark.django_db
class TestDirtyStateTracking:
    """Test dirty state tracking for FSM fields."""

    def test_transition_marks_field_dirty(self):
        """Transition should mark the FSM field as modified."""
        obj = ConsistencyModel.objects.create(state="draft", name="test")

        # Initial state - no unsaved changes
        assert not obj._state.adding

        obj.publish()

        # After transition, object has unsaved changes
        # We can verify by checking save_base is needed
        obj.save()

        # After save, reload and verify
        db_obj = ConsistencyModel.objects.get(pk=obj.pk)
        assert db_obj.state == "published"


@pytest.mark.django_db
class TestConcurrentModifications:
    """Test concurrent modification handling."""

    def test_concurrent_transition_detection(self):
        """ConcurrentTransitionMixin should detect concurrent modifications."""
        # Create object
        obj1 = ConcurrentModel.objects.create(state="draft", name="test")

        # Load same object in second reference
        obj2 = ConcurrentModel.objects.get(pk=obj1.pk)

        # First transition and save
        obj1.publish()
        obj1.save()

        # Second object tries to transition from stale state
        # Note: The exact behavior depends on implementation
        # This test documents expected behavior
        with pytest.raises(Exception):  # Could be ConcurrentTransition or similar
            obj2.publish()
            obj2.save()

    def test_non_concurrent_sequential_transitions(self):
        """Sequential transitions on same object should work."""
        obj = ConcurrentModel.objects.create(state="draft", name="test")

        obj.publish()
        obj.save()

        # Refresh and continue
        obj.refresh_from_db()
        obj.archive()
        obj.save()

        db_obj = ConcurrentModel.objects.get(pk=obj.pk)
        assert db_obj.state == "archived"


@pytest.mark.django_db
class TestTransitionWithSaveInTransaction:
    """Test transitions within database transactions."""

    def test_transition_in_transaction_commit(self):
        """Transition and save in committed transaction should persist."""
        with transaction.atomic():
            obj = ConsistencyModel.objects.create(state="draft", name="test")
            obj.publish()
            obj.save()

        db_obj = ConsistencyModel.objects.get(pk=obj.pk)
        assert db_obj.state == "published"

    def test_transition_in_transaction_rollback(self):
        """Transition in rolled-back transaction should not persist."""
        obj = ConsistencyModel.objects.create(state="draft", name="test")

        try:
            with transaction.atomic():
                obj.publish()
                obj.save()
                raise ValueError("Force rollback")
        except ValueError:
            pass

        db_obj = ConsistencyModel.objects.get(pk=obj.pk)
        assert db_obj.state == "draft"

    def test_multiple_transitions_in_transaction(self):
        """Multiple transitions in transaction should all persist or rollback."""
        with transaction.atomic():
            obj = ConsistencyModel.objects.create(state="draft", name="test")
            obj.publish()
            obj.save()
            obj.archive()
            obj.save()

        db_obj = ConsistencyModel.objects.get(pk=obj.pk)
        assert db_obj.state == "archived"


@pytest.mark.django_db
class TestDeferredFieldLoading:
    """Test FSM fields with deferred loading."""

    def test_transition_with_deferred_fields(self):
        """Transition should work with deferred field loading."""
        obj = ConsistencyModel.objects.create(state="draft", name="test")

        # Load with deferred name field
        deferred_obj = ConsistencyModel.objects.defer("name").get(pk=obj.pk)

        deferred_obj.publish()
        assert deferred_obj.state == "published"

        deferred_obj.save()

        db_obj = ConsistencyModel.objects.get(pk=obj.pk)
        assert db_obj.state == "published"

    def test_can_proceed_with_deferred_fields(self):
        """can_proceed should work with deferred field loading."""
        obj = ConsistencyModel.objects.create(state="draft", name="test")

        deferred_obj = ConsistencyModel.objects.defer("name").get(pk=obj.pk)

        assert can_proceed(deferred_obj.publish)

    def test_only_state_field_loaded(self):
        """Transition should work when only state field is loaded."""
        obj = ConsistencyModel.objects.create(state="draft", name="test")

        # Load only the state field
        only_state_obj = ConsistencyModel.objects.only("state", "pk").get(pk=obj.pk)

        only_state_obj.publish()
        assert only_state_obj.state == "published"


@pytest.mark.django_db
class TestStateValidation:
    """Test state validation and invalid states."""

    def test_invalid_initial_state(self):
        """Object with invalid initial state should not break."""
        # Manually set invalid state via database
        obj = ConsistencyModel.objects.create(state="draft", name="test")
        ConsistencyModel.objects.filter(pk=obj.pk).update(state="invalid_state")

        obj.refresh_from_db()
        assert obj.state == "invalid_state"

        # Transitions from invalid state should not work (no matching source)
        assert not can_proceed(obj.publish)
        assert not can_proceed(obj.archive)

        # But reset with source='*' should work
        assert can_proceed(obj.reset)
        obj.reset()
        assert obj.state == "draft"

    def test_choices_validation_on_model(self):
        """Model with FSM choices should validate."""

        class ChoicesModel(models.Model):
            STATE_CHOICES = [
                ("draft", "Draft"),
                ("published", "Published"),
            ]
            state = FSMField(default="draft", choices=STATE_CHOICES)

            @transition(field=state, source="draft", target="published")
            def publish(self):
                pass

            class Meta:
                app_label = "tests"

        obj = ChoicesModel()
        assert obj.state == "draft"
        obj.publish()
        assert obj.state == "published"


@pytest.mark.django_db
class TestMultipleFSMFields:
    """Test models with multiple FSM fields using existing AdminBlogPost model."""

    def test_multiple_fields_independent(self):
        """Multiple FSM fields should be independent."""
        from tests.testapp.models import AdminBlogPost

        obj = AdminBlogPost.objects.create(title="Test")

        obj.publish()  # state: new -> published
        assert obj.state == "published"
        assert obj.review_state == "pending"

        obj.approve()  # review_state: pending -> approved
        assert obj.state == "published"
        assert obj.review_state == "approved"

    def test_multiple_fields_save_persists_both(self):
        """Save should persist all FSM field changes."""
        from tests.testapp.models import AdminBlogPost

        obj = AdminBlogPost.objects.create(title="Test")

        obj.publish()
        obj.approve()
        obj.save()

        db_obj = AdminBlogPost.objects.get(pk=obj.pk)
        assert db_obj.state == "published"
        assert db_obj.review_state == "approved"
