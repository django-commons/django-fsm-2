from __future__ import annotations

from django.db import models
from django.test import TestCase

from django_fsm import FSMField
from django_fsm import transition


class Insect(models.Model):
    class STATE:
        CATERPILLAR = "CTR"
        BUTTERFLY = "BTF"

    STATE_CHOICES = ((STATE.CATERPILLAR, "Caterpillar", "Caterpillar"), (STATE.BUTTERFLY, "Butterfly", "Butterfly"))

    state = FSMField(default=STATE.CATERPILLAR, state_choices=STATE_CHOICES)

    class Meta:
        app_label = "testapp"

    @transition(field=state, source=STATE.CATERPILLAR, target=STATE.BUTTERFLY)
    def cocoon(self):
        pass

    def fly(self):
        raise NotImplementedError

    def crawl(self):
        raise NotImplementedError


class Caterpillar(Insect):
    class Meta:
        app_label = "testapp"
        proxy = True

    def crawl(self):
        """
        Do crawl
        """


class Butterfly(Insect):
    class Meta:
        app_label = "testapp"
        proxy = True

    def fly(self):
        """
        Do fly
        """


class TestStateProxy(TestCase):
    def test_initial_proxy_set_succeed(self):
        insect = Insect()
        assert isinstance(insect, Caterpillar)

    def test_transition_proxy_set_succeed(self):
        insect = Insect()
        insect.cocoon()
        assert isinstance(insect, Butterfly)

    def test_load_proxy_set(self):
        Insect.objects.create(state=Insect.STATE.CATERPILLAR)
        Insect.objects.create(state=Insect.STATE.BUTTERFLY)

        insects = Insect.objects.all()
        assert {Caterpillar, Butterfly} == {insect.__class__ for insect in insects}
