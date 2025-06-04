from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

from django_fsm import FSMKeyField
from django_fsm import TransitionNotAllowed
from django_fsm import can_proceed
from django_fsm import transition
from tests.testapp.models import DbState

FK_AVAILABLE_STATES = (
    ("New", "_NEW_"),
    ("Published", "_PUBLISHED_"),
    ("Hidden", "_HIDDEN_"),
    ("Removed", "_REMOVED_"),
    ("Stolen", "_STOLEN_"),
    ("Moderated", "_MODERATED_"),
)


class FKBlogPost(models.Model):
    state = FSMKeyField(DbState, default="new", protected=True, on_delete=models.CASCADE)

    @transition(field=state, source="new", target="published")
    def publish(self):
        pass

    @transition(field=state, source="published")
    def notify_all(self):
        pass

    @transition(field=state, source="published", target="hidden")
    def hide(self):
        pass

    @transition(field=state, source="new", target="removed")
    def remove(self):
        raise Exception("Upss")

    @transition(field=state, source=["published", "hidden"], target="stolen")
    def steal(self):
        pass

    @transition(field=state, source="*", target="moderated")
    def moderate(self):
        pass


class FSMKeyFieldTest(TestCase):
    def setUp(self):
        for item in FK_AVAILABLE_STATES:
            DbState.objects.create(pk=item[0], label=item[1])
        self.model = FKBlogPost()

    def test_initial_state_instantiated(self):
        assert self.model.state == "new"

    def test_known_transition_should_succeed(self):
        assert can_proceed(self.model.publish)
        self.model.publish()
        assert self.model.state == "published"

        assert can_proceed(self.model.hide)
        self.model.hide()
        assert self.model.state == "hidden"

    def test_unknown_transition_fails(self):
        assert not can_proceed(self.model.hide)
        with pytest.raises(TransitionNotAllowed):
            self.model.hide()

    def test_state_non_changed_after_fail(self):
        assert can_proceed(self.model.remove)
        with pytest.raises(Exception, match="Upss"):
            self.model.remove()
        assert self.model.state == "new"

    def test_allowed_null_transition_should_succeed(self):
        assert can_proceed(self.model.publish)
        self.model.publish()
        self.model.notify_all()
        assert self.model.state == "published"

    def test_unknown_null_transition_should_fail(self):
        with pytest.raises(TransitionNotAllowed):
            self.model.notify_all()
        assert self.model.state == "new"

    def test_multiple_source_support_path_1_works(self):
        self.model.publish()
        self.model.steal()
        assert self.model.state == "stolen"

    def test_multiple_source_support_path_2_works(self):
        self.model.publish()
        self.model.hide()
        self.model.steal()
        assert self.model.state == "stolen"

    def test_star_shortcut_succeed(self):
        assert can_proceed(self.model.moderate)
        self.model.moderate()
        assert self.model.state == "moderated"


"""
# TODO: FIX it
class BlogPostStatus(models.Model):
    name = models.CharField(unique=True, max_length=10)
    objects = models.Manager()


class BlogPostWithFKState(models.Model):
    status = FSMKeyField(BlogPostStatus, default=lambda: BlogPostStatus.objects.get(name="new"))

    @transition(field=status, source='new', target='published')
    def publish(self):
        pass

    @transition(field=status, source='published', target='hidden')
    def hide(self):
        pass


class BlogPostWithFKStateTest(TestCase):
    def setUp(self):
        BlogPostStatus.objects.create(name="new")
        BlogPostStatus.objects.create(name="published")
        BlogPostStatus.objects.create(name="hidden")
        self.model = BlogPostWithFKState()

    def test_known_transition_should_succeed(self):
        self.model.publish()
        self.assertEqual(self.model.state, 'published')

        self.model.hide()
        self.assertEqual(self.model.state, 'hidden')

    def test_unknown_transition_fails(self):
        with pytest.raises(TransitionNotAllowed):
            self.model.hide()
"""
