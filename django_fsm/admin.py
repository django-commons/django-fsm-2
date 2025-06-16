from __future__ import annotations

from dataclasses import dataclass
from functools import partial
from typing import Any

from django.conf import settings
from django.contrib import messages
from django.contrib.admin.options import BaseModelAdmin
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.core.exceptions import FieldDoesNotExist
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseRedirect
from django.utils.translation import gettext_lazy as _

import django_fsm as fsm

try:
    import django_fsm_log  # noqa: F401
except ModuleNotFoundError:
    FSM_LOG_ENABLED = False
else:
    FSM_LOG_ENABLED = True


@dataclass
class FSMObjectTransition:
    fsm_field: str
    block_label: str
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

    def get_fsm_field_instance(self, fsm_field_name: str) -> fsm.FSMField | None:
        try:
            return self.model._meta.get_field(fsm_field_name)
        except FieldDoesNotExist:
            return None

    def get_readonly_fields(self, request: HttpRequest, obj: Any = None) -> tuple[str]:
        read_only_fields = super().get_readonly_fields(request, obj)

        for fsm_field_name in self.fsm_fields:
            if fsm_field_name in read_only_fields:
                continue
            field = self.get_fsm_field_instance(fsm_field_name=fsm_field_name)
            if field and getattr(field, "protected", False):
                read_only_fields += (fsm_field_name,)

        return read_only_fields

    @staticmethod
    def get_fsm_block_label(fsm_field_name: str) -> str:
        return f"Transition ({fsm_field_name})"

    def get_fsm_object_transitions(self, request: HttpRequest, obj: Any) -> list[FSMObjectTransition]:
        fsm_object_transitions = []

        for field_name in sorted(self.fsm_fields):
            if func := getattr(obj, f"get_available_user_{field_name}_transitions"):
                fsm_object_transitions.append(  # noqa: PERF401
                    FSMObjectTransition(
                        fsm_field=field_name,
                        block_label=self.get_fsm_block_label(fsm_field_name=field_name),
                        available_transitions=[
                            t for t in func(user=request.user) if t.custom.get("admin", self.default_disallow_transition)
                        ],
                    )
                )

        return fsm_object_transitions

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        _context = extra_context or {}
        _context[self.fsm_context_key] = self.get_fsm_object_transitions(
            request=request,
            obj=self.get_object(request=request, object_id=object_id),
        )

        return super().change_view(
            request=request,
            object_id=object_id,
            form_url=form_url,
            extra_context=_context,
        )

    def get_fsm_redirect_url(self, request: HttpRequest, obj: Any) -> str:
        return request.path

    def get_fsm_response(self, request: HttpRequest, obj: Any) -> HttpResponse:
        redirect_url = self.get_fsm_redirect_url(request=request, obj=obj)
        redirect_url = add_preserved_filters(
            context={
                "preserved_filters": self.get_preserved_filters(request),
                "opts": self.model._meta,
            },
            url=redirect_url,
        )
        return HttpResponseRedirect(redirect_to=redirect_url)

    def response_change(self, request: HttpRequest, obj: Any) -> HttpResponse:
        if self.fsm_post_param in request.POST:
            try:
                transition_name = request.POST[self.fsm_post_param]
                transition_func = getattr(obj, transition_name)
            except AttributeError:
                self.message_user(
                    request=request,
                    message=self.fsm_transition_not_valid_msg.format(
                        transition_name=transition_name,
                    ),
                    level=messages.ERROR,
                )
                return self.get_fsm_response(
                    request=request,
                    obj=obj,
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

            return self.get_fsm_response(
                request=request,
                obj=obj,
            )

        return super().response_change(request=request, obj=obj)
