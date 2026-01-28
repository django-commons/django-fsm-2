from __future__ import annotations

import contextlib
import typing
from dataclasses import dataclass
from functools import partial
from functools import wraps

from django.contrib.contenttypes.models import ContentType
from django.db import models

from .models import StateLog
from .models import TransitionLogBase
from .signals import post_transition

if typing.TYPE_CHECKING:  # pragma: no cover
    from collections.abc import Callable

    from . import _Field


__all__ = [
    "StateLog",
    "TransitionLogBase",
    "fsm_log_by",
    "fsm_log_description",
    "track",
]


@dataclass(frozen=True)
class TrackConfig:
    log_model: type[TransitionLogBase] | None
    relation_field: str | None


_registry: dict[type[models.Model], TrackConfig] = {}
NOTSET = object()


def track(
    *,
    log_model: type[TransitionLogBase] | None = None,
    relation_field: str | None = None,
) -> Callable[[type[models.Model]], type[models.Model]]:
    def decorator(model_cls: type[models.Model]) -> type[models.Model]:
        if model_cls._meta.abstract:
            raise TypeError("django_fsm.track cannot be used with abstract models")
        config = TrackConfig(log_model=log_model, relation_field=relation_field)
        _registry[model_cls] = config

        post_transition.connect(
            _log_transition,
            sender=model_cls,
            dispatch_uid=f"django_fsm.track.{model_cls._meta.label_lower}",
            weak=False,
        )
        return model_cls

    return decorator


class FSMLogDescriptor:
    ATTR_PREFIX = "__django_fsm_log_attr_"

    def __init__(self, instance: models.Model, attribute: str, value: typing.Any = NOTSET):
        self.instance = instance
        self.attribute = attribute
        if value is not NOTSET:
            self.set(value)

    def get(self) -> typing.Any:
        return getattr(self.instance, self.ATTR_PREFIX + self.attribute)

    def set(self, value: typing.Any) -> None:
        setattr(self.instance, self.ATTR_PREFIX + self.attribute, value)

    def __enter__(self) -> typing.Self:
        return self

    def __exit__(self, *args: object) -> None:
        with contextlib.suppress(AttributeError):
            delattr(self.instance, self.ATTR_PREFIX + self.attribute)


def fsm_log_by(func: typing.Callable[..., typing.Any]) -> typing.Callable[..., typing.Any]:
    @wraps(func)
    def wrapped(instance: models.Model, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        if "by" in kwargs:
            author = kwargs.pop("by")
        else:
            return func(instance, *args, **kwargs)

        with FSMLogDescriptor(instance, "by", author):
            return func(instance, *args, **kwargs)

    return wrapped


def fsm_log_description(
    func: typing.Callable[..., typing.Any] | None = None,
    *,
    description: str | None = None,
) -> typing.Callable[..., typing.Any]:
    if func is None:
        return partial(fsm_log_description, description=description)

    @wraps(func)
    def wrapped(instance: models.Model, *args: typing.Any, **kwargs: typing.Any) -> typing.Any:
        with FSMLogDescriptor(instance, "description") as descriptor:
            if "description" in kwargs:
                descriptor.set(kwargs.pop("description"))
            else:
                descriptor.set(description)
            return func(instance, *args, **kwargs)

    return wrapped


def _log_transition(
    sender: type[models.Model],
    instance: models.Model,
    name: str,
    source: typing.Any,
    target: typing.Any,
    field: _Field,
    **kwargs: typing.Any,
) -> None:
    config = _registry.get(sender)
    if not config or instance.pk is None:
        return

    log_model = config.log_model or StateLog
    log_kwargs: dict[str, typing.Any] = {
        "transition": name,
        "state_field": field.name,
        "source_state": _coerce_state(source),
        "state": _coerce_state(target),
        "by": _extract_log_value(instance, "by"),
        "description": _extract_log_value(instance, "description"),
    }

    if issubclass(log_model, StateLog):
        log_kwargs["content_type"] = ContentType.objects.get_for_model(sender)
        log_kwargs["object_id"] = str(instance.pk)
    else:
        relation_field = config.relation_field or _resolve_relation_field(log_model, sender)
        log_kwargs[relation_field] = instance

    log_model._default_manager.using(instance._state.db).create(**log_kwargs)


def _resolve_relation_field(
    log_model: type[TransitionLogBase], model_cls: type[models.Model]
) -> str:
    relation_fields = [
        field.name
        for field in log_model._meta.fields
        if isinstance(field, models.ForeignKey)
        and _matches_model(field.remote_field.model, model_cls)
    ]
    if len(relation_fields) == 1:
        return relation_fields[0]

    if not relation_fields:
        raise ValueError(
            f"{log_model.__name__} does not define a ForeignKey to {model_cls.__name__}"
        )
    raise ValueError(
        f"{log_model.__name__} has multiple ForeignKey fields to {model_cls.__name__}; "
        "set relation_field when calling track()"
    )


def _coerce_state(value: typing.Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, models.Model):
        return str(value.pk)
    return str(value)


def _matches_model(remote_model: typing.Any, model_cls: type[models.Model]) -> bool:
    if remote_model == model_cls:
        return True
    if isinstance(remote_model, str):
        return remote_model == model_cls.__name__ or remote_model.endswith(f".{model_cls.__name__}")
    return False


def _extract_log_value(
    instance: models.Model,
    attribute: str,
) -> typing.Any:
    try:
        return FSMLogDescriptor(instance, attribute).get()
    except AttributeError:
        return None
