from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

import django_fsm as fsm

from ..choices import ApplicationState


class LockedBlogPost(fsm.ConcurrentTransitionMixin, models.Model):
    state = fsm.FSMField(choices=ApplicationState.choices, default=ApplicationState.NEW)
    text = models.CharField(max_length=50)

    objects: models.Manager[LockedBlogPost] = models.Manager()

    @fsm.transition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.PUBLISHED,
    )
    def publish(self):
        pass

    @fsm.transition(
        field=state,
        source=ApplicationState.PUBLISHED,
        target=ApplicationState.REMOVED,
    )
    def remove(self):
        pass


class ExtendedBlogPost(LockedBlogPost):
    review_state = fsm.FSMField(default=ApplicationState.BLOCKED, protected=True)
    notes = models.CharField(max_length=50)

    objects: models.Manager[ExtendedBlogPost] = models.Manager()

    @fsm.transition(
        field=review_state,
        source=ApplicationState.BLOCKED,
        target=ApplicationState.REJECTED,
    )
    def reject(self):
        pass


class TestLockMixin(TestCase):
    def test_create_succeed(self):
        LockedBlogPost.objects.create(text="test_create_succeed")

    def test_crud_succeed(self):
        post = LockedBlogPost(text="test_crud_succeed")
        post.publish()
        post.save()

        post = LockedBlogPost.objects.get(pk=post.pk)
        assert post.state == ApplicationState.PUBLISHED

        post.text = "test_crud_succeed2"
        post.save()

        post = LockedBlogPost.objects.get(pk=post.pk)
        assert post.text == "test_crud_succeed2"

        post.delete()

    def test_save_and_change_succeed(self):
        post = LockedBlogPost(text="test_crud_succeed")
        post.publish()
        post.save()

        post.remove()
        post.save()

        post.delete()

    def test_concurrent_modifications_raise_exception(self):
        saved_post = LockedBlogPost.objects.create()
        stale_post = LockedBlogPost.objects.get(pk=saved_post.pk)

        saved_post.publish()
        saved_post.save()

        stale_post.text = "aaa"
        stale_post.publish()
        with pytest.raises(fsm.ConcurrentTransition):
            stale_post.save()

    def test_inheritance_crud_succeed(self):
        post = ExtendedBlogPost(text="test_inheritance_crud_succeed", notes="reject me")
        post.publish()
        post.save()

        post = ExtendedBlogPost.objects.get(pk=post.pk)
        assert post.state == ApplicationState.PUBLISHED

        post.text = "test_inheritance_crud_succeed2"
        post.reject()
        post.save()

        post = ExtendedBlogPost.objects.get(pk=post.pk)
        assert post.review_state == ApplicationState.REJECTED
        assert post.text == "test_inheritance_crud_succeed2"

    def test_concurrent_modifications_after_refresh_db_succeed(self):  # bug 255
        saved_post = LockedBlogPost.objects.create()
        stale_post = LockedBlogPost.objects.get(pk=saved_post.pk)

        saved_post.publish()
        saved_post.save()

        stale_post.refresh_from_db()
        stale_post.remove()
        stale_post.save()
