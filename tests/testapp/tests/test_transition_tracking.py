from __future__ import annotations

from django.contrib.auth import get_user_model
from django.test import TestCase

from django_fsm.log import StateLog
from tests.testapp.models import GenericTrackedPost
from tests.testapp.models import TrackedPost
from tests.testapp.models import TrackedPostLog


class TransitionTrackingTests(TestCase):
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

        log = TrackedPostLog.objects.get(post=post)

        assert log.transition == "publish"
        assert log.state_field == "state"
        assert log.source_state == "new"
        assert log.state == "published"
        assert log.by == user
        assert log.description == "published via custom log"
