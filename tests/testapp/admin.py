"""Admin configuration for testapp models."""

from __future__ import annotations

from django.contrib import admin

from django_fsm.admin import FSMAdminMixin

from .models import AdminArticle
from .models import LoggableArticle


@admin.register(AdminArticle)
class AdminArticleAdmin(FSMAdminMixin, admin.ModelAdmin):
    """Admin for AdminArticle with FSM transitions."""

    list_display = ("title", "state")
    list_filter = ("state",)
    search_fields = ("title",)
    readonly_fields = ("state",)


@admin.register(LoggableArticle)
class LoggableArticleAdmin(FSMAdminMixin, admin.ModelAdmin):
    """Admin for LoggableArticle with FSM transitions."""

    list_display = ("title", "state")
    list_filter = ("state",)
    search_fields = ("title",)
    readonly_fields = ("state",)
