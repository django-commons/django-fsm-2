from __future__ import annotations

import typing
from warnings import warn

from django.contrib.contenttypes.admin import GenericTabularInline
from django.db.models import F

from .models import StateLog

if typing.TYPE_CHECKING:
    from django.db.models import QuerySet
    from django.http import HttpRequest

    from .models import TransitionLogBase


class FSMTransitionInline(GenericTabularInline):
    model: type[TransitionLogBase] = None  # type: ignore[assignment]

    can_delete = False

    def has_add_permission(
        self, request: HttpRequest, obj: TransitionLogBase | None = None
    ) -> bool:
        return False

    def has_change_permission(
        self, request: HttpRequest, obj: TransitionLogBase | None = None
    ) -> bool:
        return True

    fields = (
        "transition",
        "source_state",
        "state",
        "by",
        "description",
        "timestamp",
    )

    def get_readonly_fields(
        self, request: HttpRequest, obj: TransitionLogBase | None = None
    ) -> list[str] | tuple[str, ...] | tuple[()]:
        return self.fields

    def get_queryset(self, request: HttpRequest) -> QuerySet[TransitionLogBase]:
        return super().get_queryset(request).order_by(F("timestamp").desc())


class StateLogInline(FSMTransitionInline):
    model = StateLog

    def __init__(self, parent_model: typing.Any, admin_site: typing.Any) -> None:
        warn(
            "StateLogInline has been deprecated by PersistedTransitionInline.",
            DeprecationWarning,
            stacklevel=2,
        )
        super().__init__(parent_model, admin_site)
