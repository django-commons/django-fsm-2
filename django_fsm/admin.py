from __future__ import annotations

import logging
import typing
from dataclasses import dataclass

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.core.exceptions import AppRegistryNotReady
from django.core.exceptions import ImproperlyConfigured
from django.forms import Form
from django.forms import ModelForm
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseRedirect
from django.shortcuts import redirect
from django.shortcuts import render
from django.urls import URLPattern
from django.urls import path
from django.urls import reverse
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _

import django_fsm as fsm

logger = logging.getLogger(__name__)

try:
    from typing import override
except ImportError:  # pragma: no cover
    # Py<3.12
    from typing_extensions import override

if typing.TYPE_CHECKING:  # pragma: no cover
    _ModelAdmin = admin.ModelAdmin[fsm._FSMModel]
else:
    _ModelAdmin = admin.ModelAdmin


@dataclass
class FSMTransitionContext:
    transition: fsm.Transition
    label: str
    help_text: str | None = None


@dataclass
class FSMObjectTransition:
    fsm_field: str
    block_label: str
    available_transitions: list[FSMTransitionContext]


class FSMAdminMixin(_ModelAdmin):
    change_form_template = "django_fsm/fsm_admin_change_form.html"

    fsm_fields: list[str] = []
    fsm_transition_success_msg = _("FSM transition '{transition_name}' succeeded.")
    fsm_transition_error_msg = _("FSM transition '{transition_name}' failed: {error}.")
    fsm_transition_not_allowed_msg = _("FSM transition '{transition_name}' is not allowed.")
    fsm_context_key = "fsm_object_transitions"
    fsm_post_param = "_fsm_transition_to"
    fsm_default_disallow_transition = not getattr(settings, "FSM_ADMIN_FORCE_PERMIT", False)
    fsm_transition_form_template = "django_fsm/fsm_admin_transition_form.html"
    fsm_forms: dict[str, str | type[Form | ModelForm[typing.Any]] | None] = {}

    @override
    def __init__(self, model: type[fsm._FSMModel], admin_site: admin.AdminSite) -> None:
        if not self.fsm_fields:  # pragma: no cover
            # django-fsm-admin retro compatibility
            if hasattr(self, "fsm_field"):
                logger.warning(
                    "'fsm_field' declaration is deprecated, please update to 'fsm_fields'"
                )
                self.fsm_fields = self.fsm_field
            else:
                raise ImproperlyConfigured("'fsm_fields' is not declared")

        super().__init__(model, admin_site)

    @override
    def get_readonly_fields(self, request: HttpRequest, obj: typing.Any = None) -> tuple[str, ...]:
        """Ensures 'protected' fields are 'readonly'"""

        read_only_fields = list(super().get_readonly_fields(request, obj))

        for fsm_field_name in self.fsm_fields:
            if fsm_field_name in read_only_fields:  # pragma: no cover
                continue

            field = self.model._meta.get_field(fsm_field_name)

            if not isinstance(field, fsm.FSMField):  # pragma: no cover
                raise ImproperlyConfigured(f"'{fsm_field_name}' is not an FSMField")

            if getattr(field, "protected", False):
                read_only_fields.append(fsm_field_name)

        return tuple(read_only_fields)

    @override
    def get_urls(self) -> list[URLPattern]:
        meta = self.model._meta
        return [
            path(
                "<path:object_id>/transition/<str:transition_name>/",
                self.admin_site.admin_view(self.fsm_transition_view),
                name=f"{meta.app_label}_{meta.model_name}_transition",
            ),
            *super().get_urls(),
        ]

    @override
    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, typing.Any] | None = None,
    ) -> HttpResponse:
        """Override the change view to add FSM transitions to the context."""

        _context = extra_context or {}
        _context[self.fsm_context_key] = self._get_fsm_extra_context(
            request=request,
            obj=self.get_object(request=request, object_id=object_id),
        )

        return super().change_view(
            request=request,
            object_id=object_id,
            form_url=form_url,
            extra_context=_context,
        )

    def _get_fsm_extra_context(
        self, *, request: HttpRequest, obj: typing.Any
    ) -> typing.Generator[FSMObjectTransition]:
        for field_name in sorted(self.fsm_fields):
            transition_func = getattr(obj, f"get_available_user_{field_name}_transitions", None)
            if callable(transition_func):
                available_transitions = transition_func(user=request.user)
                if admin_allowed_transitions := [
                    FSMTransitionContext(
                        transition=t,
                        label=self.get_fsm_label(t),
                        help_text=self.get_help_text(t),
                    )
                    for t in available_transitions
                    if self.is_fsm_transition_visible(t)
                ]:
                    yield FSMObjectTransition(
                        fsm_field=field_name,
                        block_label=self.get_fsm_block_label(fsm_field_name=field_name),
                        available_transitions=admin_allowed_transitions,
                    )

    @staticmethod
    def get_fsm_block_label(fsm_field_name: str) -> str:
        return f"Transition ({fsm_field_name})"

    def is_fsm_transition_visible(self, transition: fsm.Transition) -> bool:
        return bool(transition.custom.get("admin", self.fsm_default_disallow_transition))

    def get_fsm_label(self, transition: fsm.Transition) -> str:
        return transition.custom.get("label") or transition.name

    def get_help_text(self, transition: fsm.Transition) -> str | None:
        return transition.custom.get("help_text")

    def _get_fsm_transition_func(
        self, *, obj: typing.Any, transition_name: str
    ) -> typing.Callable[..., typing.Any]:
        try:
            transition_func: typing.Callable[..., typing.Any] = getattr(obj, transition_name)
        except AttributeError:
            raise AttributeError(
                f"{obj.__class__.__name__} has no transition method '{transition_name}'."
            )

        if not callable(transition_func):  # pragma: no cover
            raise TypeError(f"Attribute '{transition_name}' is not callable.")

        # Security: Only allow FSM transition methods
        if not hasattr(transition_func, "_django_fsm"):  # pragma: no cover
            raise ValueError(f"Method '{transition_name}' is not an FSM transition.")

        return transition_func

    def _get_fsm_transition_by_name(
        self, *, obj: typing.Any, transition_name: str
    ) -> fsm.Transition:
        transition_func = self._get_fsm_transition_func(obj=obj, transition_name=transition_name)
        transitions = transition_func._django_fsm.transitions  # type: ignore[attr-defined]
        if isinstance(transitions, dict):
            transitions = list(transitions.values())

        return transitions[0]  # type: ignore[no-any-return]

    @override
    def response_change(self, request: HttpRequest, obj: typing.Any) -> HttpResponse:
        transition_name = request.POST.get(self.fsm_post_param)
        if not transition_name:
            return super().response_change(request=request, obj=obj)

        transition = self._get_fsm_transition_by_name(obj=obj, transition_name=transition_name)

        if self.get_fsm_transition_form(transition):
            return redirect(
                reverse(
                    f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_transition",
                    kwargs={
                        "object_id": obj.pk,
                        "transition_name": transition_name,
                    },
                )
            )

        if self._apply_fsm_transition(
            obj=obj,
            transition_name=transition_name,
            request=request,
        ):
            logger.info("FSM transition %s completed successfully", transition_name)

        return HttpResponseRedirect(
            redirect_to=add_preserved_filters(
                context={
                    "preserved_filters": self.get_preserved_filters(request),
                    "opts": self.model._meta,
                },
                url=self.get_fsm_redirect_url(request=request, obj=obj),
            )
        )

    @staticmethod
    def _is_fsm_log_enabled() -> bool:
        try:
            return apps.is_installed("django_fsm_log")
        except AppRegistryNotReady:  # pragma: no cover
            return "django_fsm_log" in settings.INSTALLED_APPS

    def _execute_fsm_transition(
        self,
        *,
        transition_func: typing.Callable[..., typing.Any],
        request: HttpRequest,
        kwargs: typing.Mapping[str, typing.Any] | None = None,
    ) -> None:
        kwargs = kwargs or {}
        if self._is_fsm_log_enabled():
            try:
                transition_func(by=request.user, **kwargs)
            except TypeError:
                transition_func(**kwargs)
        else:
            transition_func(**kwargs)

    def _apply_fsm_transition(
        self,
        *,
        obj: typing.Any,
        transition_name: str,
        request: HttpRequest,
        kwargs: typing.Mapping[str, typing.Any] | None = None,
    ) -> bool:
        try:
            self._execute_fsm_transition(
                transition_func=self._get_fsm_transition_func(
                    obj=obj, transition_name=transition_name
                ),
                request=request,
                kwargs=kwargs,
            )
            obj.save()
        except fsm.TransitionNotAllowed:
            self.message_user(
                request=request,
                message=self.fsm_transition_not_allowed_msg.format(transition_name=transition_name),
                level=messages.ERROR,
            )
            return False
        except fsm.ConcurrentTransition as err:
            self.message_user(
                request=request,
                message=self.fsm_transition_error_msg.format(
                    transition_name=transition_name, error=str(err)
                ),
                level=messages.ERROR,
            )
            return False
        except Exception as err:
            logger.exception("Unexpected error during FSM transition %s", transition_name)
            self.message_user(
                request=request,
                message=self.fsm_transition_error_msg.format(
                    transition_name=transition_name, error=str(err)
                ),
                level=messages.ERROR,
            )
            return False
        else:
            self.message_user(
                request=request,
                message=self.fsm_transition_success_msg.format(transition_name=transition_name),
                level=messages.SUCCESS,
            )
            return True

    def get_fsm_redirect_url(self, request: HttpRequest, obj: typing.Any) -> str:
        return request.path

    def get_fsm_transition_form(
        self, transition: fsm.Transition
    ) -> type[Form | ModelForm[typing.Any]] | None:
        """Get transition form class with error handling."""
        form = self.fsm_forms.get(transition.name, transition.custom.get("form"))

        if isinstance(form, str):
            try:
                form = import_string(form)
            except (ImportError, AttributeError):
                raise ImproperlyConfigured(f"Failed to import form {form}")
        if isinstance(form, type) and issubclass(form, (ModelForm, Form)):
            return form
        return None

    def fsm_transition_view(
        self, request: HttpRequest, *args: typing.Any, **kwargs: typing.Any
    ) -> HttpResponse:
        """Handle FSM transition form view with enhanced validation."""
        object_id = kwargs["object_id"]
        obj = self.get_object(request, object_id)
        if obj is None:
            return self._get_obj_does_not_exist_redirect(request, self.opts, object_id)  # type: ignore[no-any-return, attr-defined]

        transition_name = kwargs["transition_name"]

        transition = self._get_fsm_transition_by_name(obj=obj, transition_name=transition_name)

        form_class = self.get_fsm_transition_form(transition)
        if not form_class:
            logger.warning("No form configured for transition %s", transition_name)
            return HttpResponseBadRequest(f"No form configuration found for {transition_name}")

        data = request.POST if request.method == "POST" else None
        transition_form: Form | ModelForm[fsm._FSMModel]
        if issubclass(form_class, ModelForm):
            transition_form = form_class(data=data, instance=obj)
        else:
            transition_form = form_class(data=data)

        if request.method == "POST" and transition_form.is_valid():  # noqa: SIM102
            if self._apply_fsm_transition(
                obj=obj,
                transition_name=transition_name,
                request=request,
                kwargs=transition_form.cleaned_data,
            ):
                return redirect(
                    f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change",
                    object_id=obj.pk,
                )

        return render(
            request,
            template_name=self.fsm_transition_form_template,
            context=(
                admin.site.each_context(request)
                | {
                    "opts": self.model._meta,
                    "original": obj,
                    "transition": transition,
                    "transition_form": transition_form,
                }
            ),
        )
