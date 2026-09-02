from __future__ import annotations

import inspect

import pytest
from asgiref.sync import sync_to_async
from django.contrib.auth.models import AnonymousUser
from django.db import models
from django.test import TestCase

import django_fsm as fsm
from django_fsm.management.commands.graph_transitions import all_fsm_fields_data
from django_fsm.management.commands.graph_transitions import generate_dot
from django_fsm.signals import post_transition
from django_fsm.signals import pre_transition

from ..choices import ApplicationState
from .test_basic_transitions import SimpleBlogPost


def _sync_true(_instance):
    return True


def _sync_false(_instance):
    return False


async def _async_true(_instance):
    return True


async def _async_false(_instance):
    return False


def _sync_perm(_instance, _user):
    return True


async def _async_perm_true(_instance, _user):
    return True


async def _async_perm_false(_instance, _user):
    return False


class AsyncBlogPost(models.Model):
    state = fsm.FSMField(default=ApplicationState.NEW)

    @fsm.atransition(field=state, source=ApplicationState.NEW, target=ApplicationState.PUBLISHED)
    async def publish(self):
        return "published-result"

    @fsm.atransition(
        field=state,
        source=ApplicationState.PUBLISHED,
        target=ApplicationState.HIDDEN,
        on_error=ApplicationState.FAILED,
    )
    async def hide_with_failure(self):
        raise RuntimeError("boom")

    @fsm.atransition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.PUBLISHED,
        conditions=[_async_true, _sync_true],
    )
    async def publish_with_mixed_conditions(self):
        pass

    @fsm.atransition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.PUBLISHED,
        conditions=[_async_false],
    )
    async def publish_blocked_async(self):
        pass

    @fsm.atransition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.PUBLISHED,
        permission=_async_perm_true,
    )
    async def publish_async_perm_allowed(self):
        pass

    @fsm.atransition(
        field=state,
        source=ApplicationState.NEW,
        target=ApplicationState.PUBLISHED,
        permission=_async_perm_false,
    )
    async def publish_async_perm_denied(self):
        pass


async def _async_target(_instance, allow):
    return ApplicationState.PUBLISHED if allow else ApplicationState.REJECTED


class AsyncGetStateModel(models.Model):
    state = fsm.FSMField(default=ApplicationState.NEW)

    @fsm.atransition(
        field=state,
        source=ApplicationState.NEW,
        target=fsm.GET_STATE(
            _async_target,
            states=[ApplicationState.PUBLISHED, ApplicationState.REJECTED],
        ),
    )
    async def moderate(self, allow):
        return None

    @fsm.atransition(
        field=state,
        source=ApplicationState.NEW,
        target=fsm.RETURN_VALUE(ApplicationState.PUBLISHED, ApplicationState.REJECTED),
    )
    async def publish_or_reject(self, *, accept):
        return ApplicationState.PUBLISHED if accept else ApplicationState.REJECTED


class AsyncMultiDecoratedModel(models.Model):
    counter = models.IntegerField(default=0)
    state = fsm.FSMField(default=ApplicationState.NEW)

    @fsm.atransition(field=state, source=ApplicationState.PUBLISHED, target=ApplicationState.HIDDEN)
    @fsm.atransition(field=state, source=ApplicationState.NEW, target=ApplicationState.PUBLISHED)
    async def step(self):
        self.counter += 1


class AsyncRefreshableProtected(fsm.FSMModelMixin, models.Model):
    state = fsm.FSMField(default=ApplicationState.NEW, protected=True)

    @fsm.atransition(field=state, source=ApplicationState.NEW, target=ApplicationState.PUBLISHED)
    async def publish(self):
        pass


class AsyncLoggedModel(models.Model):
    """Deliberately NOT added to DJANGO_FSM_LOG_IGNORED_MODELS so django_fsm_log
    receivers fire and we can verify they run on the async path via asend."""

    state = fsm.FSMField(default=ApplicationState.NEW)

    @fsm.atransition(field=state, source=ApplicationState.NEW, target=ApplicationState.PUBLISHED)
    async def publish(self):
        pass


