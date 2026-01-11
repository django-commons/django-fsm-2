from __future__ import annotations

from django.contrib import admin

from django_fsm_2.admin import FSMAdminMixin

from .models import AdminBlogPost


@admin.register(AdminBlogPost)
class AdminBlogPostAdmin(FSMAdminMixin, admin.ModelAdmin):
    """Admin for AdminBlogPost with FSM integration."""

    list_display = ["title", "state", "review_state"]
    fsm_fields = ["state", "review_state"]
    readonly_fields = ["state"]  # state is already protected, but explicit
