"""
Tests for prefix wildcard pattern edge cases.

These tests verify edge cases in prefix pattern matching:
- Non-string states
- Different separators
- Overlapping patterns
- Pattern precedence
- Integration with conditions and permissions
- Empty and malformed patterns
"""

from __future__ import annotations

from django.db import models

from django_fsm_rx import FSMField
from django_fsm_rx import FSMIntegerField
from django_fsm_rx import can_proceed
from django_fsm_rx import has_transition_perm
from django_fsm_rx import transition


# Module-level condition functions for prefix pattern tests
def _always_true(instance):
    return True


def _always_false(instance):
    return False


class PrefixConditionPassModel(models.Model):
    """Model for testing prefix pattern with passing condition."""

    state = FSMField(default="WRK-REP-PRG")

    @transition(field=state, source="WRK-*", target="CMP-STD-DON", conditions=[_always_true])
    def complete(self):
        pass

    class Meta:
        app_label = "tests"


class PrefixConditionFailModel(models.Model):
    """Model for testing prefix pattern with failing condition."""

    state = FSMField(default="WRK-REP-PRG")

    @transition(field=state, source="WRK-*", target="CMP-STD-DON", conditions=[_always_false])
    def complete(self):
        pass

    class Meta:
        app_label = "tests"


class PrefixStringPermModel(models.Model):
    """Model for testing prefix pattern with string permission."""

    state = FSMField(default="WRK-REP-PRG")

    @transition(
        field=state,
        source="WRK-*",
        target="CMP-STD-DON",
        permission="testapp.can_complete",
    )
    def complete(self):
        pass

    class Meta:
        app_label = "tests"


def _is_manager(instance, user):
    """Check if user is a manager."""
    return getattr(user, "is_manager", False)


class PrefixCallablePermModel(models.Model):
    """Model for testing prefix pattern with callable permission."""

    state = FSMField(default="WRK-REP-PRG")

    @transition(field=state, source="WRK-*", target="CMP-STD-DON", permission=_is_manager)
    def complete(self):
        pass

    class Meta:
        app_label = "tests"


class TestPrefixPatternSeparators:
    """Test prefix patterns with different separators.

    Note: Prefix wildcard patterns ONLY support '-*' suffix (dash-asterisk).
    Other separators like '/', '.', ':' require exact match or can be
    combined with the standard '-' separator.
    """

    def test_dash_separator_is_required(self):
        """Prefix patterns only work with dash separator (e.g., 'WRK-*')."""

        class DashModel(models.Model):
            state = FSMField(default="CAT-SUB-STA")

            @transition(field=state, source="CAT-*", target="OTH-SUB-STA")
            def change_category(self):
                pass

            class Meta:
                app_label = "tests"

        model = DashModel()
        assert can_proceed(model.change_category)
        model.change_category()
        assert model.state == "OTH-SUB-STA"

    def test_non_dash_patterns_require_exact_match(self):
        """Non-dash separators with '*' are treated as literal characters."""

        class SlashModel(models.Model):
            state = FSMField(default="CAT/SUB/STA")

            # This is NOT a wildcard - it's an exact match for "CAT/*"
            @transition(field=state, source="CAT/*", target="OTH/SUB/STA")
            def pattern_match(self):
                pass

            # Exact match works
            @transition(field=state, source="CAT/SUB/STA", target="OTH/SUB/STA")
            def exact_match(self):
                pass

            class Meta:
                app_label = "tests"

        model = SlashModel()
        # Pattern "CAT/*" is NOT a wildcard, so it won't match "CAT/SUB/STA"
        assert not can_proceed(model.pattern_match)
        # But exact match works
        assert can_proceed(model.exact_match)

    def test_universal_wildcard_works_with_any_separator(self):
        """Universal wildcard '*' matches any state regardless of separator."""

        class UniversalModel(models.Model):
            state = FSMField(default="pkg.mod.cls")

            @transition(field=state, source="*", target="done")
            def finish(self):
                pass

            class Meta:
                app_label = "tests"

        model = UniversalModel()
        assert can_proceed(model.finish)

        model.state = "ns:sub:state"
        assert can_proceed(model.finish)

        model.state = "cat_sub_state"
        assert can_proceed(model.finish)