class AsyncDeferrableModel(models.Model):
    state = fsm.FSMField(default=ApplicationState.NEW)

    objects: models.Manager[AsyncDeferrableModel] = models.Manager()

    @fsm.atransition(field=state, source=ApplicationState.NEW, target=ApplicationState.PUBLISHED)
    async def publish(self):
        pass


class AsyncTransitionBasicsTestCase(TestCase):
    async def test_async_transition_runs_and_sets_state(self):
        post = AsyncBlogPost()
        result = await post.publish()

        assert post.state == ApplicationState.PUBLISHED
        assert result == "published-result"

    async def test_async_wrapper_is_coroutine_function(self):
        assert inspect.iscoroutinefunction(AsyncBlogPost.publish)
        assert inspect.iscoroutinefunction(AsyncBlogPost().publish)

    async def test_sync_wrapper_still_sync_when_method_is_sync(self):
        assert not inspect.iscoroutinefunction(SimpleBlogPost.publish)

    async def test_async_transition_disallowed_from_wrong_state_raises(self):
        post = AsyncBlogPost(state=ApplicationState.PUBLISHED)

        with pytest.raises(fsm.TransitionNotAllowed):
            await post.publish()

    async def test_async_transition_records_on_error_state(self):
        post = AsyncBlogPost(state=ApplicationState.PUBLISHED)

        with pytest.raises(RuntimeError, match="boom"):
            await post.hide_with_failure()

        assert post.state == ApplicationState.FAILED


class AsyncConditionsTestCase(TestCase):
    async def test_acan_proceed_true_for_async_condition(self):
        post = AsyncBlogPost()

        assert await fsm.acan_proceed(post.publish_with_mixed_conditions)

    async def test_acan_proceed_false_when_async_condition_fails(self):
        post = AsyncBlogPost()

        assert not await fsm.acan_proceed(post.publish_blocked_async)

    async def test_async_condition_failure_raises_transition_not_allowed(self):
        post = AsyncBlogPost()

        with pytest.raises(fsm.TransitionNotAllowed):
            await post.publish_blocked_async()

    async def test_sync_condition_works_on_async_transition(self):
        post = AsyncBlogPost()

        assert await fsm.acan_proceed(post.publish_with_mixed_conditions)
        await post.publish_with_mixed_conditions()

        assert post.state == ApplicationState.PUBLISHED

    async def test_acan_proceed_skip_conditions(self):
        post = AsyncBlogPost()

        assert await fsm.acan_proceed(post.publish_blocked_async, check_conditions=False)

    async def test_acan_proceed_rejects_non_transition(self):
        post = AsyncBlogPost()

        with pytest.raises(TypeError):
            await fsm.acan_proceed(post.save)

    async def test_sync_can_proceed_rejects_async_condition(self):
        post = AsyncBlogPost()

        with pytest.raises(TypeError, match="coroutine function"):
            fsm.can_proceed(post.publish_blocked_async)


