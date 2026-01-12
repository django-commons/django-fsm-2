"""
Optional integration with django-fsm-log for transition logging.

This module provides decorators and utilities for logging state transitions.
It is designed to be compatible with django-fsm-log but can also work
standalone with a custom StateLog model.

Usage with django-fsm-log:
    1. Install django-fsm-log: pip install django-fsm-log
    2. Add 'django_fsm_log' to INSTALLED_APPS
    3. Run migrations: python manage.py migrate
    4. Use the decorators on your transitions:

    >>> from django_fsm_rx import FSMField, transition
    >>> from django_fsm_rx.log import fsm_log_by, fsm_log_description
    >>>
    >>> class BlogPost(models.Model):
    ...     state = FSMField(default='draft')
    ...
    ...     @fsm_log_by
    ...     @fsm_log_description
    ...     @transition(field=state, source='draft', target='published')
    ...     def publish(self, by=None, description=None):
    ...         pass
    >>>
    >>> post = BlogPost.objects.create()
    >>> post.publish(by=user, description="Ready for publication")
    >>> post.save()

Standalone usage:
    If you don't want to use django-fsm-log, you can connect to the
    post_transition signal to implement your own logging:

    >>> from django_fsm_rx.signals import post_transition
    >>>
    >>> def log_transition(sender, instance, name, source, target, **kwargs):
    ...     MyCustomLog.objects.create(
    ...         content_object=instance,
    ...         transition=name,
    ...         source_state=source,
    ...         state=target,
    ...         by=kwargs.get('by'),
    ...     )
    >>>
    >>> post_transition.connect(log_transition)
"""

from __future__ import annotations

from collections.abc import Callable
from collections.abc import Generator
from contextlib import contextmanager
from functools import partial
from functools import wraps
from typing import TYPE_CHECKING
from typing import Any
from typing import TypeVar

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser

__all__ = [
    "fsm_log_by",
    "fsm_log_description",
    "FSMLogDescriptor",
]

_F = TypeVar("_F", bound=Callable[..., Any])


class FSMLogDescriptor:
    """
    Context manager for setting transition log attributes.

    This descriptor is used internally by the logging decorators to
    attach metadata (like 'by' user or 'description') to the model
    instance during a transition.

    The attached data can be read by signal handlers (like django-fsm-log)
    to persist the transition metadata.

    Attributes:
        instance: The model instance being transitioned.
        attribute: The attribute name to store ('by', 'description', etc.).
        value: The initial value to set (optional).

    Example:
        >>> with FSMLogDescriptor(instance, 'by', user) as desc:
        ...     # instance._fsm_log_by is now set to user
        ...     do_transition()
        >>> # instance._fsm_log_by is now cleared
    """

    def __init__(
        self,
        instance: Any,
        attribute: str,
        value: Any = None,
    ) -> None:
        self.instance = instance
        self.attribute = f"_fsm_log_{attribute}"
        self._value = value

    def __enter__(self) -> FSMLogDescriptor:
        """Set the attribute value on the instance."""
        if self._value is not None:
            setattr(self.instance, self.attribute, self._value)
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Clear the attribute from the instance."""
        if hasattr(self.instance, self.attribute):
            delattr(self.instance, self.attribute)

    def set(self, value: Any) -> None:
        """
        Set the attribute value.

        Can be called within the context to update the value.

        Args:
            value: The value to set.
        """
        self._value = value
        setattr(self.instance, self.attribute, value)


def fsm_log_by(func: _F) -> _F:
    """
    Decorator to capture the user who triggered a transition.

    When applied to a transition method, this decorator extracts the
    'by' keyword argument and stores it on the instance for logging.

    The stored value is accessible during the transition via
    instance._fsm_log_by and can be used by signal handlers for logging.

    Args:
        func: The transition method to wrap.

    Returns:
        The wrapped function.

    Example:
        >>> @fsm_log_by
        ... @transition(field=state, source='draft', target='published')
        ... def publish(self, by=None):
        ...     pass
        >>>
        >>> post.publish(by=request.user)

    Note:
        The 'by' parameter should be declared in the method signature
        with a default value of None for cases where the user is not provided.
    """

    @wraps(func)
    def wrapped(instance: Any, *args: Any, **kwargs: Any) -> Any:
        by = kwargs.get("by")
        if by is None:
            return func(instance, *args, **kwargs)
        with FSMLogDescriptor(instance, "by", by):
            return func(instance, *args, **kwargs)

    return wrapped  # type: ignore[return-value]


def fsm_log_description(
    func: _F | None = None,
    allow_inline: bool = False,
    description: str | None = None,
) -> _F | Callable[[_F], _F]:
    """
    Decorator to capture a description for the transition.

    This decorator can be used in several ways:

    1. Simple usage - description passed as argument:
        >>> @fsm_log_description
        ... @transition(field=state, source='draft', target='published')
        ... def publish(self, description=None):
        ...     pass
        >>>
        >>> post.publish(description="Approved by editor")

    2. With default description:
        >>> @fsm_log_description(description="Auto-published")
        ... @transition(field=state, source='draft', target='published')
        ... def publish(self):
        ...     pass

    3. With inline setting (set description inside the method):
        >>> @fsm_log_description(allow_inline=True)
        ... @transition(field=state, source='draft', target='published')
        ... def publish(self, description=None):
        ...     description.set(f"Published at {timezone.now()}")

    Args:
        func: The transition method (when used without arguments).
        allow_inline: If True, pass the descriptor to allow setting
            the description inside the method.
        description: Default description if none provided.

    Returns:
        Decorated function or decorator.
    """
    if func is None:
        return partial(
            fsm_log_description,
            allow_inline=allow_inline,
            description=description,
        )

    @wraps(func)
    def wrapped(instance: Any, *args: Any, **kwargs: Any) -> Any:
        with FSMLogDescriptor(instance, "description") as descriptor:
            desc_value = kwargs.get("description")
            if desc_value:
                descriptor.set(desc_value)
            elif allow_inline:
                kwargs["description"] = descriptor
            elif description:
                descriptor.set(description)
            return func(instance, *args, **kwargs)

    return wrapped  # type: ignore[return-value]


@contextmanager
def fsm_log_context(
    instance: Any,
    by: AbstractBaseUser | None = None,
    description: str | None = None,
) -> Generator[None]:
    """
    Context manager for setting log metadata during a transition.

    This provides an alternative to the decorators when you need more
    control over when the metadata is set.

    Args:
        instance: The model instance being transitioned.
        by: The user triggering the transition.
        description: A description of the transition.

    Yields:
        None

    Example:
        >>> with fsm_log_context(post, by=user, description="Bulk publish"):
        ...     post.publish()
        ...     post.save()
    """
    descriptors = []
    try:
        if by is not None:
            desc = FSMLogDescriptor(instance, "by", by)
            desc.__enter__()
            descriptors.append(desc)
        if description is not None:
            desc = FSMLogDescriptor(instance, "description", description)
            desc.__enter__()
            descriptors.append(desc)
        yield
    finally:
        for desc in reversed(descriptors):
            desc.__exit__(None, None, None)
