"""
State tracking functionality for django models
"""

from __future__ import annotations

import inspect
from functools import partialmethod
from functools import wraps

from django.apps import apps as django_apps
from django.db import models
from django.db.models import Field
from django.db.models.query_utils import DeferredAttribute
from django.db.models.signals import class_prepared

from django_fsm.signals import post_transition
from django_fsm.signals import pre_transition

__all__ = [
    "GET_STATE",
    "RETURN_VALUE",
    "ConcurrentTransition",
    "ConcurrentTransitionMixin",
    "FSMField",
    "FSMFieldMixin",
    "FSMIntegerField",
    "FSMKeyField",
    "TransitionNotAllowed",
    "can_proceed",
    "has_transition_perm",
    "transition",
]


class TransitionNotAllowed(Exception):  # noqa: N818
    """Raised when a transition is not allowed"""

    def __init__(self, *args, **kwargs):
        self.object = kwargs.pop("object", None)
        self.method = kwargs.pop("method", None)
        super().__init__(*args, **kwargs)


class InvalidResultState(Exception):  # noqa: N818
    """Raised when we got invalid result state"""


class ConcurrentTransition(Exception):  # noqa: N818
    """
    Raised when the transition cannot be executed because the
    object has become stale (state has been changed since it
    was fetched from the database).
    """


class Transition:
    def __init__(self, method, source, target, on_error, conditions, permission, custom):
        self.method = method
        self.source = source
        self.target = target
        self.on_error = on_error
        self.conditions = conditions
        self.permission = permission
        self.custom = custom

    @property
    def name(self):
        return self.method.__name__

    def has_perm(self, instance, user):
        if not self.permission:
            return True
        if callable(self.permission):
            return bool(self.permission(instance, user))
        if user.has_perm(self.permission, instance):
            return True
        if user.has_perm(self.permission):
            return True
        return False

    def __hash__(self):
        return hash(self.name)

    def __eq__(self, other):
        if isinstance(other, str):
            return other == self.name
        if isinstance(other, Transition):
            return other.name == self.name

        return False


def get_available_FIELD_transitions(instance, field):  # noqa: N802
    """
    List of transitions available in current model state
    with all conditions met
    """
    curr_state = field.get_state(instance)
    transitions = field.transitions[instance.__class__]

    for transition in transitions.values():
        meta = transition._django_fsm
        if meta.has_transition(curr_state) and meta.conditions_met(instance, curr_state):
            yield meta.get_transition(curr_state)


def get_all_FIELD_transitions(instance, field):  # noqa: N802
    """
    List of all transitions available in current model state
    """
    return field.get_all_transitions(instance.__class__)


def get_available_user_FIELD_transitions(instance, user, field):  # noqa: N802
    """
    List of transitions available in current model state
    with all conditions met and user have rights on it
    """
    for transition in get_available_FIELD_transitions(instance, field):
        if transition.has_perm(instance, user):
            yield transition


class FSMMeta:
    """
    Models methods transitions meta information
    """

    def __init__(self, field, method):
        self.field = field
        self.transitions = {}  # source -> Transition

    def get_transition(self, source):
        transition = self.transitions.get(source, None)
        if transition is None:
            transition = self.transitions.get("*", None)
        if transition is None:
            transition = self.transitions.get("+", None)
        return transition

    def add_transition(self, method, source, target, on_error=None, conditions=[], permission=None, custom={}):
        if source in self.transitions:
            raise AssertionError(f"Duplicate transition for {source} state")

        self.transitions[source] = Transition(
            method=method,
            source=source,
            target=target,
            on_error=on_error,
            conditions=conditions,
            permission=permission,
            custom=custom,
        )

    def has_transition(self, state):
        """
        Lookup if any transition exists from current model state using current method
        """
        if state in self.transitions:
            return True

        if "*" in self.transitions:
            return True

        if "+" in self.transitions and self.transitions["+"].target != state:
            return True

        return False

    def conditions_met(self, instance, state):
        """
        Check if all conditions have been met
        """
        transition = self.get_transition(state)

        if transition is None:
            return False

        if transition.conditions is None:
            return True

        return all(condition(instance) for condition in transition.conditions)

    def has_transition_perm(self, instance, state, user):
        transition = self.get_transition(state)

        if not transition:
            return False

        return transition.has_perm(instance, user)

    def next_state(self, current_state):
        transition = self.get_transition(current_state)

        if transition is None:
            raise TransitionNotAllowed(f"No transition from {current_state}")

        return transition.target

    def exception_state(self, current_state):
        transition = self.get_transition(current_state)

        if transition is None:
            raise TransitionNotAllowed(f"No transition from {current_state}")

        return transition.on_error


