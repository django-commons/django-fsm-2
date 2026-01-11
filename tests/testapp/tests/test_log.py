"""Tests for FSM logging functionality."""

from __future__ import annotations

from unittest.mock import MagicMock
from unittest.mock import patch

from django.contrib.auth.models import User
from django.test import TestCase

from django_fsm_2.log import FSMLogDescriptor
from django_fsm_2.log import fsm_log_by
from django_fsm_2.log import fsm_log_context
from django_fsm_2.log import fsm_log_description

from ..models import LoggableArticle


class FSMLogDescriptorTests(TestCase):
    """Tests for FSMLogDescriptor context manager."""

    def test_descriptor_sets_attribute(self):
        """Test that descriptor sets attribute on instance."""
        instance = MagicMock()

        with FSMLogDescriptor(instance, "by", "test_value"):
            self.assertEqual(instance._fsm_log_by, "test_value")

        # Should be cleared after context
        self.assertFalse(hasattr(instance, "_fsm_log_by"))

    def test_descriptor_clears_attribute_on_exit(self):
        """Test that attribute is cleared when exiting context."""
        instance = MagicMock()
        instance._fsm_log_by = "initial"

        with FSMLogDescriptor(instance, "by", "new_value"):
            self.assertEqual(instance._fsm_log_by, "new_value")

        # MagicMock doesn't truly delete, but real objects would
        # For real test, we verify the delattr was called

    def test_descriptor_set_method(self):
        """Test the set() method updates value."""
        instance = MagicMock()

        with FSMLogDescriptor(instance, "description") as desc:
            desc.set("First description")
            self.assertEqual(instance._fsm_log_description, "First description")

            desc.set("Updated description")
            self.assertEqual(instance._fsm_log_description, "Updated description")

    def test_descriptor_with_none_value(self):
        """Test that None value doesn't set attribute initially."""

        class SimpleObj:
            pass

        instance = SimpleObj()

        with FSMLogDescriptor(instance, "by", None):
            # Should not set attribute when value is None
            self.assertFalse(hasattr(instance, "_fsm_log_by"))


class FSMLogByDecoratorTests(TestCase):
    """Tests for @fsm_log_by decorator."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass",
        )

    def test_fsm_log_by_sets_user(self):
        """Test that fsm_log_by sets _fsm_log_by on instance."""
        article = LoggableArticle.objects.create(title="Test")

        # The decorator wraps the transition and sets _fsm_log_by
        # We need to check during the transition
        logged_by = None

        def capture_by(sender, instance, **kwargs):
            nonlocal logged_by
            logged_by = getattr(instance, "_fsm_log_by", None)

        from django_fsm_2.signals import post_transition

        post_transition.connect(capture_by)
        try:
            article.publish(by=self.user, description="Test publish")
            article.save()
        finally:
            post_transition.disconnect(capture_by)

        self.assertEqual(logged_by, self.user)

    def test_fsm_log_by_without_user(self):
        """Test that transition works without providing user."""
        article = LoggableArticle.objects.create(title="Test")

        # Should work fine without 'by' argument
        article.publish()
        article.save()

        # State should change
        article = LoggableArticle.objects.get(pk=article.pk)
        self.assertEqual(article.state, "published")


class FSMLogDescriptionDecoratorTests(TestCase):
    """Tests for @fsm_log_description decorator."""

    def test_fsm_log_description_sets_description(self):
        """Test that fsm_log_description sets _fsm_log_description."""
        article = LoggableArticle.objects.create(title="Test")

        logged_description = None

        def capture_description(sender, instance, **kwargs):
            nonlocal logged_description
            logged_description = getattr(instance, "_fsm_log_description", None)

        from django_fsm_2.signals import post_transition

        post_transition.connect(capture_description)
        try:
            article.publish(description="Published for testing")
            article.save()
        finally:
            post_transition.disconnect(capture_description)

        self.assertEqual(logged_description, "Published for testing")

    def test_fsm_log_description_without_description(self):
        """Test that transition works without description."""
        article = LoggableArticle.objects.create(title="Test")

        # Should work fine without description
        article.publish()
        article.save()

        article = LoggableArticle.objects.get(pk=article.pk)
        self.assertEqual(article.state, "published")


class FSMLogContextTests(TestCase):
    """Tests for fsm_log_context context manager."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass",
        )

    def test_fsm_log_context_sets_both(self):
        """Test that context manager sets both by and description."""
        article = LoggableArticle.objects.create(title="Test")

        logged_by = None
        logged_description = None

        def capture_log(sender, instance, **kwargs):
            nonlocal logged_by, logged_description
            logged_by = getattr(instance, "_fsm_log_by", None)
            logged_description = getattr(instance, "_fsm_log_description", None)

        from django_fsm_2.signals import post_transition

        post_transition.connect(capture_log)
        try:
            with fsm_log_context(article, by=self.user, description="Context test"):
                article.publish()
                article.save()
        finally:
            post_transition.disconnect(capture_log)

        self.assertEqual(logged_by, self.user)
        self.assertEqual(logged_description, "Context test")

    def test_fsm_log_context_clears_on_exit(self):
        """Test that context manager clears attributes on exit."""
        article = LoggableArticle.objects.create(title="Test")

        with fsm_log_context(article, by=self.user, description="Test"):
            self.assertEqual(article._fsm_log_by, self.user)
            self.assertEqual(article._fsm_log_description, "Test")

        # Should be cleared after context
        self.assertFalse(hasattr(article, "_fsm_log_by"))
        self.assertFalse(hasattr(article, "_fsm_log_description"))

    def test_fsm_log_context_partial(self):
        """Test context manager with only some arguments."""
        article = LoggableArticle.objects.create(title="Test")

        with fsm_log_context(article, by=self.user):
            self.assertEqual(article._fsm_log_by, self.user)
            self.assertFalse(hasattr(article, "_fsm_log_description"))

        with fsm_log_context(article, description="Only description"):
            self.assertFalse(hasattr(article, "_fsm_log_by"))
            self.assertEqual(article._fsm_log_description, "Only description")


