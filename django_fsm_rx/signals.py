"""
Django signals for FSM state transitions.

This module provides two signals that are sent during state transitions:
- pre_transition: Sent before a transition is executed
- post_transition: Sent after a transition completes (success or failure)

Signal Handlers:
    Both signals send the following keyword arguments to connected handlers:

    sender: type[Model]
        The model class of the transitioning instance.

    instance: Model
        The model instance being transitioned.

    name: str
        The name of the transition method being called.

    field: FSMFieldMixin
        The FSM field being transitioned.

    source: str | int
        The state value before the transition.

    target: str | int | None
        The target state value (may be None for validation-only transitions,
        or dynamically resolved for RETURN_VALUE/GET_STATE).

    method_args: tuple
        Positional arguments passed to the transition method.

    method_kwargs: dict
        Keyword arguments passed to the transition method.

    exception: Exception (post_transition only, optional)
        If the transition raised an exception and on_error is defined,
        this contains the exception that was raised.

Example:
    >>> from django.dispatch import receiver
    >>> from django_fsm_rx.signals import pre_transition, post_transition
    >>>
    >>> @receiver(pre_transition)
    ... def log_transition_start(sender, instance, name, source, target, **kwargs):
    ...     print(f"Starting {name}: {source} -> {target}")
    ...
    >>> @receiver(post_transition)
    ... def log_transition_end(sender, instance, name, source, target, **kwargs):
    ...     if 'exception' in kwargs:
    ...         print(f"Transition {name} failed: {kwargs['exception']}")
    ...     else:
    ...         print(f"Completed {name}: {source} -> {target}")
"""

from __future__ import annotations

from django.dispatch import Signal

# Signal sent before a transition is executed
pre_transition: Signal = Signal()

# Signal sent after a transition completes (or fails with on_error defined)
post_transition: Signal = Signal()
