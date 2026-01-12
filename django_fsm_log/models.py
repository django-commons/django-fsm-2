from __future__ import annotations

import typing

from django.core import checks

from django_fsm.models import StateLog

__all__ = ["StateLog"]


@checks.register(checks.Tags.compatibility)
def check_deprecated_mixin_import(
    app_configs: typing.Any, **kwargs: typing.Any
) -> list[checks.CheckMessage]:
    """
    Check to warn users that they are still using the legacy import path.
    """
    return [
        checks.Warning(
            "'django_fsm_log.models' is deprecated, Update your imports:",
            hint="Replace 'from django_fsm_log.models import StateLog' "
            "with 'from django_fsm.models import StateLog'.",
            id="django_fsm.log.W001",
        )
    ]
