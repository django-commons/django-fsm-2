from __future__ import annotations

import typing
from warnings import warn

from django.contrib.contenttypes.admin import GenericTabularInline
from django.core import checks

from django_fsm.admin import FSMTransitionInlineMixin

from .models import StateLog

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


class StateLogInline(FSMTransitionInlineMixin, GenericTabularInline):
    model = StateLog

    def __init__(self, parent_model: typing.Any, admin_site: typing.Any) -> None:
        warn(
            "StateLogInline has been deprecated by FSMTransitionInlineMixin.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(parent_model, admin_site)