class AsyncPermissionsTestCase(TestCase):
    async def test_ahas_transition_perm_with_async_callable_allowed(self):
        post = AsyncBlogPost()
        user = AnonymousUser()

        assert await fsm.ahas_transition_perm(post.publish_async_perm_allowed, user)

    async def test_ahas_transition_perm_with_async_callable_denied(self):
        post = AsyncBlogPost()
        user = AnonymousUser()

        assert not await fsm.ahas_transition_perm(post.publish_async_perm_denied, user)

    async def test_ahas_transition_perm_returns_false_for_unavailable_transition(self):
        post = AsyncBlogPost(state=ApplicationState.PUBLISHED)
        user = AnonymousUser()

        assert not await fsm.ahas_transition_perm(post.publish_async_perm_allowed, user)

    async def test_ahas_transition_perm_with_no_permission_required(self):
        post = AsyncBlogPost()
        user = AnonymousUser()

        assert await fsm.ahas_transition_perm(post.publish, user)

    async def test_ahas_transition_perm_with_string_permission(self):
        # String permissions stay sync, delegating to user.has_perm(). This verifies the
        # async path takes that branch without trying to await a string. We use a stub user
        # so the call doesn't hit Django's auth backends (which would touch the DB).
        class _StubUser:
            def has_perm(self, perm, obj=None):
                return perm == "testapp.allowed"

        t_allowed = fsm.Transition(
            method=lambda: None,
            source=ApplicationState.NEW,
            target=ApplicationState.PUBLISHED,
            on_error=None,
            conditions=[],
            permission="testapp.allowed",
            custom={},
        )
        t_denied = fsm.Transition(
            method=lambda: None,
            source=ApplicationState.NEW,
            target=ApplicationState.PUBLISHED,
            on_error=None,
            conditions=[],
            permission="testapp.denied",
            custom={},
        )

        assert await t_allowed.ahas_perm(AsyncBlogPost(), _StubUser())
        assert not await t_denied.ahas_perm(AsyncBlogPost(), _StubUser())

    async def test_sync_has_transition_perm_rejects_async_permission(self):
        post = AsyncBlogPost()
        user = AnonymousUser()

        with pytest.raises(TypeError, match="coroutine function"):
            fsm.has_transition_perm(post.publish_async_perm_allowed, user)


class AsyncGetStateTestCase(TestCase):
    async def test_async_get_state_returns_target(self):
        m = AsyncGetStateModel()

        await m.moderate(allow=True)

        assert m.state == ApplicationState.PUBLISHED

    async def test_async_get_state_returns_other_target(self):
        m = AsyncGetStateModel()

        await m.moderate(allow=False)

        assert m.state == ApplicationState.REJECTED

    async def test_async_get_state_invalid_result_raises(self):
        async def bad_target(_instance):
            return "not-a-known-state"

        class _Model(models.Model):
            state = fsm.FSMField(default=ApplicationState.NEW)

            class Meta:
                app_label = "testapp"

            @fsm.atransition(
                field=state,
                source=ApplicationState.NEW,
                target=fsm.GET_STATE(
                    bad_target,
                    states=[ApplicationState.PUBLISHED],
                ),
            )
            async def go(self):
                pass

        m = _Model()
        with pytest.raises(fsm.InvalidResultState):
            await m.go()

    async def test_return_value_works_on_async_transition(self):
        m = AsyncGetStateModel()

        await m.publish_or_reject(accept=True)

        assert m.state == ApplicationState.PUBLISHED

    async def test_sync_get_state_rejects_async_func(self):
        target = fsm.GET_STATE(_async_target, states=[ApplicationState.PUBLISHED])

        with pytest.raises(TypeError, match="coroutine function"):
            target.get_state(AsyncGetStateModel(), None, args=(True,), kwargs={})


class AsyncSignalsTestCase(TestCase):
    def setUp(self):
        self.pre_called = False
        self.post_called = False
        self.async_pre_called = False
        self.async_post_called = False
        self.exception_seen = None

        def on_pre(sender, instance, source, target, **kwargs):
            assert instance.state == source
            self.pre_called = True

        def on_post(sender, instance, source, target, exception=None, **kwargs):
            self.post_called = True
            self.exception_seen = exception

        async def on_pre_async(sender, instance, source, target, **kwargs):
            self.async_pre_called = True

        async def on_post_async(sender, instance, source, target, **kwargs):
            self.async_post_called = True

        self._on_pre = on_pre
        self._on_post = on_post
        self._on_pre_async = on_pre_async
        self._on_post_async = on_post_async

        pre_transition.connect(on_pre, sender=AsyncBlogPost)
        post_transition.connect(on_post, sender=AsyncBlogPost)
        pre_transition.connect(on_pre_async, sender=AsyncBlogPost)
        post_transition.connect(on_post_async, sender=AsyncBlogPost)

    def tearDown(self):
        pre_transition.disconnect(self._on_pre, sender=AsyncBlogPost)
        post_transition.disconnect(self._on_post, sender=AsyncBlogPost)
        pre_transition.disconnect(self._on_pre_async, sender=AsyncBlogPost)
        post_transition.disconnect(self._on_post_async, sender=AsyncBlogPost)

    async def test_async_path_fires_sync_and_async_receivers(self):
        post = AsyncBlogPost()

        await post.publish()

        assert self.pre_called
        assert self.post_called
        assert self.async_pre_called
        assert self.async_post_called

    async def test_async_path_post_signal_carries_exception(self):
        post = AsyncBlogPost(state=ApplicationState.PUBLISHED)

        with pytest.raises(RuntimeError, match="boom"):
            await post.hide_with_failure()

        assert self.pre_called
        assert self.post_called
        assert isinstance(self.exception_seen, RuntimeError)

    async def test_async_path_signals_not_fired_when_transition_not_allowed(self):
        post = AsyncBlogPost(state=ApplicationState.PUBLISHED)

        with pytest.raises(fsm.TransitionNotAllowed):
            await post.publish()

        assert not self.pre_called
        assert not self.post_called


