"""
State tracking functionality for django models.

This module provides a declarative state machine for Django models,
allowing you to define state transitions with conditions, permissions,
and callbacks.

Example:
    >>> from django_fsm_rx import FSMField, transition
    >>> class BlogPost(models.Model):
    ...     state = FSMField(default='draft')
    ...
    ...     @transition(field=state, source='draft', target='published')
    ...     def publish(self):
    ...         pass
"""

from __future__ import annotations

import inspect
from collections.abc import Callable
from collections.abc import Iterator
from collections.abc import Sequence
from functools import partialmethod
from functools import wraps
from typing import TYPE_CHECKING
from typing import Any
from typing import TypeVar
from typing import Union

from django.apps import apps as django_apps
from django.db import models
from django.db.models import Field
from django.db.models import Model
from django.db.models import QuerySet
from django.db.models.query_utils import DeferredAttribute
from django.db.models.signals import class_prepared

from django_fsm_rx.signals import post_transition
from django_fsm_rx.signals import pre_transition

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

__all__ = [
    "TransitionNotAllowed",
    "ConcurrentTransition",
    "InvalidResultState",
    "FSMFieldMixin",
    "FSMField",
    "FSMIntegerField",
    "FSMKeyField",
    "FSMModelMixin",
    "ConcurrentTransitionMixin",
    "transition",
    "can_proceed",
    "has_transition_perm",
    "GET_STATE",
    "RETURN_VALUE",
    "State",
    "Transition",
    "TransitionCallback",
    "FSMMeta",
]

# Type aliases for better readability and documentation
# Note: Using Union for type aliases with string forward references (required at runtime)
StateValue = str | int
"""A state value - either a string or integer representing a state."""

ConditionFunc = Callable[[Any], bool]
"""A condition function that takes a model instance and returns a boolean."""

PermissionFunc = Callable[[Any, "AbstractBaseUser"], bool]
"""A permission function that takes a model instance and user, returns boolean."""

PermissionType = Union[str, PermissionFunc, None]  # noqa: UP007
"""Permission can be a string (permission codename), a callable, or None."""

StateTarget = Union[StateValue, "State", None]  # noqa: UP007
"""Target state can be a value, a State subclass instance, or None (no change)."""

StateSource = Union[StateValue, Sequence[StateValue], str]  # noqa: UP007
"""Source state can be a value, list of values, '*' (any), or '+' (any except target)."""

CustomDict = dict[str, Any]
"""Custom properties dictionary for transitions."""

TransitionCallback = Callable[..., None]
"""
Callback function invoked after successful transition.

The callback receives:
- instance: The model instance that transitioned
- source: The source state (before transition)
- target: The target state (after transition)
- **kwargs: Additional keyword arguments including method_args and method_kwargs

Example:
    def log_transition(instance, source, target, **kwargs):
        TransitionLog.objects.create(
            model_instance=instance,
            from_state=source,
            to_state=target,
        )

    @transition(field=state, source='draft', target='published', on_success=log_transition)
    def publish(self):
        pass
"""

_F = TypeVar("_F", bound=Callable[..., Any])
"""TypeVar for decorated transition methods."""

_M = TypeVar("_M", bound=Model)
"""TypeVar for Django model instances."""


class TransitionNotAllowed(Exception):
    """
    Raised when a transition is not allowed.

    This exception is raised when:
    - The current state does not allow the requested transition
    - Transition conditions are not met

    Attributes:
        object: The model instance that failed the transition (optional).
        method: The transition method that was called (optional).

    Example:
        >>> try:
        ...     post.publish()
        ... except TransitionNotAllowed as e:
        ...     print(f"Cannot transition {e.object} via {e.method}")
    """

    object: Any
    method: Callable[..., Any] | None

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        self.object = kwargs.pop("object", None)
        self.method = kwargs.pop("method", None)
        super().__init__(*args, **kwargs)


class InvalidResultState(Exception):
    """
    Raised when a dynamic state resolution returns an invalid state.

    This occurs when using RETURN_VALUE or GET_STATE with allowed_states
    and the computed state is not in the allowed list.

    Example:
        >>> @transition(field=state, source='*', target=RETURN_VALUE('a', 'b'))
        ... def change(self):
        ...     return 'c'  # Raises InvalidResultState - 'c' not in ['a', 'b']
    """


class ConcurrentTransition(Exception):
    """
    Raised when the transition cannot be executed due to concurrent modification.

    This exception is raised by ConcurrentTransitionMixin when the object's
    state has been changed in the database since it was fetched (optimistic
    locking failure).

    Example:
        >>> # In transaction 1:
        >>> post = BlogPost.objects.get(pk=1)  # state='draft'
        >>>
        >>> # In transaction 2 (concurrent):
        >>> post2 = BlogPost.objects.get(pk=1)
        >>> post2.publish()
        >>> post2.save()  # state='published' in DB
        >>>
        >>> # Back in transaction 1:
        >>> post.publish()
        >>> post.save()  # Raises ConcurrentTransition
    """


