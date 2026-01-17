"""
Django Admin integration for django-fsm-2.

This module provides mixins and utilities for integrating FSM fields
with Django's admin interface, allowing administrators to execute
state transitions directly from the admin panel.

Example:
    >>> from django.contrib import admin
    >>> from django_fsm_rx.admin import FSMAdminMixin
    >>> from myapp.models import BlogPost
    >>>
    >>> @admin.register(BlogPost)
    >>> class BlogPostAdmin(FSMAdminMixin, admin.ModelAdmin):
    ...     fsm_fields = ['state']
"""

from __future__ import annotations

from dataclasses import dataclass
from dataclasses import field
from typing import TYPE_CHECKING
from typing import Any

from django.contrib import admin
from django.contrib import messages
from django.contrib.admin.options import BaseModelAdmin
from django.contrib.admin.templatetags.admin_urls import add_preserved_filters
from django.core.exceptions import FieldDoesNotExist
from django.http import HttpRequest
from django.http import HttpResponse
from django.http import HttpResponseBadRequest
from django.http import HttpResponseRedirect
from django.shortcuts import render
from django.urls import path
from django.urls import reverse
from django.utils.module_loading import import_string
from django.utils.translation import gettext_lazy as _

from django_fsm_rx import ConcurrentTransition
from django_fsm_rx import FSMFieldMixin
from django_fsm_rx import Transition
from django_fsm_rx import TransitionNotAllowed

if TYPE_CHECKING:
    from django.db.models import Model
    from django.forms import Form

from django_fsm_rx.widgets import FSMCascadeWidget

__all__ = [
    "FSMAdminMixin",
    "FSMCascadeWidget",
    "FSMObjectTransitions",
]


@dataclass
class FSMObjectTransitions:
    """
    Container for available transitions on an FSM field.

    Attributes:
        fsm_field: The name of the FSM field.
        block_label: Display label for the transition block in admin.
        available_transitions: List of transitions available to the current user.
    """

    fsm_field: str
    block_label: str
    available_transitions: list[Transition] = field(default_factory=list)


