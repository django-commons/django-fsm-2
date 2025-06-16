from __future__ import annotations

from django.contrib import admin
from django_fsm_log.admin import StateLogInline

from django_fsm.admin import FSMAdminMixin

from .models import AdminBlogPost


@admin.register(AdminBlogPost)
class AdminBlogPostAdmin(FSMAdminMixin, admin.ModelAdmin):
    list_display = (
        "id",
        "title",
        "state",
        "step",
    )

    fsm_fields = [
        "state",
        "step",
    ]

    inlines = [StateLogInline]
