from __future__ import annotations

from django.conf import settings
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
    state = models.CharField(verbose_name="Target state", max_length=255)
    transition = models.CharField(max_length=255)

    description = models.TextField(null=True, blank=True)  # noqa: DJ001

    class Meta:
        abstract = True
        get_latest_by = "timestamp"
