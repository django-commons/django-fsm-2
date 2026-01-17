"""
Custom form widgets for django-fsm-rx.

This module provides widgets for FSM fields, including a cascading
dropdown widget for hierarchical status codes.
"""

from __future__ import annotations

import json
from typing import Any

from django import forms

__all__ = [
    "FSMCascadeWidget",
]


class FSMCascadeWidget(forms.Widget):
    """
    A cascading dropdown widget for hierarchical FSM status codes.

    This widget renders N dropdowns for status codes that follow a
    hierarchical pattern (e.g., AAA-BBB-CCC). Each dropdown filters
    the next based on the selected value.

    Attributes:
        levels: Number of hierarchy levels (default: 2)
        separator: Character separating levels (default: "-")
        labels: Optional list of labels for each dropdown
        choices: List of (value, label) tuples for all statuses
        allowed_targets: Optional list of allowed target states (for FSM integration)

    Example:
        >>> widget = FSMCascadeWidget(
        ...     levels=3,
        ...     separator="-",
        ...     labels=["Category", "Subcategory", "Status"],
        ...     choices=Job.STATUS_CHOICES,
        ... )

    Usage in ModelAdmin:
        >>> class JobAdmin(FSMAdminMixin, ModelAdmin):
        ...     def formfield_for_dbfield(self, db_field, request, **kwargs):
        ...         if db_field.name == "status":
        ...             kwargs["widget"] = FSMCascadeWidget(
        ...                 levels=3,
        ...                 separator="-",
        ...                 labels=["Category", "Subcategory", "Status"],
        ...                 choices=Job.STATUS_CHOICES,
        ...             )
        ...         return super().formfield_for_dbfield(db_field, request, **kwargs)
    """

    template_name = "django_fsm_rx/widgets/cascade_select.html"

    def __init__(
        self,
        levels: int = 2,
        separator: str = "-",
        labels: list[str] | None = None,
        choices: list[tuple[str, str]] | None = None,
        allowed_targets: list[str] | None = None,
        attrs: dict[str, Any] | None = None,
    ):
        """
        Initialize the cascade widget.

        Args:
            levels: Number of dropdown levels
            separator: Character separating hierarchy levels in status codes
            labels: Optional labels for each dropdown (defaults to "Level 1", "Level 2", etc.)
            choices: List of (value, label) tuples for all possible statuses
            allowed_targets: Optional list of allowed target states (filters choices)
            attrs: Additional HTML attributes for the widget container
        """
        super().__init__(attrs)
        self.levels = levels
        self.separator = separator
        self.labels = labels or [f"Level {i + 1}" for i in range(levels)]
        self.choices = choices or []
        self.allowed_targets = allowed_targets

    def _parse_hierarchy(self) -> dict[str, Any]:
        """
        Parse choices into a hierarchical structure.

        Returns:
            Nested dict structure for cascading dropdowns.
            Example for AAA-BBB-CCC format:
            {
                "DRF": {
                    "__label__": "Draft",
                    "NEW": {
                        "__label__": "New",
                        "CRT": {"__label__": "Created", "__value__": "DRF-NEW-CRT"},
                    }
                }
            }
        """
        hierarchy: dict[str, Any] = {}

        for value, label in self.choices:
            # Filter by allowed targets if specified
            if self.allowed_targets is not None and value not in self.allowed_targets:
                continue

            parts = value.split(self.separator)

            # Ensure we have enough parts
            if len(parts) < self.levels:
                # Pad with empty strings if needed
                parts.extend([""] * (self.levels - len(parts)))

            # Build nested structure
            current = hierarchy
            for i, part in enumerate(parts[: self.levels]):
                if part not in current:
                    current[part] = {}
                if i == self.levels - 1:
                    # Last level - store the full value and label
                    current[part]["__value__"] = value
                    current[part]["__label__"] = label
                else:
                    # Extract label for this level from the full label if possible
                    # This is a heuristic - uses the part code as fallback
                    if "__label__" not in current[part]:
                        current[part]["__label__"] = part
                current = current[part]

        return hierarchy

    def _get_level_choices(self, hierarchy: dict[str, Any], level: int, prefix: list[str]) -> list[tuple[str, str]]:
        """
        Get choices for a specific level given parent selections.

        Args:
            hierarchy: The parsed hierarchy dict
            level: Which level to get choices for (0-indexed)
            prefix: List of selected values for previous levels

        Returns:
            List of (value, label) tuples for this level
        """
        current = hierarchy

        # Navigate to the correct level
        for p in prefix:
            if p in current:
                current = current[p]
            else:
                return []

        # Get choices at this level (excluding __label__ and __value__ keys)
        choices = []
        for key, val in current.items():
            if key.startswith("__"):
                continue
            label = val.get("__label__", key) if isinstance(val, dict) else key
            choices.append((key, label))

        return sorted(choices, key=lambda x: x[1])

    def get_context(self, name: str, value: Any, attrs: dict[str, Any] | None) -> dict[str, Any]:
        """
        Build the template context for rendering.

        Args:
            name: The form field name
            value: The current field value
            attrs: Additional HTML attributes

        Returns:
            Context dict for the template
        """
        context = super().get_context(name, value, attrs)

        # Parse current value into parts
        current_parts = []
        if value:
            current_parts = str(value).split(self.separator)
            # Pad if needed
            while len(current_parts) < self.levels:
                current_parts.append("")

        # Build hierarchy data for JavaScript
        hierarchy = self._parse_hierarchy()

        # Get initial choices for each level
        level_data = []
        for i in range(self.levels):
            prefix = current_parts[:i] if i > 0 else []
            choices = self._get_level_choices(hierarchy, i, prefix)
            selected = current_parts[i] if i < len(current_parts) else ""

            level_data.append(
                {
                    "index": i,
                    "label": self.labels[i] if i < len(self.labels) else f"Level {i + 1}",
                    "choices": choices,
                    "selected": selected,
                    "field_name": f"{name}_level_{i}",
                }
            )

        context["widget"].update(
            {
                "levels": self.levels,
                "separator": self.separator,
                "labels": self.labels,
                "level_data": level_data,
                "hierarchy_json": json.dumps(hierarchy),
                "hidden_name": name,
                "current_value": value or "",
            }
        )

        return context

    def value_from_datadict(self, data: dict, files: dict, name: str) -> str | None:
        """
        Extract the combined value from submitted form data.

        Args:
            data: The submitted form data
            files: The submitted files
            name: The form field name

        Returns:
            The combined status value (e.g., "DRF-NEW-CRT")
        """
        # Try to get from hidden field first
        if name in data:
            return data[name]

        # Otherwise, combine from level fields
        parts = []
        for i in range(self.levels):
            level_name = f"{name}_level_{i}"
            part = data.get(level_name, "")
            if part:
                parts.append(part)

        if parts:
            return self.separator.join(parts)

        return None

    class Media:
        js = ("django_fsm_rx/js/cascade_widget.js",)
        css = {"all": ("django_fsm_rx/css/cascade_widget.css",)}


class FSMCascadeSelectWidget(FSMCascadeWidget):
    """
    Alias for FSMCascadeWidget for backwards compatibility.
    """

    pass