class AsyncMultiDecoratorTestCase(TestCase):
    async def test_multi_decorated_async_method_advances_through_states(self):
        m = AsyncMultiDecoratedModel()

        await m.step()
        assert m.state == ApplicationState.PUBLISHED
        assert m.counter == 1

        await m.step()
        assert m.state == ApplicationState.HIDDEN
        assert m.counter == 2  # noqa: PLR2004

    async def test_multi_decorated_async_method_is_coroutine_function(self):
        assert inspect.iscoroutinefunction(AsyncMultiDecoratedModel.step)


class DecoratorMismatchTestCase(TestCase):
    async def test_transition_rejects_async_method(self):
        state = fsm.FSMField(default=ApplicationState.NEW)

        with pytest.raises(TypeError, match="coroutine function"):

            @fsm.transition(
                field=state,
                source=ApplicationState.NEW,
                target=ApplicationState.PUBLISHED,
            )
            async def publish(self):
                pass

    async def test_atransition_rejects_sync_method(self):
        state = fsm.FSMField(default=ApplicationState.NEW)

        with pytest.raises(TypeError, match="not a coroutine function"):

            @fsm.atransition(
                field=state,
                source=ApplicationState.NEW,
                target=ApplicationState.PUBLISHED,
            )
            def publish(self):
                pass

    async def test_atransition_then_transition_mix_rejected(self):
        # Inner @atransition installs async wrapper, outer @transition sees a coroutine
        # function and refuses.
        state = fsm.FSMField(default=ApplicationState.NEW)

        with pytest.raises(TypeError, match="coroutine function"):

            @fsm.transition(
                field=state,
                source=ApplicationState.PUBLISHED,
                target=ApplicationState.HIDDEN,
            )
            @fsm.atransition(
                field=state,
                source=ApplicationState.NEW,
                target=ApplicationState.PUBLISHED,
            )
            async def step(self):
                pass

    async def test_transition_then_atransition_mix_rejected(self):
        # Inner @transition installs sync wrapper, outer @atransition sees a non-coroutine
        # function and refuses.
        state = fsm.FSMField(default=ApplicationState.NEW)

        with pytest.raises(TypeError, match="not a coroutine function"):

            @fsm.atransition(
                field=state,
                source=ApplicationState.PUBLISHED,
                target=ApplicationState.HIDDEN,
            )
            @fsm.transition(
                field=state,
                source=ApplicationState.NEW,
                target=ApplicationState.PUBLISHED,
            )
            def step(self):
                pass


