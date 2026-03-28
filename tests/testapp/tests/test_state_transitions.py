from __future__ import annotations

from django.db import models
from django.test import TestCase

import django_fsm as fsm


class Insect(models.Model):
    class STATE:
        CATERPILLAR = "CTR"
        BUTTERFLY = "BTF"

    STATE_CHOICES = (
        (STATE.CATERPILLAR, "Caterpillar", "Caterpillar"),
        (STATE.BUTTERFLY, "Butterfly", "Butterfly"),
    )

    state = fsm.FSMField(default=STATE.CATERPILLAR, state_choices=STATE_CHOICES)

    objects: models.Manager[Insect] = models.Manager()

    @fsm.transition(field=state, source=STATE.CATERPILLAR, target=STATE.BUTTERFLY)
    def cocoon(self):
        pass

    def fly(self):
        raise NotImplementedError

    def crawl(self):
        raise NotImplementedError


class Caterpillar(Insect):
    class Meta:
        proxy = True

    def crawl(self):
        """
        Do crawl
        """


class Butterfly(Insect):
    class Meta:
        proxy = True

    def fly(self):
        """
        Do fly
        """


class TestStateProxy(TestCase):
    def test_initial_proxy_resolution(self):
        insect = Insect()

        assert isinstance(insect, Caterpillar)

    def test_proxy_updates_after_state_change(self):
        insect = Insect()
        insect.cocoon()

        assert isinstance(insect, Butterfly)

    def test_proxy_resolution_after_load(self):
        Insect.objects.bulk_create(
            [
                Insect(state=Insect.STATE.CATERPILLAR),
                Insect(state=Insect.STATE.BUTTERFLY),
            ]
        )

        assert {insect.__class__ for insect in Insect.objects.all()} == {Caterpillar, Butterfly}