class TestPrefixPatternNonStringStates:
    """Test prefix patterns with non-string states."""

    def test_prefix_not_matched_on_integer_states(self):
        """Prefix patterns should not match integer states."""

        class IntStateModel(models.Model):
            state = FSMIntegerField(default=100)

            @transition(field=state, source="10*", target=200)
            def bad_prefix(self):
                """This should NOT match integer 100."""
                pass

            @transition(field=state, source=100, target=200)
            def good_exact(self):
                """This SHOULD match integer 100."""
                pass

            class Meta:
                app_label = "tests"

        model = IntStateModel()
        # Prefix pattern should not match integer
        assert not can_proceed(model.bad_prefix)
        # Exact match should work
        assert can_proceed(model.good_exact)

    def test_wildcard_matches_integer_states(self):
        """Universal wildcard * should still match integer states."""

        class IntWildcardModel(models.Model):
            state = FSMIntegerField(default=100)

            @transition(field=state, source="*", target=200)
            def universal(self):
                pass

            class Meta:
                app_label = "tests"

        model = IntWildcardModel()
        assert can_proceed(model.universal)


class TestPrefixPatternPrecedence:
    """Test pattern precedence: exact > longer prefix > shorter prefix > * > +."""

    def test_exact_match_beats_prefix(self):
        """Exact state match should take precedence over prefix wildcard."""

        class PrecedenceModel(models.Model):
            state = FSMField(default="WRK-REP-PRG")

            @transition(field=state, source="WRK-REP-PRG", target="exact_target")
            def exact_match(self):
                pass

            @transition(field=state, source="WRK-*", target="prefix_target")
            def prefix_match(self):
                pass

            class Meta:
                app_label = "tests"

        model = PrecedenceModel()
        # Both should be available
        assert can_proceed(model.exact_match)
        assert can_proceed(model.prefix_match)

    def test_longer_prefix_available_alongside_shorter(self):
        """Longer prefix should be available alongside shorter prefix."""

        class PrefixLengthModel(models.Model):
            state = FSMField(default="WRK-REP-PRG")

            @transition(field=state, source="WRK-REP-*", target="long_prefix_target")
            def long_prefix(self):
                pass

            @transition(field=state, source="WRK-*", target="short_prefix_target")
            def short_prefix(self):
                pass

            class Meta:
                app_label = "tests"

        model = PrefixLengthModel()
        # Both should be available
        assert can_proceed(model.long_prefix)
        assert can_proceed(model.short_prefix)

    def test_prefix_beats_universal_wildcard(self):
        """Prefix wildcard should be available alongside universal wildcard."""

        class PrefixVsUniversalModel(models.Model):
            state = FSMField(default="WRK-REP-PRG")

            @transition(field=state, source="WRK-*", target="prefix_target")
            def prefix_match(self):
                pass

            @transition(field=state, source="*", target="universal_target")
            def universal_match(self):
                pass

            class Meta:
                app_label = "tests"

        model = PrefixVsUniversalModel()
        # Both should be available
        assert can_proceed(model.prefix_match)
        assert can_proceed(model.universal_match)