class Transition:
    """
    Represents a single state transition.

    A Transition encapsulates all the metadata about moving from one state
    to another, including conditions, permissions, and custom properties.

    Attributes:
        method: The decorated transition method.
        source: The source state(s) for this transition.
        target: The target state after transition.
        on_error: State to transition to if an exception occurs.
        conditions: List of condition functions that must all return True.
        permission: Permission string or callable for access control.
        custom: Dictionary of custom properties attached to the transition.
        on_success: Callback function invoked after successful transition.
        name: The name of the transition method (read-only property).

    Example:
        >>> # Transitions are typically created via the @transition decorator
        >>> @transition(field=state, source='draft', target='published',
        ...             conditions=[is_valid], permission='blog.publish')
        ... def publish(self):
        ...     pass
    """

    method: Callable[..., Any]
    source: StateValue
    target: StateTarget
    on_error: StateValue | None
    conditions: list[ConditionFunc] | None
    permission: PermissionType
    custom: CustomDict
    on_success: TransitionCallback | None

    def __init__(
        self,
        method: Callable[..., Any],
        source: StateValue,
        target: StateTarget,
        on_error: StateValue | None,
        conditions: list[ConditionFunc] | None,
        permission: PermissionType,
        custom: CustomDict,
        on_success: TransitionCallback | None = None,
    ) -> None:
        self.method = method
        self.source = source
        self.target = target
        self.on_error = on_error
        self.conditions = conditions
        self.permission = permission
        self.custom = custom
        self.on_success = on_success

    @property
    def name(self) -> str:
        """Return the name of the transition method."""
        return self.method.__name__

    def has_perm(self, instance: Model, user: AbstractBaseUser) -> bool:
        """
        Check if user has permission to execute this transition.

        Args:
            instance: The model instance being transitioned.
            user: The user attempting the transition.

        Returns:
            True if user has permission, False otherwise.
        """
        if not self.permission:
            return True
        if callable(self.permission):
            return bool(self.permission(instance, user))
        if user.has_perm(self.permission, instance):
            return True
        if user.has_perm(self.permission):
            return True
        return False

    def __hash__(self) -> int:
        return hash(self.name)

    def __eq__(self, other: object) -> bool:
        if isinstance(other, str):
            return other == self.name
        if isinstance(other, Transition):
            return other.name == self.name
        return False


def get_available_FIELD_transitions(instance: Model, field: FSMFieldMixin) -> Iterator[Transition]:
    """
    Get transitions available from the current state with all conditions met.

    This function is used internally to implement the dynamic
    `get_available_FIELD_transitions` method on model instances.

    Args:
        instance: The model instance to check transitions for.
        field: The FSM field to check transitions on.

    Yields:
        Transition objects that are available from the current state
        and whose conditions are all satisfied.

    Example:
        >>> post = BlogPost.objects.get(pk=1)
        >>> for t in post.get_available_state_transitions():
        ...     print(f"Can {t.name}: {t.source} -> {t.target}")
    """
    curr_state = field.get_state(instance)
    transitions = field.transitions[instance.__class__]

    for transition in transitions.values():
        meta: FSMMeta = transition._django_fsm_rx
        if meta.has_transition(curr_state) and meta.conditions_met(instance, curr_state):
            yield meta.get_transition(curr_state)


def get_all_FIELD_transitions(instance: Model, field: FSMFieldMixin) -> Iterator[Transition]:
    """
    Get all transitions declared for this field, regardless of current state.

    This function is used internally to implement the dynamic
    `get_all_FIELD_transitions` method on model instances.

    Args:
        instance: The model instance to check transitions for.
        field: The FSM field to check transitions on.

    Returns:
        Iterator of all Transition objects declared for this field.

    Example:
        >>> post = BlogPost.objects.get(pk=1)
        >>> for t in post.get_all_state_transitions():
        ...     print(f"{t.name}: {t.source} -> {t.target}")
    """
    return field.get_all_transitions(instance.__class__)


def get_available_user_FIELD_transitions(instance: Model, user: AbstractBaseUser, field: FSMFieldMixin) -> Iterator[Transition]:
    """
    Get transitions available to a specific user from the current state.

    Filters transitions by:
    1. Current state allows the transition
    2. All conditions are met
    3. User has the required permission

    This function is used internally to implement the dynamic
    `get_available_user_FIELD_transitions` method on model instances.

    Args:
        instance: The model instance to check transitions for.
        user: The user to check permissions for.
        field: The FSM field to check transitions on.

    Yields:
        Transition objects available to the user.

    Example:
        >>> post = BlogPost.objects.get(pk=1)
        >>> for t in post.get_available_user_state_transitions(request.user):
        ...     print(f"User can {t.name}")
    """
    for transition in get_available_FIELD_transitions(instance, field):
        if transition.has_perm(instance, user):
            yield transition