class FSMAdminMixin(BaseModelAdmin):
    """
    Admin mixin for FSM field integration.

    This mixin adds FSM transition capabilities to Django admin:
    - Displays available transitions as buttons in the change form
    - Handles transition execution via secure POST requests
    - Supports transition arguments through custom forms
    - Integrates with django-fsm-log for transition logging
    - Marks protected FSM fields as read-only

    Attributes:
        fsm_fields: List of FSM field names to manage in admin.
        fsm_transition_success_msg: Message template for successful transitions.
        fsm_transition_error_msg: Message template for transition errors.
        fsm_transition_not_allowed_msg: Message template when transition not allowed.
        fsm_transition_not_valid_msg: Message template for invalid transitions.
        fsm_context_key: Template context key for transition data.
        fsm_post_param: POST parameter name for inline transitions.
        fsm_transition_form_template: Template for transition argument forms.

    Example:
        >>> @admin.register(BlogPost)
        >>> class BlogPostAdmin(FSMAdminMixin, admin.ModelAdmin):
        ...     fsm_fields = ['state']
        ...
        ...     # Optionally customize messages
        ...     fsm_transition_success_msg = "State changed to '{target_state}'!"

    Note:
        FSMAdminMixin should come before ModelAdmin in the inheritance order
        to ensure proper method resolution.
    """

    # Template for the change form with transition buttons
    change_form_template: str = "django_fsm_rx/fsm_admin_change_form.html"

    # Template for transition forms (when arguments are needed)
    fsm_transition_form_template: str = "django_fsm_rx/fsm_transition_form.html"

    # List of FSM field names to manage
    fsm_fields: list[str] = []

    # Cascade widget configuration for hierarchical status codes
    # Format: {"field_name": {"levels": 3, "separator": "-", "labels": ["Cat", "Sub", "Status"]}}
    fsm_cascade_fields: dict[str, dict[str, Any]] = {}

    # Message templates
    fsm_transition_success_msg: str = _("FSM transition '{transition_name}' succeeded.")
    fsm_transition_error_msg: str = _("FSM transition '{transition_name}' failed: {error}.")
    fsm_transition_not_allowed_msg: str = _("FSM transition '{transition_name}' is not allowed.")
    fsm_transition_not_valid_msg: str = _("FSM transition '{transition_name}' is not valid.")
    fsm_transition_conditions_not_met_msg: str = _("FSM transition '{transition_name}' conditions not met.")

    # Template context configuration
    fsm_context_key: str = "fsm_object_transitions"
    fsm_post_param: str = "_fsm_transition_to"

    def get_fsm_field_instance(self, fsm_field_name: str) -> FSMFieldMixin | None:
        """
        Get the FSM field instance by name.

        Args:
            fsm_field_name: Name of the FSM field.

        Returns:
            The FSM field instance if found, None otherwise.
        """
        try:
            field = self.model._meta.get_field(fsm_field_name)
            if isinstance(field, FSMFieldMixin):
                return field
            return None
        except FieldDoesNotExist:
            return None

    def get_readonly_fields(self, request: HttpRequest, obj: Any = None) -> tuple[str, ...]:
        """
        Add protected FSM fields to the read-only fields list.

        Protected FSM fields should not be directly editable in admin;
        state changes should only happen through transitions.

        Args:
            request: The current request.
            obj: The model instance being edited.

        Returns:
            Tuple of read-only field names.
        """
        readonly_fields = list(super().get_readonly_fields(request, obj) or [])

        for fsm_field_name in self.fsm_fields:
            if fsm_field_name in readonly_fields:
                continue
            field = self.get_fsm_field_instance(fsm_field_name)
            if field and getattr(field, "protected", False):
                readonly_fields.append(fsm_field_name)

        return tuple(readonly_fields)

    def formfield_for_dbfield(self, db_field: Any, request: HttpRequest, **kwargs: Any) -> Any:
        """
        Configure form field widgets, including cascade widget for configured fields.

        If a field is configured in fsm_cascade_fields, uses FSMCascadeWidget.

        Args:
            db_field: The database field.
            request: The current request.
            **kwargs: Additional keyword arguments.

        Returns:
            The form field instance.
        """
        if db_field.name in self.fsm_cascade_fields:
            config = self.fsm_cascade_fields[db_field.name]
            choices = getattr(db_field, "choices", None) or []

            # Get allowed transitions if we have an object
            allowed_targets = None
            # Note: allowed_targets filtering happens in the widget

            kwargs["widget"] = FSMCascadeWidget(
                levels=config.get("levels", 2),
                separator=config.get("separator", "-"),
                labels=config.get("labels"),
                choices=list(choices),
                allowed_targets=allowed_targets,
            )

        return super().formfield_for_dbfield(db_field, request, **kwargs)

    def get_fsm_block_label(self, fsm_field_name: str) -> str:
        """
        Get the display label for a transition block.

        Override this method to customize transition block labels.

        Args:
            fsm_field_name: Name of the FSM field.

        Returns:
            The label to display for this field's transitions.
        """
        return f"Transitions ({fsm_field_name})"

    def get_fsm_transition_label(self, transition: Transition) -> str:
        """
        Get the display label for a transition button.

        Uses the transition's custom 'label' or 'short_description' if set,
        otherwise falls back to the transition name.

        Args:
            transition: The transition object.

        Returns:
            The label to display for this transition.
        """
        custom = transition.custom or {}
        if "label" in custom:
            return str(custom["label"])
        if "short_description" in custom:
            return str(custom["short_description"])
        # Convert method name to title case
        return transition.name.replace("_", " ").title()

    def is_fsm_transition_visible(self, transition: Transition) -> bool:
        """
        Check if a transition should be visible in admin.

        Transitions can be hidden by setting custom={'admin': False}.
        If FSM_ADMIN_FORCE_PERMIT is True in settings, transitions must
        explicitly set custom={'admin': True} to be visible.

        Args:
            transition: The transition to check.

        Returns:
            True if the transition should be shown, False otherwise.
        """
        from django.conf import settings

        custom = transition.custom or {}
        force_permit = getattr(settings, "FSM_ADMIN_FORCE_PERMIT", False)

        if force_permit:
            return custom.get("admin", False) is True
        return custom.get("admin", True) is not False

    def get_fsm_object_transitions(self, request: HttpRequest, obj: Model) -> list[FSMObjectTransitions]:
        """
        Get available transitions for each FSM field on the object.

        Filters transitions by:
        - User permissions (via get_available_user_FIELD_transitions)
        - Admin visibility (via is_fsm_transition_visible)

        Args:
            request: The current request.
            obj: The model instance.

        Returns:
            List of FSMObjectTransitions for each configured FSM field.
        """
        fsm_object_transitions = []

        for field_name in sorted(self.fsm_fields):
            func = getattr(obj, f"get_available_user_{field_name}_transitions", None)
            if func:
                transitions = [t for t in func(request.user) if self.is_fsm_transition_visible(t)]
                fsm_object_transitions.append(
                    FSMObjectTransitions(
                        fsm_field=field_name,
                        block_label=self.get_fsm_block_label(field_name),
                        available_transitions=transitions,
                    )
                )

        return fsm_object_transitions

    def get_fsm_transition_form(self, transition: Transition) -> type[Form] | None:
        """
        Get the form class for a transition that requires arguments.

        Transitions can specify a form via custom={'form': FormClass} or
        custom={'form': 'myapp.forms.MyForm'} (dotted path).

        Args:
            transition: The transition to get a form for.

        Returns:
            The form class if specified, None otherwise.
        """
        custom = transition.custom or {}
        form = custom.get("form")
        if form is None:
            return None
        if isinstance(form, str):
            return import_string(form)
        return form

    def change_view(
        self,
        request: HttpRequest,
        object_id: str,
        form_url: str = "",
        extra_context: dict[str, Any] | None = None,
    ) -> HttpResponse:
        """
        Render the change form with FSM transition data.

        Injects available transitions into the template context for
        rendering transition buttons.

        Args:
            request: The current request.
            object_id: The object's primary key.
            form_url: Optional form URL override.
            extra_context: Additional template context.

        Returns:
            The rendered change form response.
        """
        context = extra_context or {}
        obj = self.get_object(request, object_id)

        if obj is not None:
            context[self.fsm_context_key] = self.get_fsm_object_transitions(
                request=request,
                obj=obj,
            )
            # Pass helper function to template
            context["get_fsm_transition_label"] = self.get_fsm_transition_label

        return super().change_view(
            request=request,
            object_id=object_id,
            form_url=form_url,
            extra_context=context,
        )

    def get_fsm_redirect_url(self, request: HttpRequest, obj: Model) -> str:
        """
        Get the URL to redirect to after a transition.

        Override this to customize post-transition redirect behavior.

        Args:
            request: The current request.
            obj: The model instance.

        Returns:
            The redirect URL (defaults to current path).
        """
        return request.path

    def get_fsm_response(self, request: HttpRequest, obj: Model) -> HttpResponse:
        """
        Create the response after a transition.

        Handles preserved filters to maintain list view state.

        Args:
            request: The current request.
            obj: The model instance.

        Returns:
            Redirect response to the appropriate URL.
        """
        redirect_url = self.get_fsm_redirect_url(request, obj)
        redirect_url = add_preserved_filters(
            context={
                "preserved_filters": self.get_preserved_filters(request),
                "opts": self.model._meta,
            },
            url=redirect_url,
        )
        return HttpResponseRedirect(redirect_url)

    def _execute_transition(
        self,
        request: HttpRequest,
        obj: Model,
        transition_name: str,
        transition_kwargs: dict[str, Any] | None = None,
    ) -> bool:
        """
        Execute a transition with optional arguments.

        Handles logging integration with django-fsm-log if available.

        Args:
            request: The current request.
            obj: The model instance.
            transition_name: Name of the transition method.
            transition_kwargs: Optional keyword arguments for the transition.

        Returns:
            True if transition succeeded, False otherwise.
        """
        if transition_kwargs is None:
            transition_kwargs = {}

        try:
            transition_func = getattr(obj, transition_name)
        except AttributeError:
            self.message_user(
                request,
                self.fsm_transition_not_valid_msg.format(transition_name=transition_name),
                level=messages.ERROR,
            )
            return False

        # Try different calling signatures for django-fsm-log compatibility
        try:
            # First try with 'by' parameter (django-fsm-log support)
            transition_func(by=request.user, **transition_kwargs)
        except TypeError:
            try:
                # Then try with request parameter
                transition_func(request=request, **transition_kwargs)
            except TypeError:
                # Finally try plain call
                transition_func(**transition_kwargs)

        obj.save()
        return True

    def response_change(self, request: HttpRequest, obj: Model) -> HttpResponse:
        """
        Handle the response after saving, including inline FSM transitions.

        This method processes the fsm_post_param from the form submission
        to execute transitions that don't require arguments.

        Args:
            request: The current request.
            obj: The saved model instance.

        Returns:
            The appropriate HTTP response.
        """
        if self.fsm_post_param not in request.POST:
            return super().response_change(request, obj)

        transition_name = request.POST[self.fsm_post_param]

        try:
            if self._execute_transition(request, obj, transition_name):
                self.message_user(
                    request,
                    self.fsm_transition_success_msg.format(transition_name=transition_name),
                    level=messages.SUCCESS,
                )
        except TransitionNotAllowed:
            self.message_user(
                request,
                self.fsm_transition_not_allowed_msg.format(transition_name=transition_name),
                level=messages.ERROR,
            )
        except ConcurrentTransition as err:
            self.message_user(
                request,
                self.fsm_transition_error_msg.format(transition_name=transition_name, error=str(err)),
                level=messages.ERROR,
            )
        except Exception as err:
            self.message_user(
                request,
                self.fsm_transition_error_msg.format(transition_name=transition_name, error=str(err)),
                level=messages.ERROR,
            )

        return self.get_fsm_response(request, obj)

    def get_urls(self) -> list:
        """
        Add custom URL for transitions with arguments.

        Returns:
            List of URL patterns including the transition view.
        """
        urls = super().get_urls()
        info = self.model._meta.app_label, self.model._meta.model_name
        custom_urls = [
            path(
                "<path:object_id>/fsm-transition/<str:transition_name>/",
                self.admin_site.admin_view(self.fsm_transition_view),
                name="{}_{}_fsm_transition".format(*info),
            ),
        ]
        return custom_urls + urls

    def fsm_transition_view(
        self,
        request: HttpRequest,
        object_id: str,
        transition_name: str,
    ) -> HttpResponse:
        """
        Handle transitions that require form arguments.

        This view:
        1. Validates the transition exists and has a form
        2. Displays the form for GET requests
        3. Processes the form and executes the transition for POST requests

        Args:
            request: The current request.
            object_id: The object's primary key.
            transition_name: Name of the transition method.

        Returns:
            Form page or redirect response.
        """
        obj = self.get_object(request, object_id)
        if obj is None:
            return HttpResponseBadRequest("Object not found")

        # Get the transition method
        transition_method = getattr(obj, transition_name, None)
        if transition_method is None or not hasattr(transition_method, "_django_fsm_rx"):
            return HttpResponseBadRequest(f"'{transition_name}' is not a valid transition")

        # Get transition metadata
        meta = transition_method._django_fsm_rx
        current_state = meta.field.get_state(obj)
        transition = meta.get_transition(current_state)

        if transition is None:
            self.message_user(
                request,
                self.fsm_transition_not_allowed_msg.format(transition_name=transition_name),
                level=messages.ERROR,
            )
            return self.get_fsm_response(request, obj)

        # Get form class
        form_class = self.get_fsm_transition_form(transition)

        if form_class is None:
            # No form needed, execute directly
            try:
                if self._execute_transition(request, obj, transition_name):
                    self.message_user(
                        request,
                        self.fsm_transition_success_msg.format(transition_name=transition_name),
                        level=messages.SUCCESS,
                    )
            except TransitionNotAllowed:
                self.message_user(
                    request,
                    self.fsm_transition_not_allowed_msg.format(transition_name=transition_name),
                    level=messages.ERROR,
                )
            except Exception as err:
                self.message_user(
                    request,
                    self.fsm_transition_error_msg.format(transition_name=transition_name, error=str(err)),
                    level=messages.ERROR,
                )
            return self.get_fsm_response(request, obj)

        # Handle form
        if request.method == "POST":
            form = form_class(request.POST, request.FILES)
            if form.is_valid():
                try:
                    if self._execute_transition(request, obj, transition_name, form.cleaned_data):
                        self.message_user(
                            request,
                            self.fsm_transition_success_msg.format(transition_name=transition_name),
                            level=messages.SUCCESS,
                        )
                    return self.get_fsm_response(request, obj)
                except TransitionNotAllowed:
                    self.message_user(
                        request,
                        self.fsm_transition_not_allowed_msg.format(transition_name=transition_name),
                        level=messages.ERROR,
                    )
                except Exception as err:
                    self.message_user(
                        request,
                        self.fsm_transition_error_msg.format(transition_name=transition_name, error=str(err)),
                        level=messages.ERROR,
                    )
        else:
            form = form_class()

        # Build context for form template
        info = self.model._meta.app_label, self.model._meta.model_name
        context = {
            **self.admin_site.each_context(request),
            "title": f"Transition: {self.get_fsm_transition_label(transition)}",
            "form": form,
            "object": obj,
            "object_id": object_id,
            "transition": transition,
            "transition_name": transition_name,
            "transition_label": self.get_fsm_transition_label(transition),
            "opts": self.model._meta,
            "app_label": self.model._meta.app_label,
            "original": obj,
            "has_view_permission": self.has_view_permission(request, obj),
            "has_change_permission": self.has_change_permission(request, obj),
            "change_url": reverse(
                f"admin:{info[0]}_{info[1]}_change",
                args=[object_id],
            ),
        }

        return render(request, self.fsm_transition_form_template, context)


class FSMTransitionInline(admin.TabularInline):
    """
    Inline admin for displaying FSM transition history.

    Use this with django-fsm-log's StateLog model to show
    transition history in the admin change form.

    Example:
        >>> from django_fsm_log.models import StateLog
        >>>
        >>> class StateLogInline(FSMTransitionInline):
        ...     model = StateLog
        ...
        >>> @admin.register(BlogPost)
        >>> class BlogPostAdmin(FSMAdminMixin, admin.ModelAdmin):
        ...     fsm_fields = ['state']
        ...     inlines = [StateLogInline]
    """

    extra = 0
    can_delete = False
    readonly_fields = ["timestamp", "source_state", "state", "transition", "by"]
    fields = readonly_fields

    def has_add_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Disable adding new log entries manually."""
        return False

    def has_change_permission(self, request: HttpRequest, obj: Any = None) -> bool:
        """Disable editing log entries."""
        return False
