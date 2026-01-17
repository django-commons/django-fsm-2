"""
Tests for FSMCascadeWidget.

Tests the cascading dropdown widget for hierarchical status codes.
"""

import json

import pytest
from django.test import RequestFactory

from django_fsm_rx.widgets import FSMCascadeWidget


class TestFSMCascadeWidget:
    """Tests for FSMCascadeWidget."""

    @pytest.fixture
    def sample_choices(self):
        """Sample hierarchical status choices (3 levels)."""
        return [
            ("DRF-NEW-CRT", "Draft - New - Created"),
            ("DRF-NEW-EDT", "Draft - New - Edited"),
            ("DRF-REV-PND", "Draft - Review - Pending"),
            ("WRK-REP-PRG", "Work - Repair - In Progress"),
            ("WRK-REP-HLD", "Work - Repair - On Hold"),
            ("WRK-INS-PRG", "Work - Inspection - In Progress"),
            ("CMP-STD-DON", "Complete - Standard - Done"),
            ("CMP-STD-INV", "Complete - Standard - Invoiced"),
        ]

    @pytest.fixture
    def two_level_choices(self):
        """Sample hierarchical status choices (2 levels)."""
        return [
            ("PEN-NEW", "Pending - New"),
            ("PEN-REV", "Pending - Review"),
            ("ACT-PRG", "Active - Progress"),
            ("ACT-HLD", "Active - Hold"),
            ("DON-CMP", "Done - Complete"),
        ]

    def test_init_defaults(self):
        """Test widget initialization with defaults."""
        widget = FSMCascadeWidget()
        assert widget.levels == 2
        assert widget.separator == "-"
        assert widget.labels == ["Level 1", "Level 2"]
        assert widget.choices == []
        assert widget.allowed_targets is None

    def test_init_custom(self, sample_choices):
        """Test widget initialization with custom settings."""
        widget = FSMCascadeWidget(
            levels=3,
            separator="-",
            labels=["Category", "Subcategory", "Status"],
            choices=sample_choices,
        )
        assert widget.levels == 3
        assert widget.separator == "-"
        assert widget.labels == ["Category", "Subcategory", "Status"]
        assert widget.choices == sample_choices

    def test_parse_hierarchy_three_levels(self, sample_choices):
        """Test parsing choices into hierarchy (3 levels)."""
        widget = FSMCascadeWidget(levels=3, choices=sample_choices)
        hierarchy = widget._parse_hierarchy()

        # Check top level keys
        assert "DRF" in hierarchy
        assert "WRK" in hierarchy
        assert "CMP" in hierarchy

        # Check second level
        assert "NEW" in hierarchy["DRF"]
        assert "REV" in hierarchy["DRF"]
        assert "REP" in hierarchy["WRK"]
        assert "INS" in hierarchy["WRK"]

        # Check third level with values
        assert hierarchy["DRF"]["NEW"]["CRT"]["__value__"] == "DRF-NEW-CRT"
        assert hierarchy["DRF"]["NEW"]["EDT"]["__value__"] == "DRF-NEW-EDT"
        assert hierarchy["WRK"]["REP"]["PRG"]["__value__"] == "WRK-REP-PRG"

    def test_parse_hierarchy_two_levels(self, two_level_choices):
        """Test parsing choices into hierarchy (2 levels)."""
        widget = FSMCascadeWidget(levels=2, choices=two_level_choices)
        hierarchy = widget._parse_hierarchy()

        assert "PEN" in hierarchy
        assert "ACT" in hierarchy
        assert "DON" in hierarchy

        assert hierarchy["PEN"]["NEW"]["__value__"] == "PEN-NEW"
        assert hierarchy["ACT"]["PRG"]["__value__"] == "ACT-PRG"

    def test_parse_hierarchy_with_allowed_targets(self, sample_choices):
        """Test filtering hierarchy by allowed targets."""
        widget = FSMCascadeWidget(
            levels=3,
            choices=sample_choices,
            allowed_targets=["WRK-REP-PRG", "WRK-REP-HLD", "CMP-STD-DON"],
        )
        hierarchy = widget._parse_hierarchy()

        # DRF should not be present (no allowed targets)
        assert "DRF" not in hierarchy

        # WRK should have only REP (not INS)
        assert "WRK" in hierarchy
        assert "REP" in hierarchy["WRK"]
        assert "INS" not in hierarchy["WRK"]

        # CMP should be present
        assert "CMP" in hierarchy

    def test_get_level_choices(self, sample_choices):
        """Test getting choices for each level."""
        widget = FSMCascadeWidget(levels=3, choices=sample_choices)
        hierarchy = widget._parse_hierarchy()

        # Level 0 choices (top level)
        level0 = widget._get_level_choices(hierarchy, 0, [])
        assert ("CMP", "CMP") in level0 or any(c[0] == "CMP" for c in level0)
        assert ("DRF", "DRF") in level0 or any(c[0] == "DRF" for c in level0)
        assert ("WRK", "WRK") in level0 or any(c[0] == "WRK" for c in level0)

        # Level 1 choices for DRF
        level1_drf = widget._get_level_choices(hierarchy, 1, ["DRF"])
        level1_codes = [c[0] for c in level1_drf]
        assert "NEW" in level1_codes
        assert "REV" in level1_codes

        # Level 2 choices for DRF-NEW
        level2_drf_new = widget._get_level_choices(hierarchy, 2, ["DRF", "NEW"])
        level2_codes = [c[0] for c in level2_drf_new]
        assert "CRT" in level2_codes
        assert "EDT" in level2_codes

    def test_get_context(self, sample_choices):
        """Test template context generation."""
        widget = FSMCascadeWidget(
            levels=3,
            separator="-",
            labels=["Category", "Subcategory", "Status"],
            choices=sample_choices,
        )

        context = widget.get_context("status", "WRK-REP-PRG", {})

        assert context["widget"]["levels"] == 3
        assert context["widget"]["separator"] == "-"
        assert context["widget"]["current_value"] == "WRK-REP-PRG"
        assert context["widget"]["hidden_name"] == "status"

        # Check level data
        level_data = context["widget"]["level_data"]
        assert len(level_data) == 3

        # Level 0 should have WRK selected
        assert level_data[0]["selected"] == "WRK"
        assert level_data[0]["label"] == "Category"

        # Level 1 should have REP selected
        assert level_data[1]["selected"] == "REP"
        assert level_data[1]["label"] == "Subcategory"

        # Level 2 should have PRG selected
        assert level_data[2]["selected"] == "PRG"
        assert level_data[2]["label"] == "Status"

        # Check hierarchy JSON is valid
        hierarchy = json.loads(context["widget"]["hierarchy_json"])
        assert "WRK" in hierarchy

    def test_get_context_empty_value(self, sample_choices):
        """Test context with no current value."""
        widget = FSMCascadeWidget(levels=3, choices=sample_choices)
        context = widget.get_context("status", None, {})

        assert context["widget"]["current_value"] == ""
        level_data = context["widget"]["level_data"]

        # All levels should have empty selection
        for level in level_data:
            assert level["selected"] == ""

    def test_value_from_datadict_hidden_field(self):
        """Test extracting value from hidden field."""
        widget = FSMCascadeWidget(levels=3)

        data = {"status": "WRK-REP-PRG"}
        value = widget.value_from_datadict(data, {}, "status")

        assert value == "WRK-REP-PRG"

    def test_value_from_datadict_level_fields(self):
        """Test extracting value from level fields."""
        widget = FSMCascadeWidget(levels=3)

        data = {
            "status_level_0": "WRK",
            "status_level_1": "REP",
            "status_level_2": "PRG",
        }
        value = widget.value_from_datadict(data, {}, "status")

        assert value == "WRK-REP-PRG"

    def test_value_from_datadict_partial_levels(self):
        """Test extracting value when not all levels selected."""
        widget = FSMCascadeWidget(levels=3)

        data = {
            "status_level_0": "WRK",
            "status_level_1": "REP",
            "status_level_2": "",
        }
        value = widget.value_from_datadict(data, {}, "status")

        # Should only include non-empty parts
        assert value == "WRK-REP"

    def test_value_from_datadict_no_data(self):
        """Test extracting value when no data provided."""
        widget = FSMCascadeWidget(levels=3)

        value = widget.value_from_datadict({}, {}, "status")

        assert value is None

    def test_media_class(self):
        """Test that Media class includes required assets."""
        widget = FSMCascadeWidget()
        media = widget.media

        # Check JS
        assert any("cascade_widget.js" in str(js) for js in media._js)

        # Check CSS
        css_all = media._css.get("all", [])
        assert any("cascade_widget.css" in str(css) for css in css_all)

    def test_custom_separator(self):
        """Test widget with custom separator."""
        choices = [
            ("CAT/SUB/STA", "Category / Subcategory / Status"),
            ("CAT/SUB/OTH", "Category / Subcategory / Other"),
        ]
        widget = FSMCascadeWidget(levels=3, separator="/", choices=choices)
        hierarchy = widget._parse_hierarchy()

        assert "CAT" in hierarchy
        assert "SUB" in hierarchy["CAT"]
        assert "STA" in hierarchy["CAT"]["SUB"]
        assert hierarchy["CAT"]["SUB"]["STA"]["__value__"] == "CAT/SUB/STA"

    def test_single_level(self):
        """Test widget with single level (no hierarchy)."""
        choices = [
            ("ACTIVE", "Active"),
            ("INACTIVE", "Inactive"),
            ("PENDING", "Pending"),
        ]
        widget = FSMCascadeWidget(levels=1, choices=choices)
        hierarchy = widget._parse_hierarchy()

        # Each status should be at top level
        assert "ACTIVE" in hierarchy
        assert "INACTIVE" in hierarchy
        assert "PENDING" in hierarchy
        assert hierarchy["ACTIVE"]["__value__"] == "ACTIVE"


