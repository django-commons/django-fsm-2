from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

import django_fsm as fsm
from tests.testapp.models import DbState
from tests.testapp.models import DbStateAutoPk

FK_AVAILABLE_STATES = (
    ("NEW", "New"),
    ("PUBLISHED", "Published"),
    ("HIDDEN", "Hidden"),
    ("REMOVED", "Removed"),
    ("STOLEN", "Stolen"),
    ("MODERATED", "Moderated"),
)


class FSMKeyModelAbstract(models.Model):
    state: fsm.FSMKeyField

    @fsm.transition(field="state", source="NEW", target="PUBLISHED")
    def publish(self):
        pass

    @fsm.transition(field="state", source="PUBLISHED")
    def notify_all(self):
        pass

    @fsm.transition(field="state", source="PUBLISHED", target="HIDDEN")
    def hide(self):
        pass

    @fsm.transition(field="state", source="NEW", target="REMOVED")
    def remove(self):
        raise Exception("Upss")

    @fsm.transition(field="state", source=["PUBLISHED", "HIDDEN"], target="STOLEN")
    def steal(self):
        pass

    @fsm.transition(field="state", source=fsm.ANY_STATE, target="MODERATED")
    def moderate(self):
        pass


class FSMKeyModel(FSMKeyModelAbstract):
    state = fsm.FSMKeyField(DbState, default="NEW", protected=True, on_delete=models.CASCADE)


class FSMKeyFieldTestCase(TestCase):
    model: FSMKeyModelAbstract

    def setUp(self):
        DbState.objects.bulk_create(
            DbState(
                pk=item[0],
                label=item[1],
            )
            for item in FK_AVAILABLE_STATES
        )
        self.model = FSMKeyModel()

    def test_initial_state_instantiated(self):
        assert self.model.state == "NEW"

    def test_known_transition_should_succeed(self):
        assert fsm.can_proceed(self.model.publish)
        self.model.publish()
        assert self.model.state == "PUBLISHED"

        assert fsm.can_proceed(self.model.hide)
        self.model.hide()
        assert self.model.state == "HIDDEN"

    def test_unknown_transition_fails(self):
        assert not fsm.can_proceed(self.model.hide)
        with pytest.raises(fsm.TransitionNotAllowed):
            self.model.hide()

    def test_state_non_changed_after_fail(self):
        assert fsm.can_proceed(self.model.remove)
        with pytest.raises(Exception, match="Upss"):
            self.model.remove()
        assert self.model.state == "NEW"

    def test_allowed_null_transition_should_succeed(self):
        assert fsm.can_proceed(self.model.publish)
        self.model.publish()
        self.model.notify_all()
        assert self.model.state == "PUBLISHED"

    def test_unknown_null_transition_should_fail(self):
        with pytest.raises(fsm.TransitionNotAllowed):
            self.model.notify_all()
        assert self.model.state == "NEW"

    def test_multiple_source_support_path_1_works(self):
        self.model.publish()
        self.model.steal()
        assert self.model.state == "STOLEN"

    def test_multiple_source_support_path_2_works(self):
        self.model.publish()
        self.model.hide()
        self.model.steal()
        assert self.model.state == "STOLEN"

    def test_star_shortcut_succeed(self):
        assert fsm.can_proceed(self.model.moderate)
        self.model.moderate()
        assert self.model.state == "MODERATED"


class AutoPkFSMKeyModel(FSMKeyModelAbstract):
    state = fsm.FSMKeyField(
        DbStateAutoPk,
        to_field="name",  # FK with different column
        default="NEW",
        on_delete=models.CASCADE,
    )


class AutoPkFSMKeyFieldTestCase(FSMKeyFieldTestCase):
    model: FSMKeyModelAbstract

    def setUp(self):
        DbStateAutoPk.objects.bulk_create(
            [
                DbStateAutoPk(
                    name=item[1],
                )
                for item in FK_AVAILABLE_STATES
            ]
        )

        self.model = AutoPkFSMKeyModel()