class FSMFieldDescriptor:
    def __init__(self, field):
        self.field = field

    def __get__(self, instance, instance_type=None):
        if instance is None:
            return self
        return self.field.get_state(instance)

    def __set__(self, instance, value):
        if self.field.protected and self.field.name in instance.__dict__:
            raise AttributeError(f"Direct {self.field.name} modification is not allowed")

        # Update state
        self.field.set_proxy(instance, value)
        self.field.set_state(instance, value)


class FSMFieldMixin:
    descriptor_class = FSMFieldDescriptor

    def __init__(self, *args, **kwargs):
        self.protected = kwargs.pop("protected", False)
        self.transitions = {}  # cls -> (transitions name -> method)
        self.state_proxy = {}  # state -> ProxyClsRef

        state_choices = kwargs.pop("state_choices", None)
        choices = kwargs.get("choices")
        if state_choices is not None and choices is not None:
            raise ValueError("Use one of choices or state_choices value")

        if state_choices is not None:
            choices = []
            for state, title, proxy_cls_ref in state_choices:
                choices.append((state, title))
                self.state_proxy[state] = proxy_cls_ref
            kwargs["choices"] = choices

        super().__init__(*args, **kwargs)

    def deconstruct(self):
        name, path, args, kwargs = super().deconstruct()
        if self.protected:
            kwargs["protected"] = self.protected
        return name, path, args, kwargs

    def get_state(self, instance):
        # The state field may be deferred. We delegate the logic of figuring this out
        # and loading the deferred field on-demand to Django's built-in DeferredAttribute class.
        return DeferredAttribute(self).__get__(instance)

    def set_state(self, instance, state):
        instance.__dict__[self.name] = state

    def set_proxy(self, instance, state):
        """
        Change class
        """
        if state in self.state_proxy:
            state_proxy = self.state_proxy[state]

            try:
                app_label, model_name = state_proxy.split(".")
            except ValueError:
                # If we can't split, assume a model in current app
                app_label = instance._meta.app_label
                model_name = state_proxy

            model = django_apps.get_app_config(app_label).get_model(model_name)

            if model is None:
                raise ValueError(f"No model found {state_proxy}")

            instance.__class__ = model

    def change_state(self, instance, method, *args, **kwargs):
        meta = method._django_fsm
        method_name = method.__name__
        current_state = self.get_state(instance)

        if not meta.has_transition(current_state):
            raise TransitionNotAllowed(
                f"Can't switch from state '{current_state}' using method '{method_name}'",
                object=instance,
                method=method,
            )
        if not meta.conditions_met(instance, current_state):
            raise TransitionNotAllowed(
                f"Transition conditions have not been met for method '{method_name}'", object=instance, method=method
            )

        next_state = meta.next_state(current_state)

        signal_kwargs = {
            "sender": instance.__class__,
            "instance": instance,
            "name": method_name,
            "field": meta.field,
            "source": current_state,
            "target": next_state,
            "method_args": args,
            "method_kwargs": kwargs,
        }

        pre_transition.send(**signal_kwargs)

        try:
            result = method(instance, *args, **kwargs)
            if next_state is not None:
                if hasattr(next_state, "get_state"):
                    next_state = next_state.get_state(instance, transition, result, args=args, kwargs=kwargs)
                    signal_kwargs["target"] = next_state
                self.set_proxy(instance, next_state)
                self.set_state(instance, next_state)
        except Exception as exc:
            exception_state = meta.exception_state(current_state)
            if exception_state:
                self.set_proxy(instance, exception_state)
                self.set_state(instance, exception_state)
                signal_kwargs["target"] = exception_state
                signal_kwargs["exception"] = exc
                post_transition.send(**signal_kwargs)
            raise
        else:
            post_transition.send(**signal_kwargs)

        return result

    def get_all_transitions(self, instance_cls):
        """
        Returns [(source, target, name, method)] for all field transitions
        """
        transitions = self.transitions[instance_cls]

        for transition in transitions.values():
            meta = transition._django_fsm

            yield from meta.transitions.values()

    def contribute_to_class(self, cls, name, **kwargs):
        self.base_cls = cls

        super().contribute_to_class(cls, name, **kwargs)
        setattr(cls, self.name, self.descriptor_class(self))
        setattr(cls, f"get_all_{self.name}_transitions", partialmethod(get_all_FIELD_transitions, field=self))
        setattr(cls, f"get_available_{self.name}_transitions", partialmethod(get_available_FIELD_transitions, field=self))
        setattr(
            cls,
            f"get_available_user_{self.name}_transitions",
            partialmethod(get_available_user_FIELD_transitions, field=self),
        )

        class_prepared.connect(self._collect_transitions)

    def _collect_transitions(self, *args, **kwargs):
        sender = kwargs["sender"]

        if not issubclass(sender, self.base_cls):
            return

        def is_field_transition_method(attr):
            return (
                (inspect.ismethod(attr) or inspect.isfunction(attr))
                and hasattr(attr, "_django_fsm")
                and (
                    attr._django_fsm.field in [self, self.name]
                    or (
                        isinstance(attr._django_fsm.field, Field)
                        and attr._django_fsm.field.name == self.name
                        and attr._django_fsm.field.creation_counter == self.creation_counter
                    )
                )
            )

        sender_transitions = {}
        transitions = inspect.getmembers(sender, predicate=is_field_transition_method)
        for method_name, method in transitions:
            method._django_fsm.field = self
            sender_transitions[method_name] = method

        self.transitions[sender] = sender_transitions