class TestPrefixPatternEdgeCases:
    """Test edge cases in prefix pattern matching."""

    def test_pattern_without_asterisk_is_exact_match(self):
        """Pattern 'WRK-' (without *) should be treated as exact match."""

        class NoAsteriskModel(models.Model):
            state = FSMField(default="WRK-")

            @transition(field=state, source="WRK-", target="done")
            def finish(self):
                pass

            class Meta:
                app_label = "tests"

        model = NoAsteriskModel()
        assert can_proceed(model.finish)

        # Should NOT match "WRK-REP-PRG"
        model.state = "WRK-REP-PRG"
        assert not can_proceed(model.finish)

    def test_asterisk_alone_at_end_of_prefix(self):
        """Pattern ending with -* should match states with that prefix."""

        class AsteriskEndModel(models.Model):
            state = FSMField(default="A-B-C")

            @transition(field=state, source="A-*", target="done")
            def from_a(self):
                pass

            class Meta:
                app_label = "tests"

        model = AsteriskEndModel()
        assert can_proceed(model.from_a)

    def test_multiple_consecutive_separators(self):
        """Handle multiple consecutive separators in state."""

        class DoubleSepModel(models.Model):
            state = FSMField(default="WRK--PRG")

            @transition(field=state, source="WRK-*", target="done")
            def finish(self):
                pass

            class Meta:
                app_label = "tests"

        model = DoubleSepModel()
        # "WRK--PRG" starts with "WRK-" so should match "WRK-*"
        assert can_proceed(model.finish)

    def test_empty_state_after_prefix(self):
        """Pattern should match when state is exactly the prefix."""

        class EmptyAfterPrefixModel(models.Model):
            state = FSMField(default="WRK-")

            @transition(field=state, source="WRK-*", target="done")
            def finish(self):
                pass

            class Meta:
                app_label = "tests"

        model = EmptyAfterPrefixModel()
        # "WRK-" should match "WRK-*" (empty string after prefix)
        assert can_proceed(model.finish)

    def test_state_equals_prefix_without_separator(self):
        """State that equals prefix without separator should NOT match."""

        class ExactPrefixModel(models.Model):
            state = FSMField(default="WRK")

            @transition(field=state, source="WRK-*", target="done")
            def finish(self):
                pass

            @transition(field=state, source="WRK", target="done2")
            def exact(self):
                pass

            class Meta:
                app_label = "tests"

        model = ExactPrefixModel()
        # "WRK" should NOT match "WRK-*" (no separator)
        assert not can_proceed(model.finish)
        # But exact match should work
        assert can_proceed(model.exact)

    def test_asterisk_in_middle_not_supported(self):
        """Asterisk in middle of pattern should be treated literally."""

        class MiddleAsteriskModel(models.Model):
            state = FSMField(default="A-*-C")

            @transition(field=state, source="A-*-C", target="done")
            def literal_match(self):
                pass

            class Meta:
                app_label = "tests"

        model = MiddleAsteriskModel()
        # Should match literally "A-*-C"
        assert can_proceed(model.literal_match)

        # Should NOT match "A-B-C"
        model.state = "A-B-C"
        assert not can_proceed(model.literal_match)


class TestPrefixPatternWithConditions:
    """Test prefix patterns combined with conditions."""

    def test_prefix_with_passing_condition(self):
        """Prefix pattern with passing condition should allow transition."""
        # Define condition function at module level to avoid class scoping issues
        model = PrefixConditionPassModel()
        assert can_proceed(model.complete)

    def test_prefix_with_failing_condition(self):
        """Prefix pattern with failing condition should block transition."""
        model = PrefixConditionFailModel()
        assert not can_proceed(model.complete)

    def test_prefix_with_instance_checking_condition(self):
        """Prefix pattern with condition that checks instance state."""

        def check_has_reviewer(instance):
            return hasattr(instance, "reviewer") and instance.reviewer

        class ReviewerModel(models.Model):
            state = FSMField(default="WRK-REV-PND")
            reviewer = None

            @transition(
                field=state,
                source="WRK-*",
                target="CMP-REV-DON",
                conditions=[check_has_reviewer],
            )
            def complete_review(self):
                pass

            class Meta:
                app_label = "tests"

        model = ReviewerModel()
        assert not can_proceed(model.complete_review)

        model.reviewer = "Alice"
        assert can_proceed(model.complete_review)


class TestPrefixPatternWithPermissions:
    """Test prefix patterns combined with permissions."""

    def test_prefix_with_string_permission(self):
        """Prefix pattern with string permission should check permission."""
        model = PrefixStringPermModel()

        # Create mock user without permission (Django's has_perm takes perm and optional obj)
        class MockUser:
            def has_perm(self, perm, obj=None):
                return False

        user = MockUser()
        assert not has_transition_perm(model.complete, user)

        # User with permission
        class MockUserWithPerm:
            def has_perm(self, perm, obj=None):
                return perm == "testapp.can_complete"

        user_with_perm = MockUserWithPerm()
        assert has_transition_perm(model.complete, user_with_perm)

    def test_prefix_with_callable_permission(self):
        """Prefix pattern with callable permission."""
        model = PrefixCallablePermModel()

        class RegularUser:
            is_manager = False

        class ManagerUser:
            is_manager = True

        assert not has_transition_perm(model.complete, RegularUser())
        assert has_transition_perm(model.complete, ManagerUser())


