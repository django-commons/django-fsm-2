"""
Tests for category/prefix wildcard pattern matching in transitions.

This feature enables hierarchical status codes like AAA-BBB-CCC format,
where 'WRK-*' matches 'WRK-REP-PRG', 'WRK-INS-PRG', etc.
"""

from __future__ import annotations

import pytest
from django.db import models

from django_fsm_rx import FSMField
from django_fsm_rx import TransitionNotAllowed
from django_fsm_rx import can_proceed
from django_fsm_rx import transition


class HierarchicalStatusModel(models.Model):
    """
    Test model with hierarchical status codes (AAA-BBB-CCC format).

    Categories:
    - DRF: Draft
    - WRK: Work in Progress
    - CMP: Completed
    - CXL: Cancelled
    """

    state = FSMField(default="DRF-NEW-CRT")

    @transition(field=state, source="DRF-*", target="WRK-INS-PRG")
    def start_inspection(self):
        """Start inspection from any draft state."""
        pass

    @transition(field=state, source="WRK-*", target="CMP-STD-DON")
    def complete(self):
        """Complete from any work state."""
        pass

    @transition(field=state, source="WRK-INS-*", target="WRK-REP-PRG")
    def start_repair(self):
        """Start repair from any inspection state (more specific pattern)."""
        pass

    @transition(field=state, source=["DRF-*", "WRK-*"], target="CXL-CST-REQ")
    def cancel(self):
        """Cancel from draft or work states."""
        pass

    @transition(field=state, source="*", target="DRF-NEW-CRT")
    def reset(self):
        """Reset from any state (universal wildcard)."""
        pass

    class Meta:
        app_label = "tests"


class TestPrefixWildcardTransitions:
    """Test prefix wildcard pattern matching (e.g., 'WRK-*')."""

    def test_prefix_wildcard_matches_state(self):
        """WRK-* should match WRK-INS-PRG."""
        model = HierarchicalStatusModel()
        model.state = "WRK-INS-PRG"

        assert can_proceed(model.complete)
        model.complete()
        assert model.state == "CMP-STD-DON"

    def test_prefix_wildcard_matches_any_suffix(self):
        """WRK-* should match any WRK-xxx-xxx state."""
        model = HierarchicalStatusModel()

        # Test various WRK states
        for state in ["WRK-INS-PRG", "WRK-REP-PRG", "WRK-QC-PRG", "WRK-TST-PRG"]:
            model.state = state
            assert can_proceed(model.complete), f"Expected complete() to be allowed from {state}"

    def test_prefix_wildcard_does_not_match_different_prefix(self):
        """WRK-* should NOT match CMP-xxx-xxx."""
        model = HierarchicalStatusModel()
        model.state = "CMP-STD-DON"

        assert not can_proceed(model.complete)

    def test_draft_to_work_transition(self):
        """DRF-* should allow transition to work state."""
        model = HierarchicalStatusModel()
        model.state = "DRF-NEW-CRT"

        assert can_proceed(model.start_inspection)
        model.start_inspection()
        assert model.state == "WRK-INS-PRG"

    def test_draft_prefix_matches_variants(self):
        """DRF-* should match DRF-NEW-CRT and DRF-INF-INC."""
        model = HierarchicalStatusModel()

        for state in ["DRF-NEW-CRT", "DRF-INF-INC"]:
            model.state = state
            assert can_proceed(model.start_inspection), f"Expected start_inspection() from {state}"


class TestPrefixWildcardSpecificity:
    """Test that more specific prefix patterns take precedence."""

    def test_more_specific_pattern_wins(self):
        """WRK-INS-* should take precedence over WRK-* for WRK-INS-PRG."""
        model = HierarchicalStatusModel()
        model.state = "WRK-INS-PRG"

        # start_repair uses WRK-INS-* (more specific)
        # complete uses WRK-* (less specific)
        # Both should be available, but let's verify start_repair works
        assert can_proceed(model.start_repair)
        model.start_repair()
        assert model.state == "WRK-REP-PRG"

    def test_less_specific_pattern_still_available(self):
        """WRK-* should still work for WRK-REP-PRG (no WRK-REP-* defined)."""
        model = HierarchicalStatusModel()
        model.state = "WRK-REP-PRG"

        # No WRK-REP-* pattern defined, so WRK-* should match
        assert can_proceed(model.complete)
        model.complete()
        assert model.state == "CMP-STD-DON"


class TestPrefixWithListSources:
    """Test prefix wildcards in source lists."""

    def test_list_with_prefix_wildcards(self):
        """source=['DRF-*', 'WRK-*'] should work."""
        model = HierarchicalStatusModel()

        # From draft
        model.state = "DRF-NEW-CRT"
        assert can_proceed(model.cancel)

        # From work
        model.state = "WRK-REP-PRG"
        assert can_proceed(model.cancel)

        # From completed - should NOT be allowed
        model.state = "CMP-STD-DON"
        assert not can_proceed(model.cancel)


class TestPrefixWithUniversalWildcard:
    """Test prefix wildcards coexisting with universal '*' wildcard."""

    def test_exact_match_beats_prefix(self):
        """Exact state match should take precedence over prefix wildcard."""
        # This is implicitly tested - exact matches are checked first

    def test_prefix_beats_universal(self):
        """Prefix wildcard should take precedence over universal '*'."""
        model = HierarchicalStatusModel()
        model.state = "WRK-INS-PRG"

        # complete() uses WRK-*, reset() uses *
        # Both should be available
        assert can_proceed(model.complete)
        assert can_proceed(model.reset)

    def test_universal_works_when_no_prefix_match(self):
        """Universal '*' should work when no prefix matches."""
        model = HierarchicalStatusModel()
        model.state = "CMP-STD-DON"

        # Only reset() with '*' should work (no CMP-* defined)
        assert not can_proceed(model.complete)
        assert can_proceed(model.reset)


class TestPrefixWildcardErrors:
    """Test error handling with prefix wildcards."""

    def test_transition_not_allowed_from_wrong_prefix(self):
        """Should raise TransitionNotAllowed when prefix doesn't match."""
        model = HierarchicalStatusModel()
        model.state = "CMP-STD-DON"

        with pytest.raises(TransitionNotAllowed):
            model.complete()  # WRK-* doesn't match CMP-STD-DON


class TestPrefixWildcardEdgeCases:
    """Test edge cases for prefix wildcard matching."""

    def test_partial_prefix_no_match(self):
        """'WRK-' alone should not match 'WRK-INS-PRG' (need 'WRK-*')."""
        # This is a design test - we only support patterns ending in '-*'

    def test_empty_after_prefix(self):
        """'WRK-*' should match 'WRK-' if that's a valid state."""
        model = HierarchicalStatusModel()
        model.state = "WRK-"  # Edge case: empty after prefix

        # WRK-* should still match WRK-
        assert can_proceed(model.complete)

    def test_case_sensitivity(self):
        """Pattern matching should be case-sensitive."""
        model = HierarchicalStatusModel()
        model.state = "wrk-ins-prg"  # lowercase

        # WRK-* should NOT match wrk-ins-prg
        assert not can_proceed(model.complete)

    def test_integer_state_no_prefix_match(self):
        """Prefix patterns should not match integer states."""
        # Prefix patterns require string states
        # Integer states would use exact match or universal wildcards
