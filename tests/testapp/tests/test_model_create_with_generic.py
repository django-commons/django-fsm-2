from __future__ import annotations

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.test import TestCase

import django_fsm as fsm


class Ticket(models.Model):
    objects: models.Manager[Ticket] = models.Manager()


class TaskState(models.TextChoices):
    NEW = "NEW", "New"
    DONE = "DONE", "Done"


class Task(models.Model):
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.PositiveIntegerField()
    causality = GenericForeignKey("content_type", "object_id")
    state = fsm.FSMField(choices=TaskState.choices, default=TaskState.NEW)

    objects: models.Manager[Task] = models.Manager()

    @fsm.transition(field=state, source=TaskState.NEW, target=TaskState.DONE)
    def do(self):
        pass


class GenericRelationModelCreateTests(TestCase):
    def setUp(self):
        self.ticket = Ticket.objects.create()

    def test_model_create_with_generic_relation(self):
        """Check a model with state field can be created
        if one of the other fields is a property or a virtual field.
        """
        created_task = Task.objects.create(causality=self.ticket)

        assert created_task.pk is not None