class FSMField(FSMFieldMixin, models.CharField):
    """
    State Machine support for Django model as CharField
    """

    def __init__(self, *args, **kwargs):
        kwargs.setdefault("max_length", 50)
        super().__init__(*args, **kwargs)


class FSMIntegerField(FSMFieldMixin, models.IntegerField):
    """
    Same as FSMField, but stores the state value in an IntegerField.
    """


class FSMKeyField(FSMFieldMixin, models.ForeignKey):
    """
    State Machine support for Django model
    """

    def get_state(self, instance):
        return instance.__dict__[self.attname]

    def set_state(self, instance, state):
        instance.__dict__[self.attname] = self.to_python(state)


class FSMModelMixin:
    """
    Mixin that allows refresh_from_db for models with fsm protected fields
    """

    def _get_protected_fsm_fields(self):
        def is_fsm_and_protected(f):
            return isinstance(f, FSMFieldMixin) and f.protected

        protected_fields = filter(is_fsm_and_protected, self._meta.concrete_fields)
        return {f.attname for f in protected_fields}

    def refresh_from_db(self, *args, **kwargs):
        fields = kwargs.pop("fields", None)

        # Use provided fields, if not set then reload all non-deferred fields.0
        if not fields:
            deferred_fields = self.get_deferred_fields()
            protected_fields = self._get_protected_fsm_fields()
            skipped_fields = deferred_fields.union(protected_fields)

            fields = [f.attname for f in self._meta.concrete_fields if f.attname not in skipped_fields]

        kwargs["fields"] = fields
        super().refresh_from_db(*args, **kwargs)


