"""
Backwards compatibility shim for django-fsm.

This module re-exports all public APIs from django_fsm_rx, allowing existing
projects to continue using `from django_fsm import ...` imports.

For new projects, we recommend using `from django_fsm_rx import ...` directly.

Example:
    # Both of these work:
    from django_fsm import FSMField, transition  # backwards compatible
    from django_fsm_rx import FSMField, transition  # recommended for new code
"""

from __future__ import annotations

import warnings

from django_fsm_rx import *  # noqa: F401, F403
from django_fsm_rx import __all__ as __all__  # noqa: PLC0414

warnings.warn(
    "Importing from 'django_fsm' is deprecated. Please update your imports to use 'django_fsm_rx' instead.",
    DeprecationWarning,
    stacklevel=2,
)
