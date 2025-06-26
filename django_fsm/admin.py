from __future__ import annotations

import typing
from dataclasses import dataclass
from functools import partial

from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.options import BaseModelAdmin
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.core.exceptions import FieldDoesNotExist
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import path
from django.urls import reverse
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _

import django_fsm as fsm

if typing.TYPE_CHECKING:
    from django.forms import Form

try:
    import django_fsm_log  # noqa: F401
except ModuleNotFoundError:
    FSM_LOG_ENABLED = False
else:
    FSM_LOG_ENABLED = True


@dataclass
class FSMObjectTransition:
    fsm_field: str
    available_transitions: list[fsm.Transition]


class FSMAdminMixin(BaseModelAdmin):
    change_form_template: str = "django_fsm/fsm_admin_change_form.html"

    fsm_fields: list[str] = []
    fsm_transition_success_msg = _("FSM transition '{transition_name}' succeeded.")
    fsm_transition_error_msg = _("FSM transition '{transition_name}' failed: {error}.")
    fsm_transition_not_allowed_msg = _("FSM transition '{transition_name}' is not allowed.")
    fsm_transition_not_valid_msg = _("FSM transition '{transition_name}' is not a valid.")
    fsm_context_key = "fsm_object_transitions"
    fsm_post_param = "_fsm_transition_to"
    default_disallow_transition = not getattr(settings, "FSM_ADMIN_FORCE_PERMIT", False)
    fsm_transition_form_template = "django_fsm/fsm_admin_transition_form.html"

    def get_urls(self):
        meta = self.model._meta
        return [
            path(
                "<path:object_id>/transition/<str:transition_name>/",
                self.admin_site.admin_view(self.fsm_transition_view),
                name=f"{meta.app_label}_{meta.model_name}_transition",
            ),
            *super().get_urls(),
        ]

    def get_readonly_fields(self, request: HttpRequest, obj: typing.Any = None) -> tuple[str]:
        """Add FSM fields to readonly fields if they are protected."""

        read_only_fields = super().get_readonly_fields(request, obj)

        for fsm_field_name in self.fsm_fields:
            if fsm_field_name in read_only_fields:
                continue
            try:
                field = self.model._meta.get_field(fsm_field_name)
            except FieldDoesNotExist:
                pass
            else:
                if getattr(field, "protected", False):
                    read_only_fields += (fsm_field_name,)

        return read_only_fields

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, typing.Any] | None = None,
    ) -> HttpResponse:
        """Override the change view to add FSM transitions to the context."""

        _context = extra_context or {}
        _context[self.fsm_context_key] = self._get_fsm_object_transitions(
            request=request,
            obj=self.get_object(request=request, object_id=object_id),
        )

        return super().change_view(
            request=request,
            object_id=object_id,
            form_url=form_url,
            extra_context=_context,
        )

    def _get_fsm_object_transitions(self, request: HttpRequest, obj: typing.Any) -> list[FSMObjectTransition]:
        for field_name in sorted(self.fsm_fields):
            if func := getattr(obj, f"get_available_user_{field_name}_transitions"):
                yield FSMObjectTransition(
                    fsm_field=field_name,
                    available_transitions=[
                        t for t in func(user=request.user) if t.custom.get("admin", self.default_disallow_transition)
                    ],
                )

    def response_change(self, request: HttpRequest, obj: typing.Any) -> HttpResponse:  # noqa: C901
        if transition_name := request.POST.get(self.fsm_post_param):
            try:
                transition_func = getattr(obj, transition_name)
            except AttributeError:
                self.message_user(
                    request=request,
                    message=self.fsm_transition_not_valid_msg.format(
                        transition_name=transition_name,
                    ),
                    level=messages.ERROR,
                )
                return self.get_fsm_response(request=request, obj=obj)

            # NOTE: if a form is defined in the transition.custom, we redirect to the form view
            if self.get_fsm_transition_custom(instance=obj, transition_func=transition_func).get("form"):
                return redirect(
                    reverse(
                        f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_transition",
                        kwargs={
                            "object_id": obj.pk,
                            "transition_name": transition_name,
                        },
                    )
                )

            try:
                if FSM_LOG_ENABLED:
                    for fn in [
                        partial(transition_func, request=request, by=request.user),
                        partial(transition_func, by=request.user),
                        transition_func,
                    ]:
                        try:
                            fn()
                        except TypeError:  # noqa: PERF203
                            pass
                        else:
                            break
                else:
                    transition_func()
            except fsm.TransitionNotAllowed:
                self.message_user(
                    request=request,
                    message=self.fsm_transition_not_allowed_msg.format(
                        transition_name=transition_name,
                    ),
                    level=messages.ERROR,
                )
            except fsm.ConcurrentTransition as err:
                self.message_user(
                    request=request,
                    message=self.fsm_transition_error_msg.format(transition_name=transition_name, error=str(err)),
                    level=messages.ERROR,
                )
            else:
                obj.save()
                self.message_user(
                    request=request,
                    message=self.fsm_transition_success_msg.format(
                        transition_name=transition_name,
                    ),
                    level=messages.INFO,
                )

            return self.get_fsm_response(request=request, obj=obj)

        return super().response_change(request=request, obj=obj)

    def get_fsm_response(self, request: HttpRequest, obj: typing.Any) -> HttpResponse:
        redirect_url = add_preserved_filters(
            context={
                "preserved_filters": self.get_preserved_filters(request),
                "opts": self.model._meta,
            },
            url=self.get_fsm_redirect_url(request=request, obj=obj),
        )
        return HttpResponseRedirect(redirect_to=redirect_url)

    def get_fsm_redirect_url(self, request: HttpRequest, obj: typing.Any) -> str:
        return request.path

    def get_fsm_transition_custom(self, instance, transition_func):
        """Helper function to get custom attributes for the current transition"""
        return getattr(self.get_fsm_transition(instance, transition_func), "custom", {})

    def get_fsm_transition(self, instance, transition_func) -> fsm.Transition | None:
        """
        Extract custom attributes from a transition function for the current state.
        """
        if not hasattr(transition_func, "_django_fsm"):
            return None

        fsm_meta = transition_func._django_fsm
        current_state = fsm_meta.field.get_state(instance)
        return fsm_meta.get_transition(current_state)

    def get_fsm_transition_form(self, transition: fsm.Transition) -> Form | None:
        form = transition.custom.get("form")
        if isinstance(form, str):
            form = import_string(form)
        return form

    def fsm_transition_view(self, request, *args, **kwargs):
        transition_name = kwargs["transition_name"]
        obj = self.get_object(request, kwargs["object_id"])

        transition_method = getattr(obj, transition_name)
        if not hasattr(transition_method, "_django_fsm"):
            return HttpResponseBadRequest(f"{transition_name} is not a transition method")

        transitions = transition_method._django_fsm.transitions
        if isinstance(transitions, dict):
            transitions = list(transitions.values())
        transition = transitions[0]

        if TransitionForm := self.get_fsm_transition_form(transition):
            if request.method == "POST":
                transition_form = TransitionForm(data=request.POST, instance=obj)
                if transition_form.is_valid():
                    transition_method(**transition_form.cleaned_data)
                    obj.save()
                else:
                    return render(
                        request,
                        self.fsm_transition_form_template,
                        context=admin.site.each_context(request)
                        | {
                            "opts": self.model._meta,
                            "original": obj,
                            "transition": transition,
                            "transition_form": transition_form,
                        },
                    )
            else:
                transition_form = TransitionForm(instance=obj)
                return render(
                    request,
                    self.fsm_transition_form_template,
                    context=admin.site.each_context(request)
                    | {
                        "opts": self.model._meta,
                        "original": obj,
                        "transition": transition,
                        "transition_form": transition_form,
                    },
                )
        else:
            try:
                transition_method()
            except fsm.TransitionNotAllowed:
                self.message_user(
                    request,
                    self.fsm_transition_not_allowed_msg.format(transition_name=transition_name),
                    messages.ERROR,
                )
            else:
                obj.save()
                self.message_user(
                    request,
                    self.fsm_transition_success_msg.format(transition_name=transition_name),
                    messages.SUCCESS,
                )
        return redirect(f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change", object_id=obj.id)
