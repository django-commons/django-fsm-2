from __future__ import annotations

import typing

try:
    from typing import override
except ImportError:  # pragma: no cover
    # Py<3.12
    from typing_extensions import override

if typing.TYPE_CHECKING:  # pragma: no cover
    from . import _Condition
    from . import _FSMModel
    from . import _TransitionFunc


class FSMException(Exception):  # noqa: N818
    ...


class TransitionNotAllowed(FSMException):
    """Raised when a transition is not allowed"""


class NoTransition(TransitionNotAllowed):
    """Raised when no transition exists for the current state"""


class InvalidTransition(TransitionNotAllowed):
    """Raised when a transition method is not valid for the current state"""

    object: _FSMModel
    method: _TransitionFunc

    @override
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.object = kwargs.pop("object", None)
        self.method = kwargs.pop("method", None)
        super().__init__(*args, **kwargs)


class TransitionConditionsUnmet(InvalidTransition):
    """Raised when a transition condition fails"""

    failed_condition: _Condition

    @override
    def __init__(self, *args: typing.Any, **kwargs: typing.Any) -> None:
        self.failed_condition = kwargs.pop("failed_condition", None)
        super().__init__(*args, **kwargs)


class InvalidResultState(FSMException):
    """Raised when we got invalid result state"""


class ConcurrentTransition(FSMException):
    """
    Raised when the transition cannot be executed because the
    object has become stale (state has been changed since it
    was fetched from the database).
    """
