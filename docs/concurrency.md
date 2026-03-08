# Concurrency

Use `ConcurrentTransitionMixin` to avoid concurrent state changes. If the
state changed in the database, `django_fsm.ConcurrentTransition` is raised
on `save()`.

```python
from django_fsm import FSMField, ConcurrentTransitionMixin, FSMModelMixin

class BlogPost(ConcurrentTransitionMixin, FSMModelMixin, models.Model):
    state = FSMField(default='new')
```

For guaranteed protection against race conditions caused by concurrently
executed transitions, make sure:

- Your transitions do not have side effects except for database changes.
- You always call `save()` within a `django.db.transaction.atomic()` block.

Following these recommendations, `ConcurrentTransitionMixin` will cause a
rollback of all changes executed in an inconsistent state.