class TestFSMCascadeWidgetIntegration:
    """Integration tests for FSMCascadeWidget with Django forms."""

    @pytest.fixture
    def sample_choices(self):
        """Sample choices for testing."""
        return [
            ("DRF-NEW-CRT", "Draft - New - Created"),
            ("WRK-REP-PRG", "Work - Repair - In Progress"),
            ("CMP-STD-DON", "Complete - Standard - Done"),
        ]

    def test_widget_in_form(self, sample_choices):
        """Test widget works in a Django form."""
        from django import forms

        class TestForm(forms.Form):
            status = forms.CharField(
                widget=FSMCascadeWidget(
                    levels=3,
                    separator="-",
                    labels=["Category", "Type", "Status"],
                    choices=sample_choices,
                )
            )

        # Test form with initial value
        form = TestForm(initial={"status": "WRK-REP-PRG"})
        html = form.as_p()

        assert 'class="fsm-cascade-widget"' in html
        assert 'data-levels="3"' in html
        assert 'data-separator="-"' in html

    def test_form_submission(self, sample_choices):
        """Test form submission with widget."""
        from django import forms

        class TestForm(forms.Form):
            status = forms.CharField(
                widget=FSMCascadeWidget(
                    levels=3,
                    separator="-",
                    choices=sample_choices,
                )
            )

        # Simulate form submission from hidden field
        form = TestForm(data={"status": "CMP-STD-DON"})
        assert form.is_valid()
        assert form.cleaned_data["status"] == "CMP-STD-DON"

    def test_form_submission_from_levels(self, sample_choices):
        """Test form submission from individual level fields."""
        from django import forms

        class TestForm(forms.Form):
            status = forms.CharField(
                widget=FSMCascadeWidget(
                    levels=3,
                    separator="-",
                    choices=sample_choices,
                )
            )

        # Simulate submission from level dropdowns
        form = TestForm(
            data={
                "status_level_0": "DRF",
                "status_level_1": "NEW",
                "status_level_2": "CRT",
            }
        )
        assert form.is_valid()
        assert form.cleaned_data["status"] == "DRF-NEW-CRT"
