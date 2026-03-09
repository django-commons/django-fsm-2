from __future__ import annotations

import typing

from django.contrib.auth import get_user_model
from django.test import TestCase

from django_fsm.log import StateLog
from tests.testapp.models import CharPkTrackedPost
from tests.testapp.models import GenericTrackedPost
from tests.testapp.models import IntegerPkTrackedPost
from tests.testapp.models import TrackedPost
from tests.testapp.models import TrackedPostStateLog
from tests.testapp.models import UUIDPkTrackedPost

if typing.TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser
    from django.db import models


class TransitionTrackingTests(TestCase):
    def assert_state_log_created(self, post: models.Model, user: AbstractUser) -> None:
        log = StateLog.objects.for_(post).get(object_id=str(post.pk))

        assert log.transition == "publish"
        assert log.state_field == "state"
        assert log.source_state == "new"
        assert log.state == "published"
        assert log.by == user

    def test_default_tracking_uses_generic_log(self) -> None:
        user = get_user_model().objects.create_user(username="author")
        post = GenericTrackedPost.objects.create()
        post.publish(by=user, description="published via generic log")

        log = StateLog.objects.for_(post).get(object_id=str(post.pk))

        assert log.transition == "publish"
        assert log.state_field == "state"
        assert log.source_state == "new"
        assert log.state == "published"
        assert log.by == user
        assert log.description == "published via generic log"

    def test_custom_tracking_writes_to_model_log(self) -> None:
        user = get_user_model().objects.create_user(username="author")
        post = TrackedPost.objects.create()
        post.publish(by=user, description="published via custom log")

        log = TrackedPostStateLog.objects.get(post=post)

        assert log.transition == "publish"
        assert log.state_field == "state"
        assert log.source_state == "new"
        assert log.state == "published"
        assert log.by == user
        assert log.description == "published via custom log"

    def test_state_log_for_char_pk_model(self) -> None:
        user = get_user_model().objects.create_user(username="author")
        post = CharPkTrackedPost.objects.create(id="post-1")
        assert post.logs.count() == 0
        post.publish(by=user, description="published via char pk")
        assert post.logs.count() == 1

        self.assert_state_log_created(post, user)

    def test_state_log_for_integer_pk_model(self) -> None:
        user = get_user_model().objects.create_user(username="author")
        post = IntegerPkTrackedPost.objects.create(id=1)
        assert post.logs.count() == 0
        post.publish(by=user, description="published via integer pk")
        assert post.logs.count() == 1

        self.assert_state_log_created(post, user)

    def test_state_log_for_uuid_pk_model(self) -> None:
        user = get_user_model().objects.create_user(username="author")
        post = UUIDPkTrackedPost.objects.create()
        assert post.logs.count() == 0
        post.publish(by=user, description="published via uuid pk")
        assert post.logs.count() == 1

        self.assert_state_log_created(post, user)
