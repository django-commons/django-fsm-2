from __future__ import annotations

import typing
from warnings import warn

from django.core import checks


@checks.register(checks.Tags.compatibility)
def check_deprecated_mixin_import(
    app_configs: typing.Any, **kwargs: typing.Any
) -> list[checks.CheckMessage]:
    """
    Check to warn users that they are still using the legacy import path.
    """
    return [
        checks.Warning(
            "'django_fsm_log.decorators' is deprecated.",
            hint="'fsm_log_by' and 'fsm_log_description' are not required anymore",
            id="django_fsm.log.W003",
        )
    ]


def fsm_log_by(value: typing.Any = None) -> typing.Callable[[typing.Any], typing.Any]:
    warn(
        "fsm_log_by is not required anymore.",
        DeprecationWarning,
        stacklevel=2,
    )

    if callable(value):
        return value  # type: ignore[no-any-return]

    def decorator(func: typing.Any) -> typing.Any:
        return func

    return decorator


def fsm_log_description(value: typing.Any = None) -> typing.Callable[[typing.Any], typing.Any]:
    warn(
        "fsm_log_description is not required anymore.",
        DeprecationWarning,
        stacklevel=2,
    )
    if callable(value):
        return value  # type: ignore[no-any-return]

    def decorator(func: typing.Any) -> typing.Any:
        return func

    return decorator
