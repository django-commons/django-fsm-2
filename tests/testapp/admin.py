from __future__ import annotations

import typing

from django.contrib import admin
from django_fsm_log.admin import StateLogInline

import django_fsm as fsm
from django_fsm.admin import FSMAdminMixin

from .admin_forms import ForceStateForm
from .admin_forms import FSMLogDescriptionForm
from .models import AdminBlogPost

if typing.TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest


@admin.register(AdminBlogPost)
class AdminBlogPostAdmin(FSMAdminMixin, admin.ModelAdmin[AdminBlogPost]):
    list_display = (
        "id",
        "title",
        "state",
        "step",
    )

    actions = ["step_reset_action"]

    fsm_fields = [
        "state",
        "step",
        "key_state",
    ]

    fsm_forms = {
        "complex_transition": "tests.testapp.admin_forms.AdminBlogPostRenameModelForm",
        "invalid": FSMLogDescriptionForm,
        "force_state": ForceStateForm,
    }

    inlines = [StateLogInline]

    # Override label
    def get_fsm_label(self, transition):
        if transition.name == "do_something":
            return "My awesome transition"
        return super().get_fsm_label(transition)

    # Override help_text
    def get_help_text(self, transition):
        if transition.name == "do_something":
            return "Rename blog post"
        return super().get_help_text(transition)

    # Use a Transition as a Django admin action
    @admin.action(description="Reset step")
    def step_reset_action(self, request: HttpRequest, queryset: QuerySet[AdminBlogPost]) -> None:
        for obj in queryset:
            if fsm.can_proceed(obj.step_reset):
                self._apply_fsm_transition(
                    obj=obj,
                    transition_name="step_reset",
                    request=request,
                    kwargs={
                        "description": "Reset from admin",
                    },
                )
