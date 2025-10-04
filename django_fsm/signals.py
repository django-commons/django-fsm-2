from __future__ import annotations

from django.db.models.signals import ModelSignal

pre_transition = ModelSignal()
post_transition = ModelSignal()
