from __future__ import annotations

import typing

from django.core import checks

from django_fsm.admin import FSMAdminMixin as FSMTransitionMixin

__all__ = ["FSMTransitionMixin"]


@checks.register(checks.Tags.compatibility)
def check_deprecated_mixin_import(
    app_configs: typing.Any, **kwargs: typing.Any
) -> list[checks.CheckMessage]:
    """
    Check to warn users that they are still using the legacy import path.
    """
    return [
        checks.Warning(
            "'fsm_admin.mixins' is deprecated, Update your imports:",
            hint="Replace 'from fsm_admin.mixins import FSMTransitionMixin' "
            "with 'from django_fsm.admin import FSMAdminMixin'.",
            id="django_fsm.admin.W001",
        )
    ]
