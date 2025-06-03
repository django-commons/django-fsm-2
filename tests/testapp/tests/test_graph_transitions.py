from __future__ import annotations

from django.core.management import call_command
from django.db import models
from django.test import TestCase

from django_fsm import FSMField
from django_fsm import transition


class VisualBlogPost(models.Model):
    state = FSMField(default="new")

    @transition(field=state, source="new", target="published")
    def publish(self):
        pass

    @transition(source="published", field=state)
    def notify_all(self):
        pass

    @transition(source="published", target="hidden", field=state)
    def hide(self):
        pass

    @transition(source="new", target="removed", field=state)
    def remove(self):
        raise Exception("Upss")

    @transition(source=["published", "hidden"], target="stolen", field=state)
    def steal(self):
        pass

    @transition(source="*", target="moderated", field=state)
    def moderate(self):
        pass

    @transition(source="+", target="blocked", field=state)
    def block(self):
        pass

    @transition(source="*", target="", field=state)
    def empty(self):
        pass


class GraphTransitionsCommandTest(TestCase):
    def test_dummy(self):
        call_command("graph_transitions", "testapp.VisualBlogPost")
