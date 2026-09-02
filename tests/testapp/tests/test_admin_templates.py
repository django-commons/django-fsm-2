from __future__ import annotations

import re
import warnings
from dataclasses import dataclass
from pathlib import Path

from django.conf import settings
from django.template import engines
from django.template.loader import get_template
from django.test import SimpleTestCase
from django.test import override_settings

import django_fsm

# The test project also installs `django_fsm.contrib.unfold`, whose templates
# directory shadows `django_fsm/fsm_transition_button.html` via the normal
# app-directories loader (since it's listed before `django_fsm` in
# `INSTALLED_APPS`). To exercise the *base* (non-unfold) template, we point the
# filesystem loader directly at `django_fsm`'s own templates directory, which
# is checked before the app-directories loader.
_FSM_TEMPLATES_DIR = str(Path(django_fsm.__file__).parent / "templates")
_BASE_TEMPLATE_OVERRIDE = [{**settings.TEMPLATES[0], "DIRS": [_FSM_TEMPLATES_DIR]}]


@dataclass
class FakeTransition:
    name: str
    label: str
    help_text: str | None = None


@override_settings(TEMPLATES=_BASE_TEMPLATE_OVERRIDE)
class TransitionButtonTemplateTestCase(SimpleTestCase):
    """Regression tests for `fsm_transition_button.html` rendering `title="None"`
    when a transition has no configured `help_text` (the common case, since no
    transition sets `custom=dict(help_text=...)` by default)."""

    def render(self, transition: FakeTransition) -> str:
        template = get_template("django_fsm/fsm_transition_button.html")
        return template.render({"transition": transition})

    def test_omits_title_attribute_when_help_text_is_none(self) -> None:
        rendered = self.render(FakeTransition(name="hide", label="Hide", help_text=None))

        assert "title=" not in rendered
        assert "None" not in rendered

    def test_includes_title_attribute_when_help_text_is_set(self) -> None:
        rendered = self.render(
            FakeTransition(name="complex_transition", label="Rename *", help_text="Do it wisely!")
        )

        assert 'title="Do it wisely!"' in rendered


class TransitionFormTemplateContentTestCase(SimpleTestCase):
    """Regression tests for the `{% block content %}` of
    `fsm_admin_transition_form.html`, which has the same "renders the literal
    string None" bug as the button template for its help-text paragraph.

    The full template `{% extends 'admin/change_form.html' %}`, which requires
    a large amount of real Django admin request/response context to render
    end-to-end. Instead, we render the actual `content` block in isolation, by
    extracting it directly out of the real template file.
    """

    def get_content_block_template(self) -> str:
        source = (
            Path(django_fsm.__file__)
            .parent.joinpath("templates", "django_fsm", "fsm_admin_transition_form.html")
            .read_text()
        )
        match = re.search(r"{% block content %}(.*?){% endblock %}", source, re.DOTALL)
        assert match is not None, "Could not find 'content' block in fsm_admin_transition_form.html"
        return "{% load i18n %}" + match.group(1)

    def render(self, transition: FakeTransition) -> str:
        template = engines["django"].from_string(self.get_content_block_template())
        with warnings.catch_warnings():
            # {% csrf_token %} warns without a RequestContext; irrelevant here.
            warnings.simplefilter("ignore")
            return template.render({"transition": transition, "transition_form": None})

    def test_omits_help_text_paragraph_when_none(self) -> None:
        rendered = self.render(FakeTransition(name="hide", label="Hide", help_text=None))

        assert "None" not in rendered
        assert "<p>" not in rendered

    def test_renders_configured_help_text_paragraph(self) -> None:
        rendered = self.render(
            FakeTransition(name="complex_transition", label="Rename *", help_text="Do it wisely!")
        )

        assert "<p>Do it wisely!</p>" in rendered