class ConcurrentTransitionMixin:
    """
    Protects a Model from undesirable effects caused by concurrently executed transitions,
    e.g. running the same transition multiple times at the same time, or running different
    transitions with the same SOURCE state at the same time.

    This behavior is achieved using an idea based on optimistic locking. No additional
    version field is required though; only the state field(s) is/are used for the tracking.
    This scheme is not that strict as true *optimistic locking* mechanism, it is however
    more lightweight - leveraging the specifics of FSM models.

    Instance of a model based on this Mixin will be prevented from saving into DB if any
    of its state fields (instances of FSMFieldMixin) has been changed since the object
    was fetched from the database. *ConcurrentTransition* exception will be raised in such
    cases.

    For guaranteed protection against such race conditions, make sure:
    * Your transitions do not have any side effects except for changes in the database,
    * You always run the save() method on the object within django.db.transaction.atomic()
    block.

    Following these recommendations, you can rely on ConcurrentTransitionMixin to cause
    a rollback of all the changes that have been executed in an inconsistent (out of sync)
    state, thus practically negating their effect.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._update_initial_state()

    @property
    def state_fields(self):
        return filter(lambda field: isinstance(field, FSMFieldMixin), self._meta.fields)

    def _do_update(self, base_qs, using, pk_val, values, update_fields, forced_update):
        # _do_update is called once for each model class in the inheritance hierarchy.
        # We can only filter the base_qs on state fields (can be more than one!) present in this particular model.

        # Select state fields to filter on
        filter_on = filter(lambda field: field.model == base_qs.model, self.state_fields)

        # state filter will be used to narrow down the standard filter checking only PK
        state_filter = {field.attname: self.__initial_states[field.attname] for field in filter_on}

        updated = super()._do_update(
            base_qs=base_qs.filter(**state_filter),
            using=using,
            pk_val=pk_val,
            values=values,
            update_fields=update_fields,
            forced_update=forced_update,
        )

        # It may happen that nothing was updated in the original _do_update method not because of unmatching state,
        # but because of missing PK. This codepath is possible when saving a new model instance with *preset PK*.
        # In this case Django does not know it has to do INSERT operation, so it tries UPDATE first and falls back to
        # INSERT if UPDATE fails.
        # Thus, we need to make sure we only catch the case when the object *is* in the DB, but with changed state; and
        # mimic standard _do_update behavior otherwise. Django will pick it up and execute _do_insert.
        if not updated and base_qs.filter(pk=pk_val).using(using).exists():
            raise ConcurrentTransition("Cannot save object! The state has been changed since fetched from the database!")

        return updated

    def _update_initial_state(self):
        self.__initial_states = {field.attname: field.value_from_object(self) for field in self.state_fields}

    def refresh_from_db(self, *args, **kwargs):
        super().refresh_from_db(*args, **kwargs)
        self._update_initial_state()

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        self._update_initial_state()


def transition(field, source="*", target=None, on_error=None, conditions=[], permission=None, custom={}):
    """
    Method decorator to mark allowed transitions.

    Set target to None if current state needs to be validated and
    has not changed after the function call.
    """

    def inner_transition(func):
        wrapper_installed, fsm_meta = True, getattr(func, "_django_fsm", None)
        if not fsm_meta:
            wrapper_installed = False
            fsm_meta = FSMMeta(field=field, method=func)
            setattr(func, "_django_fsm", fsm_meta)

        if isinstance(source, (list, tuple, set)):
            for state in source:
                func._django_fsm.add_transition(func, state, target, on_error, conditions, permission, custom)
        else:
            func._django_fsm.add_transition(func, source, target, on_error, conditions, permission, custom)

        @wraps(func)
        def _change_state(instance, *args, **kwargs):
            return fsm_meta.field.change_state(instance, func, *args, **kwargs)

        if not wrapper_installed:
            return _change_state

        return func

    return inner_transition


def can_proceed(bound_method, check_conditions=True):  # noqa: FBT002
    """
    Returns True if model in state allows to call bound_method

    Set ``check_conditions`` argument to ``False`` to skip checking
    conditions.
    """
    if not hasattr(bound_method, "_django_fsm"):
        raise TypeError(f"{bound_method.__func__.__name__} method is not transition")

    meta = bound_method._django_fsm
    self = bound_method.__self__
    current_state = meta.field.get_state(self)

    return meta.has_transition(current_state) and (not check_conditions or meta.conditions_met(self, current_state))


def has_transition_perm(bound_method, user):
    """
    Returns True if model in state allows to call bound_method and user have rights on it
    """
    if not hasattr(bound_method, "_django_fsm"):
        raise TypeError(f"{bound_method.__func__.__name__} method is not transition")

    meta = bound_method._django_fsm
    self = bound_method.__self__
    current_state = meta.field.get_state(self)

    return (
        meta.has_transition(current_state)
        and meta.conditions_met(self, current_state)
        and meta.has_transition_perm(self, current_state, user)
    )


class State:
    def get_state(self, model, transition, result, args=[], kwargs={}):
        raise NotImplementedError


class RETURN_VALUE(State):  # noqa: N801
    def __init__(self, *allowed_states):
        self.allowed_states = allowed_states if allowed_states else None

    def get_state(self, model, transition, result, args=[], kwargs={}):
        if self.allowed_states is not None and result not in self.allowed_states:
            raise InvalidResultState(f"{result} is not in list of allowed states\n{self.allowed_states}")
        return result


class GET_STATE(State):  # noqa: N801
    def __init__(self, func, states=None):
        self.func = func
        self.allowed_states = states

    def get_state(self, model, transition, result, args=[], kwargs={}):
        result_state = self.func(model, *args, **kwargs)
        if self.allowed_states is not None and result_state not in self.allowed_states:
            raise InvalidResultState(f"{result_state} is not in list of allowed states\n{self.allowed_states}")
        return result_state
