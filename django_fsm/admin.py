from __future__ import annotations

import logging
import typing
from dataclasses import dataclass
from functools import partial

from django.conf import settings
from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
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
    import django_fsm_log  # noqa: F401
except ModuleNotFoundError:  # pragma: no cover
    FSM_LOG_ENABLED = False
else:
    FSM_LOG_ENABLED = True


@dataclass
class FSMObjectTransition:
    fsm_field: str
    block_label: str
    available_transitions: list[fsm.Transition]


@dataclass
class TransitionContext:
    obj: typing.Any
    transition_name: str
    transition_method: typing.Callable[..., typing.Any]
    transition: fsm.Transition
    form_class: type[Form | ModelForm[typing.Any]] | None


class FSMTransitionMixin(admin.ModelAdmin[fsm._FSMModel]):
    change_form_template = "django_fsm/fsm_admin_change_form.html"

    fsm_fields: list[str] = []
    fsm_transition_success_msg = _("FSM transition '{transition_name}' succeeded.")
    fsm_transition_error_msg = _("FSM transition '{transition_name}' failed: {error}.")
    fsm_transition_not_allowed_msg = _("FSM transition '{transition_name}' is not allowed.")
    fsm_transition_not_valid_msg = _("FSM transition '{transition_name}' is not a valid.")
    fsm_context_key = "fsm_object_transitions"
    fsm_post_param = "_fsm_transition_to"
    fsm_default_disallow_transition = not getattr(settings, "FSM_ADMIN_FORCE_PERMIT", False)
    fsm_transition_form_template = "django_fsm/fsm_admin_transition_form.html"
    fsm_forms: dict[str, str | type[Form | ModelForm[typing.Any]] | None] = {}

    def get_readonly_fields(self, request: HttpRequest, obj: typing.Any = None) -> tuple[str, ...]:
        """Ensures 'protected' fields are 'readonly'"""

        if not self.fsm_fields:  # pragma: no cover
            raise ImproperlyConfigured("'fsm_fields' is not declared")

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
        self, request: HttpRequest, obj: typing.Any
    ) -> typing.Generator[FSMObjectTransition]:
        for field_name in sorted(self.fsm_fields):
            transition_func = getattr(obj, f"get_available_user_{field_name}_transitions", None)
            if transition_func and callable(transition_func):
                available_transitions = transition_func(user=request.user)
                if admin_allowed_transitions := [
                    t
                    for t in available_transitions
                    if t.custom.get("admin", self.fsm_default_disallow_transition)
                ]:
                    yield FSMObjectTransition(
                        fsm_field=field_name,
                        block_label=self.get_fsm_block_label(fsm_field_name=field_name),
                        available_transitions=admin_allowed_transitions,
                    )

    @staticmethod
    def get_fsm_block_label(fsm_field_name: str) -> str:
        return f"Transition ({fsm_field_name})"

    def response_change(self, request: HttpRequest, obj: typing.Any) -> HttpResponse:
        if transition_name := request.POST.get(self.fsm_post_param):
            return self._handle_fsm_transition(request, obj, transition_name)
        return super().response_change(request=request, obj=obj)

    def _handle_fsm_transition(
        self, request: HttpRequest, obj: typing.Any, transition_name: str
    ) -> HttpResponse:
        context = self._get_transition_context(obj, transition_name)

        if context.form_class:
            return redirect(
                reverse(
                    f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_transition",
                    kwargs={
                        "object_id": obj.pk,
                        "transition_name": transition_name,
                    },
                )
            )

        return self._execute_fsm_transition(
            request, obj, context.transition_method, transition_name
        )

    def _get_transition_method(
        self, obj: typing.Any, transition_name: str
    ) -> typing.Callable[..., typing.Any]:
        """Validate that transition method exists, is callable, and is an FSM transition."""
        if not hasattr(obj, transition_name):
            raise AttributeError(
                f"{obj.__class__.__name__} has no transition method '{transition_name}'."
            )

        transition_func: typing.Callable[..., typing.Any] = getattr(obj, transition_name)
        if not callable(transition_func):
            raise TypeError(f"Attribute '{transition_name}' is not callable.")

        # Security: Only allow FSM transition methods
        if not hasattr(transition_func, "_django_fsm"):
            raise ValueError(f"Method '{transition_name}' is not an FSM transition.")

        return transition_func

    def _execute_fsm_transition(
        self,
        request: HttpRequest,
        obj: typing.Any,
        transition_func: typing.Callable[..., typing.Any],
        transition_name: str,
    ) -> HttpResponse:
        """Execute FSM transition with proper error handling and logging."""
        try:
            if FSM_LOG_ENABLED:
                self._execute_transition_with_logging(transition_func, request)
            else:  # pragma: no cover
                transition_func()
        except fsm.TransitionNotAllowed:
            self.message_user(
                request=request,
                message=self.fsm_transition_not_allowed_msg.format(transition_name=transition_name),
                level=messages.ERROR,
            )
        except fsm.ConcurrentTransition as err:
            self.message_user(
                request=request,
                message=self.fsm_transition_error_msg.format(
                    transition_name=transition_name, error=str(err)
                ),
                level=messages.ERROR,
            )
        except Exception as e:
            logger.exception("Unexpected error during FSM transition %s", transition_name)
            self.message_user(
                request=request,
                message=self.fsm_transition_error_msg.format(
                    transition_name=transition_name, error=str(e)
                ),
                level=messages.ERROR,
            )
        else:
            obj.save()
            self.message_user(
                request=request,
                message=self.fsm_transition_success_msg.format(transition_name=transition_name),
                level=messages.SUCCESS,
            )
            logger.info("FSM transition %s completed successfully", transition_name)

        return self.get_fsm_response(request=request, obj=obj)

    def _execute_transition_with_logging(
        self, transition_func: typing.Callable[..., typing.Any], request: HttpRequest
    ) -> None:
        """Execute transition with FSM logging, trying different parameter combinations."""
        transition_attempts: list[typing.Callable[..., typing.Any]] = [
            partial(transition_func, request=request, by=request.user),
            partial(transition_func, by=request.user),
            transition_func,
        ]

        for attempt in transition_attempts:
            try:
                attempt()
                break
            except TypeError:
                continue
        else:
            # If all attempts failed, try the base transition one more time to get the real error
            transition_func()

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

    def get_fsm_transition_form(
        self, transition: fsm.Transition
    ) -> type[Form | ModelForm[typing.Any]] | None:
        """Get transition form class with error handling."""
        form = self.fsm_forms.get(transition.name, transition.custom.get("form"))
        if isinstance(form, str):
            try:
                form = import_string(form)
            except (ImportError, AttributeError) as e:
                logger.warning("Failed to import form %s: %s", form, str(e))
                return None
        if isinstance(form, type) and issubclass(form, (ModelForm, Form)):
            return form
        return None

    def _get_transition_from_method(
        self, transition_method: typing.Callable[..., typing.Any]
    ) -> fsm.Transition | None:
        """Extract transition object from FSM method with standardized handling."""
        if not hasattr(transition_method, "_django_fsm"):
            return None

        transitions = transition_method._django_fsm.transitions
        if isinstance(transitions, dict):
            transitions = list(transitions.values())

        return transitions[0] if transitions else None

    def _get_transition_context(self, obj: typing.Any, transition_name: str) -> TransitionContext:
        transition_method = self._get_transition_method(obj, transition_name)
        transition = self._get_transition_from_method(transition_method)
        if not transition:
            raise ValueError(f"No transitions defined for method '{transition_name}'.")

        return TransitionContext(
            obj=obj,
            transition_name=transition_name,
            transition_method=transition_method,
            transition=transition,
            form_class=self.get_fsm_transition_form(transition),
        )

    def fsm_transition_view(
        self, request: HttpRequest, *args: typing.Any, **kwargs: typing.Any
    ) -> HttpResponse:
        """Handle FSM transition form view with enhanced validation."""
        transition_name = kwargs["transition_name"]
        obj = self.get_object(request, kwargs["object_id"])

        context = self._get_transition_context(obj, transition_name)

        if not context.form_class:
            logger.warning("No form configured for transition %s", transition_name)
            return HttpResponseBadRequest(f"No form configuration found for {transition_name}")

        return self._handle_form_transition(request, context)

    def _create_transition_form(
        self,
        form_class: type[Form | ModelForm[typing.Any]],
        obj: typing.Any,
        data: typing.Mapping[str, typing.Any] | None,
    ) -> Form | ModelForm[typing.Any]:
        if issubclass(form_class, ModelForm):
            return form_class(data=data, instance=obj)
        return form_class(data=data)

    def _handle_form_transition(
        self, request: HttpRequest, context: TransitionContext
    ) -> HttpResponse:
        """Handle FSM transition that requires form input."""
        if context.form_class is None:
            return HttpResponseBadRequest(
                f"No form configuration found for {context.transition_name}"
            )

        transition_form = self._create_transition_form(
            context.form_class,
            context.obj,
            request.POST if request.method == "POST" else None,
        )

        if request.method == "POST" and transition_form.is_valid():
            try:
                context.transition_method(**transition_form.cleaned_data)
                context.obj.save()
                self.message_user(
                    request=request,
                    message=self.fsm_transition_success_msg.format(
                        transition_name=context.transition_name
                    ),
                    level=messages.SUCCESS,
                )
                return redirect(
                    f"admin:{self.model._meta.app_label}_{self.model._meta.model_name}_change",
                    object_id=context.obj.id,
                )
            except Exception as e:
                logger.exception("Form transition %s failed", context.transition_name)
                self.message_user(
                    request=request,
                    message=self.fsm_transition_error_msg.format(
                        transition_name=context.transition_name, error=str(e)
                    ),
                    level=messages.ERROR,
                )

        return render(
            request,
            self.fsm_transition_form_template,
            context=(
                admin.site.each_context(request)
                | {
                    "opts": self.model._meta,
                    "original": context.obj,
                    "transition": context.transition,
                    "transition_form": transition_form,
                }
            ),
        )
