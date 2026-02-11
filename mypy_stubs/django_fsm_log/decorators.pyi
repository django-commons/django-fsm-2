from collections.abc import Callable
from typing import ParamSpec
from typing import TypeVar

_P = ParamSpec("_P")
_R = TypeVar("_R")

def fsm_log_by(func: Callable[_P, _R]) -> Callable[_P, _R]: ...
def fsm_log_description(func: Callable[_P, _R]) -> Callable[_P, _R]: ...