class AsyncIterationTestCase(TestCase):
    async def test_aget_available_transitions_filters_by_async_condition(self):
        # New post: publish + publish_with_mixed_conditions allowed, publish_blocked_async blocked
        post = AsyncBlogPost()

        names = {t.name async for t in post.aget_available_state_transitions()}

        assert "publish" in names
        assert "publish_with_mixed_conditions" in names
        assert "publish_blocked_async" not in names

    async def test_aget_available_transitions_empty_when_state_terminal(self):
        post = AsyncBlogPost(state=ApplicationState.HIDDEN)

        names = {t.name async for t in post.aget_available_state_transitions()}

        assert names == set()

    async def test_aget_available_user_transitions_filters_by_async_permission(self):
        post = AsyncBlogPost()
        user = AnonymousUser()

        names = {t.name async for t in post.aget_available_user_state_transitions(user)}

        # publish has no permission requirement and async conditions all pass.
        assert "publish" in names
        # async permission allow: included
        assert "publish_async_perm_allowed" in names
        # async permission deny: excluded
        assert "publish_async_perm_denied" not in names
        # async condition False: excluded
        assert "publish_blocked_async" not in names

    async def test_get_all_field_transitions_unchanged_for_async_model(self):
        # The sync get_all_FIELD_transitions doesn't evaluate conditions, so it
        # still works on a model with async conditions.
        post = AsyncBlogPost()

        names = {t.name for t in post.get_all_state_transitions()}

        assert {"publish", "publish_blocked_async", "publish_async_perm_allowed"} <= names


class AsyncGraphTransitionsTestCase(TestCase):
    async def test_generate_dot_walks_async_transitions(self):
        fields = all_fsm_fields_data(AsyncBlogPost)
        dot = str(generate_dot(fields))

        # Edges for several async transitions should be present.
        assert "publish" in dot
        assert "publish_blocked_async" in dot
        assert "hide_with_failure" in dot


class ArefreshFromDbTestCase(TestCase):
    async def test_arefresh_from_db_reads_back_state(self):
        instance = AsyncRefreshableProtected()
        await instance.asave()

        # Mutate state behind the instance's back via another fetch + transition.
        other = await AsyncRefreshableProtected.objects.aget(pk=instance.pk)
        await other.publish()
        await other.asave()

        assert instance.state == ApplicationState.NEW
        await instance.arefresh_from_db()
        assert instance.state == ApplicationState.PUBLISHED

    async def test_arefresh_from_db_preserves_protected_flag(self):
        instance = AsyncRefreshableProtected()
        await instance.asave()

        await instance.arefresh_from_db()

        # After refresh, direct assignment must still be blocked.
        with pytest.raises(AttributeError):
            instance.state = "anything"


class AsyncDeferredFieldTestCase(TestCase):
    async def test_deferred_state_field_loads_on_async_transition(self):
        await AsyncDeferrableModel.objects.acreate()

        # Fetch with state deferred. Accessing state attribute synchronously inside an
        # async context would raise SynchronousOnlyOperation; the async path must use
        # aget_state, which loads the deferred field via arefresh_from_db.
        instance = await AsyncDeferrableModel.objects.only("id").aget()

        assert "state" not in instance.__dict__  # confirm field really is deferred

        await instance.publish()

        assert instance.state == ApplicationState.PUBLISHED

    async def test_acan_proceed_loads_deferred_state(self):
        await AsyncDeferrableModel.objects.acreate()
        instance = await AsyncDeferrableModel.objects.only("id").aget()

        assert "state" not in instance.__dict__
        assert await fsm.acan_proceed(instance.publish)
        # The check populated the field.
        assert instance.state == ApplicationState.NEW


class AsyncDjangoFsmLogInteropTestCase(TestCase):
    async def test_async_transition_writes_state_log(self):
        # Local import: django_fsm_log is only exercised by this one test, so the import
        # stays out of the module-level surface to avoid forcing the dep on collection.
        # Verifies that sync signal receivers (here, django_fsm_log's) fire correctly
        # when the transition dispatches via Signal.asend(). Django runs sync receivers
        # in a threadpool, so the receiver's manager.create() lands a real row.
        from django_fsm_log.models import StateLog

        instance = AsyncLoggedModel()
        await instance.asave()

        await instance.publish()
        await instance.asave()

        logs = await sync_to_async(list)(StateLog.objects.filter(transition="publish"))

        assert len(logs) == 1
        assert logs[0].source_state == ApplicationState.NEW
        assert logs[0].state == ApplicationState.PUBLISHED
