from __future__ import annotations

from django.contrib import admin
from django_fsm_log.admin import StateLogInline

from fsm_admin.mixins import FSMTransitionMixin

from .admin_forms import AdminBlogPostRenameForm
from .admin_forms import AdminBlogPostRenameModelForm
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
        "complex_transition_model_form": "tests.testapp.admin_forms.AdminBlogPostRenameModelForm",
        "invalid": "tests.testapp.admin_forms.FSMLogDescription",
        "force_state": "tests.testapp.admin_forms.ForceStateForm",
    }

    inlines = [StateLogInline]


class ProxyAdminBlogPost(AdminBlogPost):
    class Meta:
        proxy = True


@admin.register(ProxyAdminBlogPost)
class ProxyAdminBlogPostAdmin(AdminBlogPostAdmin):
    fsm_forms = {
        "complex_transition": AdminBlogPostRenameForm,
        "complex_transition_model_form": AdminBlogPostRenameModelForm,
        "invalid": "tests.testapp.admin_forms.FSMLogDescription",
    }
