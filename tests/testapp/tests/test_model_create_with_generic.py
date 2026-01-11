from __future__ import annotations

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.test import TestCase

from django_fsm_2 import FSMField
from django_fsm_2 import transition


class Ticket(models.Model): ...


class TaskState(models.TextChoices):
    NEW = "new", "New"
    DONE = "done", "Done"


class Task(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    causality = GenericForeignKey("content_type", "object_id")
    state = FSMField(default=TaskState.NEW)

    @transition(field=state, source=TaskState.NEW, target=TaskState.DONE)
    def do(self):
        pass


class Test(TestCase):
    def setUp(self):
        self.ticket = Ticket.objects.create()

    def test_model_objects_create(self):
        """Check a model with state field can be created
        if one of the other fields is a property or a virtual field.
        """
        Task.objects.create(causality=self.ticket)
