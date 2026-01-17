"""
Integration utilities for django-rules permission library.

This module provides adapters to use django-rules predicates as FSM
transition permissions.

Example:
    >>> from django_fsm_rx import FSMField, transition
    >>> from django_fsm_rx.contrib.rules import rules_permission
    >>>
    >>> class BlogPost(models.Model):
    ...     state = FSMField(default='draft')
    ...
    ...     @transition(
    ...         field=state,
    ...         source='draft',
    ...         target='published',
    ...         permission=rules_permission('blog.publish_post')
    ...     )
    ...     def publish(self):
    ...         pass

Requires:
    pip install rules
    # or
    pip install django-rules
"""

from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING
from typing import Any

if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractBaseUser
    from django.db.models import Model


def rules_permission(rule_name: str) -> Callable[[Any, AbstractBaseUser], bool]:
    """
    Create an FSM permission checker from a django-rules rule name.

    This adapter allows you to use django-rules predicates as FSM transition
    permissions. The rule will be tested with the model instance as the object.

    Args:
        rule_name: The name of the rule to test (e.g., 'app.permission_name').
            This should match a rule registered with django-rules via
            `rules.add_perm()` or `rules.add_rule()`.

    Returns:
        A callable suitable for use as an FSM transition permission.
        The callable takes (instance, user) and returns True if the user
        has permission according to the django-rules rule.

    Example:
        >>> import rules
        >>> from django_fsm_rx.contrib.rules import rules_permission
        >>>
        >>> # Define a predicate
        >>> @rules.predicate
        >>> def is_author(user, post):
        ...     return post.author == user
        >>>
        >>> # Register the rule
        >>> rules.add_perm('blog.publish_post', is_author)
        >>>
        >>> # Use in FSM transition
        >>> @transition(
        ...     field=state,
        ...     source='draft',
        ...     target='published',
        ...     permission=rules_permission('blog.publish_post')
        ... )
        >>> def publish(self):
        ...     pass

    Note:
        The django-rules library must be installed for this to work.
        If rules is not installed, a helpful ImportError will be raised
        when the permission is checked.
    """

    def check_permission(instance: Model, user: AbstractBaseUser) -> bool:
        """Check if user has permission according to django-rules."""
        try:
            import rules
        except ImportError as e:
            raise ImportError("django-rules is required for rules_permission(). Install it with: pip install rules") from e

        return rules.test_rule(rule_name, user, instance)

    # Preserve the rule name for debugging/introspection
    check_permission.__name__ = f"rules_permission({rule_name!r})"
    check_permission.__doc__ = f"Check django-rules permission: {rule_name}"

    return check_permission


def rules_predicate(predicate: Callable[..., bool]) -> Callable[[Any, AbstractBaseUser], bool]:
    """
    Wrap a django-rules predicate for direct use as an FSM permission.

    This is useful when you want to use a predicate directly without
    registering it as a named rule.

    Args:
        predicate: A django-rules predicate function. Should accept
            (user, obj) and return a boolean.

    Returns:
        A callable suitable for use as an FSM transition permission.
        The arguments are swapped to match FSM's (instance, user) signature.

    Example:
        >>> import rules
        >>> from django_fsm_rx.contrib.rules import rules_predicate
        >>>
        >>> @rules.predicate
        >>> def is_manager(user, obj):
        ...     return user.role == 'manager'
        >>>
        >>> @transition(
        ...     field=state,
        ...     source='review',
        ...     target='approved',
        ...     permission=rules_predicate(is_manager)
        ... )
        >>> def approve(self):
        ...     pass
    """

    def check_permission(instance: Model, user: AbstractBaseUser) -> bool:
        """Check if user passes the predicate."""
        # django-rules predicates take (user, obj), FSM takes (instance, user)
        return bool(predicate(user, instance))

    # Preserve predicate info for debugging
    check_permission.__name__ = f"rules_predicate({getattr(predicate, '__name__', repr(predicate))})"
    check_permission.__doc__ = getattr(predicate, "__doc__", None)

    return check_permission


__all__ = ["rules_permission", "rules_predicate"]
