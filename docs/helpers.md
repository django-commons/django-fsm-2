# Helpers

## Transition availability

Use `can_proceed` to check if a transition can run before calling it.

```python
from django_fsm import can_proceed

post = BlogPost.objects.get(pk=1)
if can_proceed(post.publish):
    post.publish()
    post.save()
```

## Permission helpers

Use `has_transition_perm` to check transition permissions.

See the [Permissions](transitions.md#permissions) section for how to declare
permissions on transitions.

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

## Model helpers

Considering a model with a state field called "FIELD":

- `get_all_FIELD_transitions` enumerates all declared transitions.
- `get_available_FIELD_transitions` returns transitions available in the
  current state.
- `get_available_user_FIELD_transitions` returns transitions available in the
  current state for a given user.

Example: If your state field is called `status`:

```python
my_model_instance.get_all_status_transitions()
my_model_instance.get_available_status_transitions()
my_model_instance.get_available_user_status_transitions()
```
