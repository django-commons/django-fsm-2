from __future__ import annotations

import warnings

from django_fsm.admin import FSMTransitionMixin

__all__ = ["FSMTransitionMixin"]

warnings.warn(
    "Importing from 'fsm_admin.mixins' is deprecated. Please update your imports to use 'django_fsm.admin' instead.",  # noqa: E501
    DeprecationWarning,
    stacklevel=2,
)
