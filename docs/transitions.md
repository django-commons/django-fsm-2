# Transition definitions

## Core ideas

- Store a state in an `FSMField` (or `FSMIntegerField`/`FSMKeyField`).
- Declare transitions once with the `@transition` decorator.
- Transition methods can contain business logic and side effects.
- The in-memory state changes on success; `save()` persists it.

## Declaring a transition

```python
from django_fsm import transition

@transition(field=state, source='new', target='published')
def publish(self, **kwargs):
    """
    This function may contain side effects,
    like updating caches, notifying users, etc.
    The return value will be discarded.
    """
```

The `field` parameter accepts a string attribute name or a field instance.
If calling `publish()` succeeds without raising an exception, the state
changes in memory. You must call `save()` to persist it.

```python
from django_fsm import can_proceed

def publish_view(request, post_id, **kwargs):
    post = get_object_or_404(BlogPost, pk=post_id)
    if not can_proceed(post.publish):
        raise PermissionDenied

    post.publish()
    post.save()
    return redirect('/')
```

## Source and target states

`source` accepts a list of states, a single state, or a `django_fsm.State`
implementation.

- `source='*'` allows switching to `target` from any state.
- `source='+'` allows switching to `target` from any state except `target`.

`target` can be a specific state or a `django_fsm.State` implementation.

## Preconditions (conditions)

Use `conditions` to restrict transitions. Each function receives the
instance and must return truthy/falsey. The functions should not have
side effects.

```python
def can_publish(instance):
    # No publishing after 17 hours
    return datetime.datetime.now().hour <= 17

class XXX(FSMModelMixin, models.Model):
    @transition(
        field=state,
        source='new',
        target='published',
        conditions=[can_publish]
    )
    def publish(self, **kwargs):
        pass
```

You can also use model methods:

```python
class XXX(FSMModelMixin, models.Model):
    def can_destroy(self):
        return self.is_under_investigation()

    @transition(
        field=state,
        source='*',
        target='destroyed',
        conditions=[can_destroy]
    )
    def destroy(self, **kwargs):
        pass
```

## Permissions

Attach permissions to transitions with the `permission` argument. It accepts
a permission string or a callable that receives `(instance, user)`.

```python
@transition(
    field=state,
    source='*',
    target='published',
    permission=lambda instance, user: not user.has_perm('myapp.can_make_mistakes'),
)
def publish(self, **kwargs):
    pass

@transition(
    field=state,
    source='*',
    target='removed',
    permission='myapp.can_remove_post',
)
def remove(self, **kwargs):
    pass
```

Check permission with `has_transition_perm`:

```python
from django_fsm import has_transition_perm

def publish_view(request, post_id):
    post = get_object_or_404(BlogPost, pk=post_id)
    if not has_transition_perm(post.publish, request.user):
        raise PermissionDenied

    post.publish()
    post.save()
    return redirect('/')
```

## Dynamic targets

Use `RETURN_VALUE` or `GET_STATE` to compute a target state at runtime.

```python
from django_fsm import FSMField, transition, RETURN_VALUE, GET_STATE

@transition(
    field=state,
    source='*',
    target=RETURN_VALUE('for_moderators', 'published'),
)
def publish(self, is_public=False, **kwargs):
    return 'for_moderators' if is_public else 'published'

@transition(
    field=state,
    source='for_moderators',
    target=GET_STATE(
        lambda self, allowed: 'published' if allowed else 'rejected',
        states=['published', 'rejected'],
    ),
)
def moderate(self, allowed, **kwargs):
    pass

@transition(
    field=state,
    source='for_moderators',
    target=GET_STATE(
        lambda self, **kwargs: 'published' if kwargs.get('allowed', True) else 'rejected',
        states=['published', 'rejected'],
    ),
)
def moderate(self, allowed=True, **kwargs):
    pass
```

## Custom transition metadata

Use `custom` to attach arbitrary data to a transition.

```python
@transition(
    field=state,
    source='*',
    target='onhold',
    custom=dict(verbose='Hold for legal reasons'),
)
def legal_hold(self, **kwargs):
    pass
```

## Error target state

If a transition method raises an exception, you can specify an `on_error`
state.

```python
@transition(
    field=state,
    source='new',
    target='published',
    on_error='failed'
)
def publish(self, **kwargs):
    """
    Some exception could happen here
    """
```
