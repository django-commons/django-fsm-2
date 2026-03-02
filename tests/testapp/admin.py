from __future__ import annotations

from django.contrib import admin
from django_fsm_log.admin import StateLogInline

from fsm_admin.mixins import FSMTransitionMixin

from .admin_forms import ForceStateForm
from .admin_forms import FSMLogDescription
from .models import AdminBlogPost


@admin.register(AdminBlogPost)
class AdminBlogPostAdmin(FSMTransitionMixin, admin.ModelAdmin[AdminBlogPost]):
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

    fsm_forms = {
        "complex_transition": "tests.testapp.admin_forms.AdminBlogPostRenameModelForm",
        "invalid": FSMLogDescription,
        "force_state": ForceStateForm,
    }

    inlines = [StateLogInline]
