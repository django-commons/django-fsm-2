from __future__ import annotations

import typing

from django.core import checks

from django_fsm.admin import StateLogInline

__all__ = ["StateLogInline"]


@checks.register(checks.Tags.compatibility)
def check_deprecated_mixin_import(
    app_configs: typing.Any, **kwargs: typing.Any
) -> list[checks.CheckMessage]:
    """
    Check to warn users that they are still using the legacy import path.
    """
    return [
        checks.Warning(
            "'django_fsm_log.admin' is deprecated, Update your imports:",
            hint="Replace 'from django_fsm_log.admin import StateLogInline' "
            "with 'from django_fsm.admin import StateLogInline'.",
            id="django_fsm.log.W002",
        )
    ]
