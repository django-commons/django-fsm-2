from __future__ import annotations

import typing
from dataclasses import dataclass

from django.db import models

from . import FSMLogDescriptor
from .models import StateLog
from .models import TransitionLogBase
from .signals import post_transition

if typing.TYPE_CHECKING:  # pragma: no cover
    from . import _Field
    from . import _StateValue
    from . import _TransitionFunc


__all__ = [
    "StateLog",
    "TransitionLogBase",
    "track",
]


@dataclass(frozen=True)
class TrackConfig:
    log_model: type[TransitionLogBase]
    relation_field: str


_registry: dict[type[models.Model], TrackConfig] = {}

NOTSET = object()


def track(
    *,
    log_model: type[TransitionLogBase] | None = None,
    relation_field: str | None = None,
) -> _TransitionFunc:
    def decorator(model_cls: type[models.Model]) -> type[models.Model]:
        if model_cls._meta.abstract:
            raise TypeError("django_fsm.track cannot be used with abstract models")

        _registry[model_cls] = TrackConfig(
            log_model=log_model or StateLog,
            relation_field=relation_field or "content_object",
        )

        post_transition.connect(
            _log_transition,
            sender=model_cls,
            dispatch_uid=f"django_fsm.track.{model_cls._meta.label_lower}",
            weak=False,
        )
        return model_cls

    return decorator


def _log_transition(
    sender: type[models.Model],
    instance: models.Model,
    name: str,
    source: _StateValue,
    target: _StateValue,
    field: _Field,
    **kwargs: typing.Any,
) -> None:
    config = _registry.get(sender)
    if not config or instance.pk is None:
        return

    log_model = config.log_model or StateLog

    log_model._default_manager.using(instance._state.db).create(
        **{
            "transition": name,
            "state_field": field.name,
            "source_state": _coerce_state(source),
            "state": _coerce_state(target),
            "by": _extract_log_value(instance, "by"),
            "description": _extract_log_value(instance, "description"),
            config.relation_field: instance,
        }
    )


def _coerce_state(value: _StateValue | None) -> _StateValue | None:
    if value is None:
        return None
    if isinstance(value, models.Model):
        return str(value.pk)
    return value


def _extract_log_value(instance: models.Model, attribute: str) -> typing.Any:
    return getattr(instance, f"{FSMLogDescriptor.ATTR_PREFIX}{attribute}", None)
