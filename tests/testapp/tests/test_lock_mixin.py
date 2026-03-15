from __future__ import annotations

import pytest
from django.db import models
from django.test import TestCase

import django_fsm as fsm


class ApplicationState(models.TextChoices):
    NEW = "NEW", "New"
    PUBLISHED = "PUBLISHED", "Published"
    REMOVED = "REMOVED", "Removed"
    WAITING = "WAITING", "Waiting"
    REJECTED = "REJECTED", "Rejected"


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
    review_state = fsm.FSMField(default=ApplicationState.WAITING, protected=True)
    notes = models.CharField(max_length=50)

    objects: models.Manager[ExtendedBlogPost] = models.Manager()

    @fsm.transition(
        field=review_state,
        source=ApplicationState.WAITING,
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
        post1 = LockedBlogPost.objects.create()
        post2 = LockedBlogPost.objects.get(pk=post1.pk)

        post1.publish()
        post1.save()

        post2.text = "aaa"
        post2.publish()
        with pytest.raises(fsm.ConcurrentTransition):
            post2.save()

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
        post1 = LockedBlogPost.objects.create()
        post2 = LockedBlogPost.objects.get(pk=post1.pk)

        post1.publish()
        post1.save()

        post2.refresh_from_db()
        post2.remove()
        post2.save()
