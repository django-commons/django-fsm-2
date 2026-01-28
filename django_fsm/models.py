from __future__ import annotations

import typing
from warnings import warn

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils.timezone import now


class TransitionLogBase(models.Model):
    timestamp = models.DateTimeField(default=now)
    by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
    )
    state_field = models.CharField(max_length=255)
    source_state = models.CharField(max_length=255, null=True, blank=True, default=None)  # noqa: DJ001
    state = models.CharField("Target state", max_length=255)
    transition = models.CharField(max_length=255)

    description = models.TextField(null=True, blank=True)  # noqa: DJ001

    class Meta:
        abstract = True
        get_latest_by = "timestamp"


class StateLogQuerySet(models.QuerySet["StateLog"]):
    def _get_content_type(self, obj: models.Model) -> ContentType:
        return ContentType.objects.get_for_model(obj)

    def for_(self, obj: models.Model) -> typing.Self:
        return self.filter(content_type=self._get_content_type(obj), object_id=obj.pk)


class StateLog(TransitionLogBase):  # noqa: DJ008
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE)
    object_id = models.TextField()
    content_object = GenericForeignKey("content_type", "object_id")

    objects = StateLogQuerySet.as_manager()

    class Meta:
        indexes = [
            models.Index(fields=["source_state", "state"]),
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        warn(
            "StateLog model has been deprecated, you should now bring your own model."
            "\nPlease check the documentation to know how to.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(*args, **kwargs)
