# Django FSM-2

Django FSM-2 adds simple, declarative state management to Django models.

Django FSM-2 is a maintained fork of
[django-fsm](https://github.com/viewflow/django-fsm). It is a drop-in
replacement with updated dependencies and ongoing maintenance.

## Quick start

```python
from django.db import models
from django_fsm import FSMField, FSMModelMixin, transition

class BlogPost(FSMModelMixin, models.Model):
    state = FSMField(default='new')

    @transition(field=state, source='new', target='published')
    def publish(self, **kwargs):
        pass
```

```python
from django_fsm import can_proceed

post = BlogPost.objects.get(pk=1)
if can_proceed(post.publish):
    post.publish()
    post.save()
```

## What next

- Start with the [Installation](installation.md) guide.
- Read the [Fields](fields.md) and [Transitions](transitions.md) docs for core concepts.
- When you are ready, check [Admin Integration](admin.md) or
  [Graphing](graphing.md).
