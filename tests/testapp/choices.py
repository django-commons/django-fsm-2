from __future__ import annotations

from django.db import models


class ApplicationState(models.TextChoices):
    NEW = "new", "New"
    FAILED = "failed", "Failed"
    PUBLISHED = "published", "Published"
    BLOCKED = "blocked", "Blocked"
    HIDDEN = "hidden", "Hidden"
    REJECTED = "rejected", "Rejected"
    MODERATED = "moderated", "Moderated"

    REMOVED = "removed", "Removed"
    STOLEN = "stolen", "Stolen"
