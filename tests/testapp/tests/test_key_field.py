from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

import django_fsm as fsm
from tests.testapp.models import DbState
from tests.testapp.models import DbStateAutoPk

FK_AVAILABLE_STATES = (
    ("_NEW_", "New"),
    ("_PUBLISHED_", "Published"),
    ("_HIDDEN_", "Hidden"),
    ("_REMOVED_", "Removed"),
    ("_STOLEN_", "Stolen"),
    ("_MODERATED_", "Moderated"),
)


class FSMKeyModelAbstract(models.Model):
    state: fsm.FSMKeyField

    @fsm.transition(field="state", source="_NEW_", target="_PUBLISHED_")
    def publish(self):
        pass

    @fsm.transition(field="state", source="_PUBLISHED_")
    def notify_all(self):
        pass

    @fsm.transition(field="state", source="_PUBLISHED_", target="_HIDDEN_")
    def hide(self):
        pass

    @fsm.transition(field="state", source="_NEW_", target="_REMOVED_")
    def remove(self):
        raise Exception("Upss")

    @fsm.transition(field="state", source=["_PUBLISHED_", "_HIDDEN_"], target="_STOLEN_")
    def steal(self):
        pass

    @fsm.transition(field="state", source=fsm.ANY_STATE, target="_MODERATED_")
    def moderate(self):
        pass


class FSMKeyModel(FSMKeyModelAbstract):
    state = fsm.FSMKeyField(DbState, default="_NEW_", protected=True, on_delete=models.CASCADE)


class FSMKeyFieldTestCase(TestCase):
    model: FSMKeyModelAbstract

    def setUp(self):
        DbState.objects.bulk_create(
            objs=[
                DbState(
                    pk=item[0],
                    label=item[1],
                )
                for item in FK_AVAILABLE_STATES
            ],
            ignore_conflicts=True,
        )

        self.model = FSMKeyModel()

    def test_initial_state_is_default(self):
        assert self.model.state == "_NEW_"

    def test_known_transition_should_succeed(self):
        assert fsm.can_proceed(self.model.publish)

        self.model.publish()
        assert self.model.state == "_PUBLISHED_"

        assert fsm.can_proceed(self.model.hide)

        self.model.hide()
        assert self.model.state == "_HIDDEN_"

    def test_unknown_transition_fails(self):
        assert not fsm.can_proceed(self.model.hide)

        with pytest.raises(fsm.InvalidTransition):
            self.model.hide()

    def test_state_non_changed_after_fail(self):
        assert fsm.can_proceed(self.model.remove)

        with pytest.raises(Exception, match="Upss"):
            self.model.remove()

        assert self.model.state == "_NEW_"

    def test_allowed_null_transition_should_succeed(self):
        assert fsm.can_proceed(self.model.publish)

        self.model.publish()
        self.model.notify_all()

        assert self.model.state == "_PUBLISHED_"

    def test_unknown_null_transition_should_fail(self):
        with pytest.raises(fsm.InvalidTransition):
            self.model.notify_all()

        assert self.model.state == "_NEW_"

    def test_multiple_source_support_path_1_works(self):
        self.model.publish()
        self.model.steal()

        assert self.model.state == "_STOLEN_"

    def test_multiple_source_support_path_2_works(self):
        self.model.publish()
        self.model.hide()
        self.model.steal()

        assert self.model.state == "_STOLEN_"

    def test_star_shortcut_succeed(self):
        assert fsm.can_proceed(self.model.moderate)

        self.model.moderate()
        assert self.model.state == "_MODERATED_"


class AutoPkFSMKeyModel(FSMKeyModelAbstract):
    state = fsm.FSMKeyField(
        DbStateAutoPk,
        to_field="name",  # FK with different column
        default="_NEW_",
        on_delete=models.CASCADE,
    )


class AutoPkFSMKeyFieldTestCase(FSMKeyFieldTestCase):
    model: FSMKeyModelAbstract

    def setUp(self):
        DbStateAutoPk.objects.bulk_create(
            objs=[
                DbStateAutoPk(
                    name=item[1],
                )
                for item in FK_AVAILABLE_STATES
            ],
            ignore_conflicts=True,
        )

        self.model = AutoPkFSMKeyModel()