class FSMMeta:
    """
    Metadata container for transition methods.

    FSMMeta stores all transitions registered on a single method,
    indexed by source state. It provides methods to look up transitions,
    check conditions, and verify permissions.

    Attributes:
        field: The FSM field this metadata is associated with.
        transitions: Dictionary mapping source states to Transition objects.
    """

    field: FSMFieldMixin | str
    transitions: dict[StateValue, Transition]

    def __init__(self, field: FSMFieldMixin | str, method: Callable[..., Any]) -> None:
        self.field = field
        self.transitions = {}  # source -> Transition

    def _matches_prefix_pattern(self, pattern: str, state: StateValue) -> bool:
        """
        Check if state matches a prefix wildcard pattern.

        Supports patterns like 'WRK-*' which matches 'WRK-REP-PRG', 'WRK-INS-PRG', etc.
        This enables hierarchical status codes (e.g., AAA-BBB-CCC format).

        Args:
            pattern: A pattern ending with '-*' (e.g., 'WRK-*', 'WRK-REP-*')
            state: The current state value to check

        Returns:
            True if the state starts with the pattern prefix.
        """
        if not isinstance(pattern, str) or not pattern.endswith("-*"):
            return False
        if not isinstance(state, str):
            return False
        prefix = pattern[:-1]  # Remove the '*', keep the '-'
        return state.startswith(prefix)

    def _find_prefix_transition(self, state: StateValue) -> Transition | None:
        """
        Find a transition matching a prefix wildcard pattern.

        Searches through registered transitions for prefix patterns (ending in '-*')
        that match the given state. Returns the most specific match (longest prefix).

        Args:
            state: The current state value.

        Returns:
            The matching Transition or None.
        """
        if not isinstance(state, str):
            return None

        # Find all matching prefix patterns, sorted by specificity (longest first)
        matches: list[tuple[str, Transition]] = []
        for pattern, transition in self.transitions.items():
            if self._matches_prefix_pattern(pattern, state):
                matches.append((pattern, transition))

        if not matches:
            return None

        # Return the most specific match (longest prefix)
        matches.sort(key=lambda x: len(x[0]), reverse=True)
        return matches[0][1]

    def get_transition(self, source: StateValue) -> Transition | None:
        """
        Get the transition for a given source state.

        Looks up transitions in order:
        1. Exact source state match
        2. Prefix wildcard match (e.g., 'WRK-*' matches 'WRK-REP-PRG')
        3. Wildcard '*' (any state)
        4. Wildcard '+' (any state except target)

        Args:
            source: The source state to look up.

        Returns:
            The Transition object if found, None otherwise.
        """
        # 1. Exact match
        transition = self.transitions.get(source, None)
        if transition is not None:
            return transition

        # 2. Prefix wildcard match (e.g., 'WRK-*')
        transition = self._find_prefix_transition(source)
        if transition is not None:
            return transition

        # 3. Universal wildcard '*'
        transition = self.transitions.get("*", None)
        if transition is not None:
            return transition

        # 4. Any-except-target wildcard '+'
        return self.transitions.get("+", None)

    def add_transition(
        self,
        method: Callable[..., Any],
        source: StateValue,
        target: StateTarget,
        on_error: StateValue | None = None,
        conditions: list[ConditionFunc] | None = None,
        permission: PermissionType = None,
        custom: CustomDict | None = None,
        on_success: TransitionCallback | None = None,
    ) -> None:
        """
        Register a new transition from a source state.

        Args:
            method: The transition method.
            source: The source state for this transition.
            target: The target state after transition.
            on_error: State to transition to on exception.
            conditions: List of condition functions.
            permission: Permission string or callable.
            custom: Custom properties dictionary.
            on_success: Callback function invoked after successful transition.

        Raises:
            AssertionError: If a transition from this source already exists.
        """
        if source in self.transitions:
            raise AssertionError(f"Duplicate transition for {source} state")

        self.transitions[source] = Transition(
            method=method,
            source=source,
            target=target,
            on_error=on_error,
            conditions=conditions if conditions is not None else [],
            permission=permission,
            custom=custom if custom is not None else {},
            on_success=on_success,
        )

    def has_transition(self, state: StateValue) -> bool:
        """
        Check if a transition exists from the given state.

        Handles wildcard transitions:
        - Prefix wildcards like 'WRK-*' match 'WRK-REP-PRG', 'WRK-INS-PRG', etc.
        - '*' matches any state
        - '+' matches any state except the target state

        Args:
            state: The current state to check.

        Returns:
            True if a transition exists from this state.
        """
        # Exact match
        if state in self.transitions:
            return True

        # Prefix wildcard match (e.g., 'WRK-*')
        if self._find_prefix_transition(state) is not None:
            return True

        # Universal wildcard '*'
        if "*" in self.transitions:
            return True

        # Any-except-target wildcard '+'
        if "+" in self.transitions and self.transitions["+"].target != state:
            return True

        return False

    def conditions_met(self, instance: Model, state: StateValue) -> bool:
        """
        Check if all conditions are met for the transition from this state.

        Args:
            instance: The model instance to check conditions on.
            state: The current state.

        Returns:
            True if all conditions are met (or no conditions exist).
        """
        transition = self.get_transition(state)

        if transition is None:
            return False

        if transition.conditions is None:
            return True

        return all(condition(instance) for condition in transition.conditions)

    def has_transition_perm(self, instance: Model, state: StateValue, user: AbstractBaseUser) -> bool:
        """
        Check if user has permission for the transition from this state.

        Args:
            instance: The model instance.
            state: The current state.
            user: The user to check permission for.

        Returns:
            True if user has permission.
        """
        transition = self.get_transition(state)

        if not transition:
            return False

        return transition.has_perm(instance, user)

    def next_state(self, current_state: StateValue) -> StateTarget:
        """
        Get the target state for a transition from the current state.

        Args:
            current_state: The current state.

        Returns:
            The target state (may be a State subclass for dynamic resolution).

        Raises:
            TransitionNotAllowed: If no transition exists from current state.
        """
        transition = self.get_transition(current_state)

        if transition is None:
            raise TransitionNotAllowed(f"No transition from {current_state}")

        return transition.target

    def exception_state(self, current_state: StateValue) -> StateValue | None:
        """
        Get the error state for a transition from the current state.

        Args:
            current_state: The current state.

        Returns:
            The on_error state if defined, None otherwise.

        Raises:
            TransitionNotAllowed: If no transition exists from current state.
        """
        transition = self.get_transition(current_state)

        if transition is None:
            raise TransitionNotAllowed(f"No transition from {current_state}")

        return transition.on_error


class FSMFieldDescriptor:
    """
    Descriptor that controls access to FSM field values.

    This descriptor intercepts get/set operations on FSM fields to:
    - Handle deferred field loading
    - Enforce protection against direct modification
    - Trigger proxy class changes when appropriate

    Attributes:
        field: The FSM field this descriptor manages.
    """

    field: FSMFieldMixin

    def __init__(self, field: FSMFieldMixin) -> None:
        self.field = field

    def __get__(self, instance: Model | None, type: type[Model] | None = None) -> Any:
        """
        Get the current state value.

        Args:
            instance: The model instance (None for class access).
            type: The model class.

        Returns:
            The descriptor itself if accessed on class, state value otherwise.
        """
        if instance is None:
            return self
        return self.field.get_state(instance)

    def __set__(self, instance: Model, value: StateValue) -> None:
        """
        Set the state value with protection checks.

        Args:
            instance: The model instance.
            value: The new state value.

        Raises:
            AttributeError: If field is protected and already has a value.
        """
        if self.field.protected and self.field.name in instance.__dict__:
            raise AttributeError(f"Direct {self.field.name} modification is not allowed")

        # Update state
        self.field.set_proxy(instance, value)
        self.field.set_state(instance, value)