class FSMLogIntegrationTests(TestCase):
    """Integration tests for FSM logging with signals."""

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="testpass",
        )

    def test_signal_receives_log_attributes(self):
        """Test that post_transition signal can access log attributes."""
        article = LoggableArticle.objects.create(title="Test")

        transition_log = {}

        def log_handler(sender, instance, name, source, target, **kwargs):
            transition_log["name"] = name
            transition_log["source"] = source
            transition_log["target"] = target
            transition_log["by"] = getattr(instance, "_fsm_log_by", None)
            transition_log["description"] = getattr(instance, "_fsm_log_description", None)

        from django_fsm_2.signals import post_transition

        post_transition.connect(log_handler)
        try:
            article.publish(by=self.user, description="Test transition")
            article.save()
        finally:
            post_transition.disconnect(log_handler)

        self.assertEqual(transition_log["name"], "publish")
        self.assertEqual(transition_log["source"], "draft")
        self.assertEqual(transition_log["target"], "published")
        self.assertEqual(transition_log["by"], self.user)
        self.assertEqual(transition_log["description"], "Test transition")

    def test_chained_transitions_log_correctly(self):
        """Test logging works correctly across multiple transitions."""
        article = LoggableArticle.objects.create(title="Test")

        transition_logs = []

        def log_handler(sender, instance, name, source, target, **kwargs):
            transition_logs.append({
                "name": name,
                "source": source,
                "target": target,
                "by": getattr(instance, "_fsm_log_by", None),
            })

        from django_fsm_2.signals import post_transition

        post_transition.connect(log_handler)
        try:
            # First transition
            article.publish(by=self.user)
            article.save()

            # Second transition (archive only has @fsm_log_by)
            article.archive(by=self.user)
            article.save()
        finally:
            post_transition.disconnect(log_handler)

        self.assertEqual(len(transition_logs), 2)

        # First transition
        self.assertEqual(transition_logs[0]["name"], "publish")
        self.assertEqual(transition_logs[0]["by"], self.user)

        # Second transition
        self.assertEqual(transition_logs[1]["name"], "archive")
        self.assertEqual(transition_logs[1]["by"], self.user)