class TestPrefixPatternInLists:
    """Test prefix patterns in source lists."""

    def test_multiple_prefix_patterns_in_list(self):
        """Multiple prefix patterns in source list should all work."""

        class MultiPrefixModel(models.Model):
            state = FSMField(default="DRF-NEW-CRT")

            @transition(field=state, source=["DRF-*", "WRK-*", "QC-*"], target="CAN-USR-REQ")
            def cancel(self):
                pass

            class Meta:
                app_label = "tests"

        model = MultiPrefixModel()

        # From DRF
        model.state = "DRF-NEW-CRT"
        assert can_proceed(model.cancel)

        # From WRK
        model.state = "WRK-REP-PRG"
        assert can_proceed(model.cancel)

        # From QC
        model.state = "QC-REV-PND"
        assert can_proceed(model.cancel)

        # NOT from CMP
        model.state = "CMP-STD-DON"
        assert not can_proceed(model.cancel)

    def test_mix_exact_and_prefix_in_list(self):
        """Mix of exact states and prefix patterns in source list."""

        class MixedModel(models.Model):
            state = FSMField(default="DRF-NEW-CRT")

            @transition(
                field=state,
                source=["SPECIAL", "DRF-*", "WRK-REP-PRG"],
                target="PROCESSED",
            )
            def process(self):
                pass

            class Meta:
                app_label = "tests"

        model = MixedModel()

        # Exact match
        model.state = "SPECIAL"
        assert can_proceed(model.process)

        # Prefix match
        model.state = "DRF-NEW-CRT"
        assert can_proceed(model.process)

        # Another exact match
        model.state = "WRK-REP-PRG"
        assert can_proceed(model.process)

        # This should NOT match (WRK-* not in list, only WRK-REP-PRG)
        model.state = "WRK-INS-PRG"
        assert not can_proceed(model.process)

    def test_universal_and_prefix_in_list(self):
        """Universal wildcard and prefix in same list."""

        class UniversalPrefixModel(models.Model):
            state = FSMField(default="DRF-NEW-CRT")

            @transition(field=state, source=["*", "WRK-*"], target="DONE")
            def finish(self):
                """Both * and WRK-* - * should match everything anyway."""
                pass

            class Meta:
                app_label = "tests"

        model = UniversalPrefixModel()

        # Should match anything due to *
        for state in ["DRF-NEW-CRT", "WRK-REP-PRG", "ANYTHING", "123"]:
            model.state = state
            assert can_proceed(model.finish)


class TestPrefixPatternCaseSensitivity:
    """Test case sensitivity of prefix patterns."""

    def test_prefix_is_case_sensitive(self):
        """Prefix pattern matching should be case-sensitive."""

        class CaseModel(models.Model):
            state = FSMField(default="WRK-REP-PRG")

            @transition(field=state, source="WRK-*", target="done")
            def upper_prefix(self):
                pass

            @transition(field=state, source="wrk-*", target="done2")
            def lower_prefix(self):
                pass

            class Meta:
                app_label = "tests"

        model = CaseModel()

        # Upper case state, upper case pattern
        model.state = "WRK-REP-PRG"
        assert can_proceed(model.upper_prefix)
        assert not can_proceed(model.lower_prefix)

        # Lower case state, lower case pattern
        model.state = "wrk-rep-prg"
        assert not can_proceed(model.upper_prefix)
        assert can_proceed(model.lower_prefix)


class TestPrefixPatternWithSpecialCharacters:
    """Test prefix patterns with special characters in states."""

    def test_state_with_spaces(self):
        """Prefix pattern with spaces in state."""

        class SpaceModel(models.Model):
            state = FSMField(default="Category A-Status 1")

            @transition(field=state, source="Category A-*", target="done")
            def finish(self):
                pass

            class Meta:
                app_label = "tests"

        model = SpaceModel()
        assert can_proceed(model.finish)

    def test_state_with_unicode(self):
        """Prefix pattern with unicode characters."""

        class UnicodeModel(models.Model):
            state = FSMField(default="状态-新建")

            @transition(field=state, source="状态-*", target="完成")
            def finish(self):
                pass

            class Meta:
                app_label = "tests"

        model = UnicodeModel()
        assert can_proceed(model.finish)
        model.finish()
        assert model.state == "完成"