class FSMFieldMixin:
    """
    Base mixin providing FSM functionality for Django model fields.

    This mixin adds state machine capabilities to Django model fields,
    including transition management, state tracking, and proxy class support.

    Attributes:
        descriptor_class: The descriptor class to use for field access.
        protected: If True, prevents direct field modification.
        transitions: Dictionary mapping model classes to their transitions.
        state_proxy: Dictionary mapping states to proxy class references.

    Example:
        >>> class MyFSMField(FSMFieldMixin, models.CharField):
        ...     pass
        >>>
        >>> class BlogPost(models.Model):
        ...     state = MyFSMField(default='draft', protected=True)
    """

    descriptor_class: type[FSMFieldDescriptor] = FSMFieldDescriptor
    protected: bool
    transitions: dict[type[Model], dict[str, Callable[..., Any]]]
    state_proxy: dict[StateValue, str]
    base_cls: type[Model]
    name: str  # Inherited from Field

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """
        Initialize the FSM field.

        Args:
            *args: Positional arguments passed to parent field.
            **kwargs: Keyword arguments. Special FSM kwargs:
                - protected: Prevent direct field modification (default: False).
                - state_choices: Tuple of (state, title, proxy_class_ref) for
                  state-dependent proxy models.
        """
        self.protected = kwargs.pop("protected", False)
        self.transitions = {}  # cls -> (transitions name -> method)
        self.state_proxy = {}  # state -> ProxyClsRef

        state_choices: list[tuple[StateValue, str, str]] | None = kwargs.pop("state_choices", None)
        choices = kwargs.get("choices", None)
        if state_choices is not None and choices is not None:
            raise ValueError("Use one of choices or state_choices value")

        if state_choices is not None:
            choices = []
            for state, title, proxy_cls_ref in state_choices:
                choices.append((state, title))
                self.state_proxy[state] = proxy_cls_ref
            kwargs["choices"] = choices

        super().__init__(*args, **kwargs)

    def deconstruct(self) -> tuple[str, str, list[Any], dict[str, Any]]:
        """
        Deconstruct the field for migration serialization.

        Returns:
            Tuple of (name, path, args, kwargs) for reconstruction.
        """
        name, path, args, kwargs = super().deconstruct()  # type: ignore[misc]
        if self.protected:
            kwargs["protected"] = self.protected
        return name, path, args, kwargs

    def get_state(self, instance: Model) -> StateValue:
        """
        Get the current state value from a model instance.

        Handles deferred field loading automatically via Django's
        DeferredAttribute mechanism.

        Args:
            instance: The model instance to get state from.

        Returns:
            The current state value.
        """
        # The state field may be deferred. We delegate the logic of figuring this out
        # and loading the deferred field on-demand to Django's built-in DeferredAttribute class.
        return DeferredAttribute(self).__get__(instance)  # type: ignore[arg-type]

    def set_state(self, instance: Model, state: StateValue) -> None:
        """
        Set the state value on a model instance.

        Args:
            instance: The model instance.
            state: The new state value.
        """
        instance.__dict__[self.name] = state

    def set_proxy(self, instance: Model, state: StateValue) -> None:
        """
        Change the instance's class to the proxy class for the given state.

        If state_choices was provided with proxy class references, this method
        will dynamically change the instance's __class__ to the appropriate
        proxy model.

        Args:
            instance: The model instance.
            state: The new state value.

        Raises:
            ValueError: If the proxy class reference cannot be resolved.
        """
        if state in self.state_proxy:
            state_proxy = self.state_proxy[state]

            try:
                app_label, model_name = state_proxy.split(".")
            except ValueError:
                # If we can't split, assume a model in current app
                app_label = instance._meta.app_label
                model_name = state_proxy

            model = django_apps.get_app_config(app_label).get_model(model_name)

            if model is None:
                raise ValueError(f"No model found {state_proxy}")

            instance.__class__ = model

    def change_state(self, instance: Model, method: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
        """
        Execute a state transition.

        This method:
        1. Validates the transition is allowed from current state
        2. Checks all conditions are met
        3. Sends pre_transition signal
        4. Executes the transition method
        5. Updates state (handles dynamic state resolution)
        6. Sends post_transition signal

        Args:
            instance: The model instance.
            method: The transition method to execute.
            *args: Arguments to pass to the method.
            **kwargs: Keyword arguments to pass to the method.

        Returns:
            The return value of the transition method.

        Raises:
            TransitionNotAllowed: If transition is not allowed or conditions not met.
        """
        meta: FSMMeta = method._django_fsm_rx
        method_name = method.__name__
        current_state = self.get_state(instance)

        if not meta.has_transition(current_state):
            raise TransitionNotAllowed(
                f"Can't switch from state '{current_state}' using method '{method_name}'",
                object=instance,
                method=method,
            )
        if not meta.conditions_met(instance, current_state):
            raise TransitionNotAllowed(
                f"Transition conditions have not been met for method '{method_name}'",
                object=instance,
                method=method,
            )

        next_state = meta.next_state(current_state)

        signal_kwargs: dict[str, Any] = {
            "sender": instance.__class__,
            "instance": instance,
            "name": method_name,
            "field": meta.field,
            "source": current_state,
            "target": next_state,
            "method_args": args,
            "method_kwargs": kwargs,
        }

        pre_transition.send(**signal_kwargs)

        try:
            result = method(instance, *args, **kwargs)
            if next_state is not None:
                if hasattr(next_state, "get_state"):
                    next_state = next_state.get_state(instance, method, result, args=args, kwargs=kwargs)
                    signal_kwargs["target"] = next_state
                self.set_proxy(instance, next_state)
                self.set_state(instance, next_state)
        except Exception as exc:
            exception_state = meta.exception_state(current_state)
            if exception_state:
                self.set_proxy(instance, exception_state)
                self.set_state(instance, exception_state)
                signal_kwargs["target"] = exception_state
                signal_kwargs["exception"] = exc
                post_transition.send(**signal_kwargs)
            raise
        else:
            post_transition.send(**signal_kwargs)

            # Call on_success callback if defined
            transition = meta.get_transition(current_state)
            if transition and transition.on_success:
                transition.on_success(
                    instance=instance,
                    source=current_state,
                    target=next_state,
                    method_args=args,
                    method_kwargs=kwargs,
                )

        return result

    def get_all_transitions(self, instance_cls: type[Model]) -> Iterator[Transition]:
        """
        Get all transitions declared for a model class.

        Args:
            instance_cls: The model class to get transitions for.

        Yields:
            All Transition objects declared on the model for this field.
        """
        transitions = self.transitions[instance_cls]

        for transition_method in transitions.values():
            meta: FSMMeta = transition_method._django_fsm_rx

            yield from meta.transitions.values()

    def contribute_to_class(self, cls: type[Model], name: str, **kwargs: Any) -> None:
        """
        Hook called by Django when adding the field to a model class.

        Sets up the descriptor and adds helper methods to the model class:
        - get_all_FIELD_transitions()
        - get_available_FIELD_transitions()
        - get_available_user_FIELD_transitions()

        Args:
            cls: The model class.
            name: The field name.
            **kwargs: Additional keyword arguments.
        """
        self.base_cls = cls

        super().contribute_to_class(cls, name, **kwargs)  # type: ignore[misc]
        setattr(cls, self.name, self.descriptor_class(self))
        setattr(
            cls,
            f"get_all_{self.name}_transitions",
            partialmethod(get_all_FIELD_transitions, field=self),
        )
        setattr(
            cls,
            f"get_available_{self.name}_transitions",
            partialmethod(get_available_FIELD_transitions, field=self),
        )
        setattr(
            cls,
            f"get_available_user_{self.name}_transitions",
            partialmethod(get_available_user_FIELD_transitions, field=self),
        )

        class_prepared.connect(self._collect_transitions)

    def _collect_transitions(self, *args: Any, **kwargs: Any) -> None:
        """
        Callback to collect transitions when a model class is prepared.

        This is connected to Django's class_prepared signal and runs when
        each model class is fully initialized.

        Args:
            *args: Signal arguments (unused).
            **kwargs: Signal keyword arguments. Must include 'sender'.
        """
        sender: type[Model] = kwargs["sender"]

        if not issubclass(sender, self.base_cls):
            return

        def is_field_transition_method(attr: Any) -> bool:
            return (
                (inspect.ismethod(attr) or inspect.isfunction(attr))
                and hasattr(attr, "_django_fsm_rx")
                and (
                    attr._django_fsm_rx.field in [self, self.name]
                    or (
                        isinstance(attr._django_fsm_rx.field, Field)
                        and attr._django_fsm_rx.field.name == self.name
                        and attr._django_fsm_rx.field.creation_counter == self.creation_counter  # type: ignore[attr-defined]
                    )
                )
            )

        sender_transitions: dict[str, Callable[..., Any]] = {}
        transitions = inspect.getmembers(sender, predicate=is_field_transition_method)
        for method_name, method in transitions:
            method._django_fsm_rx.field = self
            sender_transitions[method_name] = method

        self.transitions[sender] = sender_transitions


class FSMField(FSMFieldMixin, models.CharField):
    """
    CharField-based state machine field.

    This is the most common FSM field type, storing state as a string.
    Default max_length is 50 characters.

    Example:
        >>> class BlogPost(models.Model):
        ...     state = FSMField(default='draft')
        ...
        ...     @transition(field=state, source='draft', target='published')
        ...     def publish(self):
        ...         pass
    """

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        kwargs.setdefault("max_length", 50)
        super().__init__(*args, **kwargs)


class FSMIntegerField(FSMFieldMixin, models.IntegerField):
    """
    IntegerField-based state machine field.

    Use this when you want to store states as integers, which is useful
    for enum-style state definitions.

    Example:
        >>> class OrderState:
        ...     PENDING = 1
        ...     PROCESSING = 2
        ...     SHIPPED = 3
        ...     DELIVERED = 4
        ...
        >>> class Order(models.Model):
        ...     state = FSMIntegerField(default=OrderState.PENDING)
        ...
        ...     @transition(field=state, source=OrderState.PENDING,
        ...                 target=OrderState.PROCESSING)
        ...     def process(self):
        ...         pass
    """

    pass


class FSMKeyField(FSMFieldMixin, models.ForeignKey):
    """
    ForeignKey-based state machine field.

    Use this when states are stored in a separate database table,
    providing referential integrity for state values.

    Example:
        >>> class WorkflowState(models.Model):
        ...     id = models.CharField(primary_key=True, max_length=50)
        ...     label = models.CharField(max_length=255)
        ...
        >>> class Document(models.Model):
        ...     state = FSMKeyField(WorkflowState, default='draft',
        ...                         on_delete=models.PROTECT)
        ...
        ...     @transition(field=state, source='draft', target='review')
        ...     def submit_for_review(self):
        ...         pass
    """

    def get_state(self, instance: Model) -> Any:
        """
        Get the state value (foreign key ID) from the instance.

        Args:
            instance: The model instance.

        Returns:
            The foreign key value (typically the PK of the related state).
        """
        return instance.__dict__[self.attname]

    def set_state(self, instance: Model, state: Any) -> None:
        """
        Set the state value on the instance.

        Args:
            instance: The model instance.
            state: The new state value (foreign key ID).
        """
        instance.__dict__[self.attname] = self.to_python(state)


class FSMModelMixin:
    """
    Mixin that enables refresh_from_db for models with protected FSM fields.

    When an FSM field is marked as protected, calling refresh_from_db()
    on the model would normally fail because it tries to set the field
    directly. This mixin overrides refresh_from_db() to skip protected
    FSM fields.

    Example:
        >>> class BlogPost(FSMModelMixin, models.Model):
        ...     state = FSMField(default='draft', protected=True)
        ...     content = models.TextField()
        ...
        >>> post = BlogPost.objects.get(pk=1)
        >>> post.refresh_from_db()  # Works! Skips protected 'state' field
    """

    def _get_protected_fsm_fields(self) -> set[str]:
        """
        Get the set of protected FSM field attribute names.

        Returns:
            Set of attribute names for protected FSM fields.
        """

        def is_fsm_and_protected(f: Field) -> bool:
            return isinstance(f, FSMFieldMixin) and f.protected

        protected_fields = filter(is_fsm_and_protected, self._meta.concrete_fields)  # type: ignore[attr-defined]
        return {f.attname for f in protected_fields}

    def refresh_from_db(self, *args: Any, **kwargs: Any) -> None:
        """
        Reload field values from the database, skipping protected FSM fields.

        Args:
            *args: Positional arguments passed to parent method.
            **kwargs: Keyword arguments. 'fields' is modified to exclude
                protected FSM fields if not explicitly provided.
        """
        fields: list[str] | None = kwargs.pop("fields", None)

        # Use provided fields, if not set then reload all non-deferred fields.
        if not fields:
            deferred_fields = self.get_deferred_fields()  # type: ignore[attr-defined]
            protected_fields = self._get_protected_fsm_fields()
            skipped_fields = deferred_fields.union(protected_fields)

            fields = [
                f.attname
                for f in self._meta.concrete_fields  # type: ignore[attr-defined]
                if f.attname not in skipped_fields
            ]

        kwargs["fields"] = fields
        super().refresh_from_db(*args, **kwargs)  # type: ignore[misc]


class ConcurrentTransitionMixin:
    """
    Mixin providing optimistic locking for FSM state transitions.

    Protects a Model from undesirable effects caused by concurrently executed
    transitions, e.g. running the same transition multiple times simultaneously,
    or running different transitions with the same source state concurrently.

    This behavior uses optimistic locking based on the state field value. No
    additional version field is required; only the state field(s) are used
    for tracking. While not as strict as true optimistic locking, it's more
    lightweight and leverages FSM model specifics.

    Models using this mixin will raise ConcurrentTransition if any FSM field
    has been changed in the database since the object was fetched.

    Important:
        For guaranteed protection against race conditions:
        1. Transitions should not have side effects except database changes
        2. Always call save() within django.db.transaction.atomic()

    Example:
        >>> from django.db import transaction
        >>>
        >>> class Order(ConcurrentTransitionMixin, models.Model):
        ...     state = FSMField(default='pending')
        ...
        ...     @transition(field=state, source='pending', target='processing')
        ...     def process(self):
        ...         pass
        ...
        >>> with transaction.atomic():
        ...     order = Order.objects.get(pk=1)
        ...     order.process()
        ...     order.save()  # Raises ConcurrentTransition if state changed

    Attributes:
        state_fields: Property returning all FSM fields on this model.
    """

    __initial_states: dict[str, StateValue]

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._update_initial_state()

    @property
    def state_fields(self) -> Iterator[FSMFieldMixin]:
        """
        Get all FSM fields defined on this model.

        Returns:
            Iterator of FSMFieldMixin instances.
        """
        return filter(lambda field: isinstance(field, FSMFieldMixin), self._meta.fields)  # type: ignore[attr-defined]

    def _do_update(
        self,
        base_qs: QuerySet[Any],
        using: str | None,
        pk_val: Any,
        values: Any,
        update_fields: Sequence[str] | None,
        forced_update: bool,
        *args: Any,
        **kwargs: Any,
    ) -> int:
        """
        Perform the actual UPDATE with optimistic locking.

        Extends Django's _do_update to filter by initial state values,
        preventing concurrent modifications from succeeding.

        Args:
            base_qs: Base queryset for the update.
            using: Database alias.
            pk_val: Primary key value.
            values: Values to update.
            update_fields: Specific fields to update.
            forced_update: Whether to force UPDATE vs INSERT.
            *args: Additional positional arguments for forward compatibility (e.g., returning_fields in Django 6.0+).
            **kwargs: Additional keyword arguments for forward compatibility.

        Returns:
            Number of rows updated.

        Raises:
            ConcurrentTransition: If state was modified since fetch.
        """
        # _do_update is called once for each model class in the inheritance hierarchy.
        # We can only filter the base_qs on state fields present in this particular model.

        # Select state fields to filter on
        filter_on = filter(lambda field: field.model == base_qs.model, self.state_fields)

        # state filter will be used to narrow down the standard filter checking only PK
        state_filter = {field.attname: self.__initial_states[field.attname] for field in filter_on}

        updated: int = super()._do_update(  # type: ignore[misc]
            base_qs.filter(**state_filter),
            using,
            pk_val,
            values,
            update_fields,
            forced_update,
            *args,
            **kwargs,
        )

        # It may happen that nothing was updated not because of unmatching state,
        # but because of missing PK. This codepath is possible when saving a new
        # model instance with *preset PK*. Django tries UPDATE first and falls back
        # to INSERT if UPDATE fails.
        # We need to only catch the case when object *is* in DB but with changed state.
        if not updated and base_qs.filter(pk=pk_val).using(using).exists():
            raise ConcurrentTransition("Cannot save object! The state has been changed since fetched from the database!")

        return updated

    def _update_initial_state(self) -> None:
        """Store the current state values as initial states for comparison."""
        self.__initial_states = {
            field.attname: field.value_from_object(self)  # type: ignore[arg-type]
            for field in self.state_fields
        }

    def refresh_from_db(self, *args: Any, **kwargs: Any) -> None:
        """Refresh from database and update tracked initial states."""
        super().refresh_from_db(*args, **kwargs)  # type: ignore[misc]
        self._update_initial_state()

    def save(self, *args: Any, **kwargs: Any) -> None:
        """Save the model and update tracked initial states."""
        super().save(*args, **kwargs)  # type: ignore[misc]
        self._update_initial_state()


def transition(
    field: FSMFieldMixin | str,
    source: StateSource = "*",
    target: StateTarget = None,
    on_error: StateValue | None = None,
    conditions: list[ConditionFunc] | None = None,
    permission: PermissionType = None,
    custom: CustomDict | None = None,
    on_success: TransitionCallback | None = None,
) -> Callable[[_F], _F]:
    """
    Decorator to mark a method as a state transition.

    The decorated method will:
    1. Validate the current state matches one of the source states
    2. Check all conditions are met
    3. Execute the method
    4. Change the state to target (if successful)
    5. Send pre/post transition signals
    6. Call on_success callback (if provided)

    Args:
        field: The FSM field to transition on. Can be the field instance
            or its name as a string.
        source: Source state(s) from which this transition is allowed.
            Can be a single state, a list of states, '*' (any state),
            '+' (any state except target), or prefix wildcards like 'WRK-*'.
            Default is '*'.
        target: Target state after transition. Can be a state value,
            RETURN_VALUE (use method return), GET_STATE (compute dynamically),
            or None (no state change, just validation). Default is None.
        on_error: State to transition to if the method raises an exception.
            Default is None (exception propagates, no state change).
        conditions: List of callables that must all return True for the
            transition to proceed. Each callable receives the model instance.
            Default is empty list.
        permission: Permission required for this transition. Can be a
            permission string (e.g., 'app.permission') or a callable
            taking (instance, user) and returning bool. Default is None.
        custom: Dictionary of custom properties accessible on the Transition
            object. Default is empty dict.
        on_success: Callback function invoked after successful transition.
            Receives (instance, source, target, method_args, method_kwargs).
            This is an alternative to using signals for side effects.
            Default is None.

    Returns:
        A decorator that wraps the method with transition logic.

    Example:
        >>> def log_publish(instance, source, target, **kwargs):
        ...     print(f"Published! {source} -> {target}")
        ...
        >>> class BlogPost(models.Model):
        ...     state = FSMField(default='draft')
        ...
        ...     @transition(field=state, source='draft', target='published',
        ...                 conditions=[is_valid], permission='blog.publish',
        ...                 on_success=log_publish)
        ...     def publish(self):
        ...         '''Publish the blog post.'''
        ...         self.published_at = timezone.now()
        ...
        >>> post = BlogPost()
        >>> post.publish()  # state changes from 'draft' to 'published'
    """
    # Use empty list/dict as defaults, not mutable defaults
    if conditions is None:
        conditions = []
    if custom is None:
        custom = {}

    def inner_transition(func: _F) -> _F:
        wrapper_installed, fsm_meta = True, getattr(func, "_django_fsm_rx", None)
        if not fsm_meta:
            wrapper_installed = False
            fsm_meta = FSMMeta(field=field, method=func)
            setattr(func, "_django_fsm_rx", fsm_meta)

        if isinstance(source, (list, tuple, set)):
            for state in source:
                func._django_fsm_rx.add_transition(func, state, target, on_error, conditions, permission, custom, on_success)
        else:
            func._django_fsm_rx.add_transition(func, source, target, on_error, conditions, permission, custom, on_success)

        @wraps(func)
        def _change_state(instance: Model, *args: Any, **kwargs: Any) -> Any:
            return fsm_meta.field.change_state(instance, func, *args, **kwargs)

        if not wrapper_installed:
            return _change_state  # type: ignore[return-value]

        return func

    return inner_transition


def can_proceed(bound_method: Any, check_conditions: bool = True) -> bool:
    """
    Check if a transition method can be called in the current state.

    This function checks:
    1. A transition exists from the current state
    2. All conditions are met (unless check_conditions=False)

    Args:
        bound_method: A bound method decorated with @transition.
        check_conditions: Whether to verify transition conditions.
            Set to False to only check if the transition exists.

    Returns:
        True if the transition can proceed, False otherwise.

    Raises:
        TypeError: If bound_method is not a transition method.

    Example:
        >>> post = BlogPost.objects.get(pk=1)
        >>> if can_proceed(post.publish):
        ...     post.publish()
        ...     post.save()
        >>> # Skip condition checking
        >>> can_proceed(post.publish, check_conditions=False)
    """
    if not hasattr(bound_method, "_django_fsm_rx"):
        raise TypeError(f"{bound_method.__func__.__name__} method is not transition")

    meta: FSMMeta = bound_method._django_fsm_rx
    instance: Model = bound_method.__self__
    current_state = meta.field.get_state(instance)

    return meta.has_transition(current_state) and (not check_conditions or meta.conditions_met(instance, current_state))


def has_transition_perm(bound_method: Any, user: AbstractBaseUser) -> bool:
    """
    Check if user has permission to execute a transition.

    This function checks:
    1. A transition exists from the current state
    2. All conditions are met
    3. User has the required permission

    Args:
        bound_method: A bound method decorated with @transition.
        user: The user to check permissions for.

    Returns:
        True if the user can execute the transition, False otherwise.

    Raises:
        TypeError: If bound_method is not a transition method.

    Example:
        >>> post = BlogPost.objects.get(pk=1)
        >>> if has_transition_perm(post.publish, request.user):
        ...     post.publish()
        ...     post.save()
        ... else:
        ...     raise PermissionDenied("Cannot publish")
    """
    if not hasattr(bound_method, "_django_fsm_rx"):
        raise TypeError(f"{bound_method.__func__.__name__} method is not transition")

    meta: FSMMeta = bound_method._django_fsm_rx
    instance: Model = bound_method.__self__
    current_state = meta.field.get_state(instance)

    return (
        meta.has_transition(current_state)
        and meta.conditions_met(instance, current_state)
        and meta.has_transition_perm(instance, current_state, user)
    )


class State:
    """
    Base class for dynamic state resolution.

    Subclass this to create custom state resolution logic. The get_state
    method is called after the transition method executes to determine
    the actual target state.

    See Also:
        RETURN_VALUE: Use the transition method's return value as state.
        GET_STATE: Use a callable to compute the state.
    """

    def get_state(
        self,
        model: Model,
        transition: Callable[..., Any],
        result: Any,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> StateValue:
        """
        Compute the target state dynamically.

        Args:
            model: The model instance being transitioned.
            transition: The transition method that was called.
            result: The return value of the transition method.
            args: Positional arguments passed to the transition method.
            kwargs: Keyword arguments passed to the transition method.

        Returns:
            The computed target state.

        Raises:
            NotImplementedError: Must be implemented by subclasses.
        """
        raise NotImplementedError


class RETURN_VALUE(State):
    """
    Dynamic state resolution using the transition method's return value.

    When used as a target, the transition method's return value becomes
    the new state. Optionally, you can specify allowed states to validate
    the return value.

    Attributes:
        allowed_states: Tuple of allowed state values, or None for any.

    Example:
        >>> class Order(models.Model):
        ...     state = FSMField(default='pending')
        ...
        ...     @transition(field=state, source='pending',
        ...                 target=RETURN_VALUE('approved', 'rejected'))
        ...     def review(self, approved: bool):
        ...         return 'approved' if approved else 'rejected'
    """

    allowed_states: tuple[StateValue, ...] | None

    def __init__(self, *allowed_states: StateValue) -> None:
        """
        Initialize with optional allowed states.

        Args:
            *allowed_states: Valid state values the method can return.
                If none provided, any return value is accepted.
        """
        self.allowed_states = allowed_states if allowed_states else None

    def get_state(
        self,
        model: Model,
        transition: Callable[..., Any],
        result: Any,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> StateValue:
        """
        Return the transition method's result as the new state.

        Args:
            model: The model instance (unused).
            transition: The transition method (unused).
            result: The return value to use as the new state.
            args: Method arguments (unused).
            kwargs: Method keyword arguments (unused).

        Returns:
            The result value as the new state.

        Raises:
            InvalidResultState: If result not in allowed_states.
        """
        if self.allowed_states is not None:
            if result not in self.allowed_states:
                raise InvalidResultState(f"{result} is not in list of allowed states\n{self.allowed_states}")
        return result


class GET_STATE(State):
    """
    Dynamic state resolution using a callable function.

    When used as a target, a provided function is called after the
    transition method to compute the new state. The function receives
    the model instance and any arguments passed to the transition.

    Attributes:
        func: Callable that computes the target state.
        allowed_states: Tuple of allowed state values, or None for any.

    Example:
        >>> def compute_state(instance, priority):
        ...     return 'urgent' if priority > 5 else 'normal'
        ...
        >>> class Task(models.Model):
        ...     state = FSMField(default='new')
        ...
        ...     @transition(field=state, source='new',
        ...                 target=GET_STATE(compute_state, states=['urgent', 'normal']))
        ...     def assign(self, priority: int):
        ...         pass
    """

    func: Callable[..., StateValue]
    allowed_states: Sequence[StateValue] | None

    def __init__(
        self,
        func: Callable[..., StateValue],
        states: Sequence[StateValue] | None = None,
    ) -> None:
        """
        Initialize with a state computation function.

        Args:
            func: Callable that receives (model, *args, **kwargs) and
                returns the target state.
            states: Optional list of valid states for validation.
        """
        self.func = func
        self.allowed_states = states

    def get_state(
        self,
        model: Model,
        transition: Callable[..., Any],
        result: Any,
        args: tuple[Any, ...] = (),
        kwargs: dict[str, Any] | None = None,
    ) -> StateValue:
        """
        Compute the state using the provided function.

        Args:
            model: The model instance to pass to func.
            transition: The transition method (unused).
            result: The transition's return value (unused).
            args: Arguments to pass to func.
            kwargs: Keyword arguments to pass to func.

        Returns:
            The computed target state.

        Raises:
            InvalidResultState: If computed state not in allowed_states.
        """
        if kwargs is None:
            kwargs = {}
        result_state = self.func(model, *args, **kwargs)
        if self.allowed_states is not None:
            if result_state not in self.allowed_states:
                raise InvalidResultState(f"{result_state} is not in list of allowed states\n{self.allowed_states}")
        return result_state
