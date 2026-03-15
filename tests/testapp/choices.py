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
    CRASHED = "crashed", "Crashed"


class BlogPostState(models.IntegerChoices):
    NEW = 0, "New"
    PUBLISHED = 1, "Published"
    HIDDEN = 2, "Hidden"
    REMOVED = 3, "Removed"
    RESTORED = 4, "Restored"
    MODERATED = 5, "Moderated"
    STOLEN = 6, "Stolen"
    FAILED = 7, "Failed"
