# Django friendly finite state machine support

[![CI tests](https://github.com/django-commons/django-fsm-2/actions/workflows/test.yml/badge.svg)](https://github.com/django-commons/django-fsm-2/actions/workflows/test.yml)
[![codecov](https://codecov.io/github/django-commons/django-fsm-2/graph/badge.svg?token=gxsNL3cBl3)](https://codecov.io/github/django-commons/django-fsm-2)
[![Documentation](https://img.shields.io/static/v1?label=Docs&message=READ&color=informational&style=plastic)](https://github.com/django-commons/django-fsm-2#usage)
[![MIT License](https://img.shields.io/static/v1?label=License&message=MIT&color=informational&style=plastic)](https://github.com/django-commons/anymail-history/LICENSE)

Django FSM-2 adds simple, declarative state management to Django models.

## Introduction

FSM really helps to structure the code, and centralize the lifecycle of your Models.

Instead of adding a CharField field to a django model and manage its values by hand everywhere, FSMFields offer the ability to declare your transitions once with the decorator. These methods could contain side-effects, permissions, or logic to make the lifecycle management easier.

Nice introduction is available here: https://gist.github.com/Nagyman/9502133

> [!IMPORTANT]
> Django FSM-2 is a maintained fork of [Django FSM](https://github.com/viewflow/django-fsm).
>
> Big thanks to Mikhail Podgurskiy for starting this project and maintaining it for so many years.
>
> Unfortunately, after 2 years without any releases, the project was brutally archived. Viewflow is presented as an alternative but the transition is not that easy.
>
> If what you need is just a simple state machine, tailor-made for Django, Django FSM-2 is the successor of Django FSM, with dependencies updates, typing (planned)

## Quick start

```python
from django.db import models
from django_fsm import FSMField, transition

class BlogPost(models.Model):
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

## Installation

Install the package:

```bash
uv pip install django-fsm-2
```

Or install from git:

```bash
uv pip install -e git://github.com/django-commons/django-fsm-2.git#egg=django-fsm
```

Add `django_fsm` to your Django apps:

```python
INSTALLED_APPS = (
    ...,
    'django_fsm',
    ...,
)
```

> [!IMPORTANT] Migration from django-fsm

Django FSM-2 is a drop-in replacement. Update your dependency from
`django-fsm` to `django-fsm-2` and keep your existing code.

```bash
uv pip install django-fsm-2
```

## Usage

### Core ideas

- Store a state in an `FSMField` (or `FSMIntegerField`/`FSMKeyField`).
- Declare transitions once with the `@transition` decorator.
- Transition methods can contain business logic and side effects.
- The in-memory state changes on success; `save()` persists it.

### Adding an FSM field

```python
from django_fsm import FSMField

class BlogPost(models.Model):
    state = FSMField(default='new')
```

### Declaring a transition

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
changes in memory. **You must call `save()` to persist it**.

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

### Preconditions (conditions)

Use `conditions` to restrict transitions. Each function receives the
instance and must return truthy/falsey. The functions should not have
side effects.

```python
def can_publish(instance):
    # No publishing after 17 hours
    return datetime.datetime.now().hour <= 17

class XXX()
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
class XXX()
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

### Protected state fields

Use `protected=True` to prevent direct assignment. Only transitions may
change the state.

```python
class BlogPost(models.Model):
    state = FSMField(default='new', protected=True)

model = BlogPost()
model.state = 'invalid'  # Raises AttributeError
model.refresh_from_db()  # Raises AttributeError
```

Because `refresh_from_db` assigns to the field, protected fields raise there
as well. Use `FSMModelMixin` to allow refresh without enabling arbitrary
writes elsewhere.

```python
from django_fsm import FSMModelMixin

class BlogPost(FSMModelMixin, models.Model):
    state = FSMField(default='new', protected=True)

model = BlogPost()
model.state = 'invalid'  # Raises AttributeError
model.refresh_from_db()  # Works
```

### Source and target states

`source` accepts a list of states, a single state, or a `django_fsm.State`
implementation.

- `source='*'` allows switching to `target` from any state.
- `source='+'` allows switching to `target` from any state except `target`.

`target` can be a specific state or a `django_fsm.State` implementation.

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

### Custom transition metadata

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

### Error target state

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

### Permissions

Attach permissions to transitions with the `permission` argument. It
accepts a permission string or a callable that receives `(instance, user)`.

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

### Model helpers

Considering a model with a state field called "FIELD"

- `get_all_FIELD_transitions` enumerates all declared transitions.
- `get_available_FIELD_transitions` returns transitions available in the
  current state.
- `get_available_user_FIELD_transitions` returns transitions available in
  the current state for a given user.

Example: If your state field is called `status`

```python
my_model_instance.get_all_status_transitions()
my_model_instance.get_available_status_transitions()
my_model_instance.get_available_user_status_transitions()
```

### FSMKeyField (foreign key support)

Use `FSMKeyField` to store state values in a table and maintain FK
integrity.

```python
class DbState(models.Model):
    id = models.CharField(primary_key=True)
    label = models.CharField()

    def __str__(self):
        return self.label


class BlogPost(models.Model):
    state = FSMKeyField(DbState, default='new')

    @transition(field=state, source='new', target='published')
    def publish(self, **kwargs):
        pass
```

In your fixtures/initial_data.json:
```json
[
    {
        "pk": "new",
        "model": "myapp.dbstate",
        "fields": {
            "label": "_NEW_"
        }
    },
    {
        "pk": "published",
        "model": "myapp.dbstate",
        "fields": {
            "label": "_PUBLISHED_"
        }
    }
]
```

Note: `source` and `target` use the PK values of the `DbState` model as
names, even if the field is accessed without the `_id` postfix.

### FSMIntegerField (enum-style states)

```python
class BlogPostStateEnum(object):
    NEW = 10
    PUBLISHED = 20
    HIDDEN = 30

class BlogPostWithIntegerField(models.Model):
    state = FSMIntegerField(default=BlogPostStateEnum.NEW)

    @transition(
        field=state,
        source=BlogPostStateEnum.NEW,
        target=BlogPostStateEnum.PUBLISHED,
    )
    def publish(self, **kwargs):
        pass
```

### Signals

`django_fsm.signals.pre_transition` and `django_fsm.signals.post_transition`
fire before and after an allowed transition. No signals fire for invalid
transitions.

Arguments sent with these signals:

- `sender` The model class.
- `instance` The actual instance being processed.
- `name` Transition name.
- `source` Source model state.
- `target` Target model state.

## Optimistic locking

Use `ConcurrentTransitionMixin` to avoid concurrent state changes. If the
state changed in the database, `django_fsm.ConcurrentTransition` is raised
on `save()`.

```python
from django_fsm import FSMField, ConcurrentTransitionMixin

class BlogPost(ConcurrentTransitionMixin, models.Model):
    state = FSMField(default='new')
```

For guaranteed protection against race conditions caused by concurrently
executed transitions, make sure:

- Your transitions do not have side effects except for database changes.
- You always call `save()` within a `django.db.transaction.atomic()` block.

Following these recommendations, `ConcurrentTransitionMixin` will cause a
rollback of all changes executed in an inconsistent state.

## Admin Integration

1. Make sure `django_fsm` is in your `INSTALLED_APPS` settings:

``` python
INSTALLED_APPS = (
    ...
    'django_fsm',
    ...
)
```

NB: If you're migrating from [django-fsm-admin](https://github.com/gadventures/django-fsm-admin) (or any alternative), make sure it's not installed anymore to avoid installing the old django-fsm.


2. In your admin.py file, use FSMTransitionMixin to add behaviour to your ModelAdmin. FSMTransitionMixin should be before ModelAdmin, the order is important.

``` python
from django_fsm.admin import FSMTransitionMixin

@admin.register(AdminBlogPost)
class MyAdmin(FSMTransitionMixin, admin.ModelAdmin):
    fsm_field = ['my_fsm_field']
    ...
```

3. You can customize the label by adding ``custom={"label": "My awesome transition"}`` to the transition decorator

``` python
@transition(
    field='state',
    source=['startstate'],
    target='finalstate',
    custom={"label": False},
)
def do_something(self, param):
       ...
```

4. By adding ``custom={"admin": False}`` to the transition decorator, one can disallow a transition to show up in the admin interface.

``` python
    @transition(
       field='state',
       source=['startstate'],
       target='finalstate',
       custom={"admin": False},
    )
    def do_something(self, param):
       # will not add a button "Do Something" to your admin model interface
```

By adding `FSM_ADMIN_FORCE_PERMIT = True` to your configuration settings (or `default_disallow_transition = False` to your admin), the above restriction becomes the default.
Then one must explicitly allow that a transition method shows up in the admin interface.

``` python
@admin.register(AdminBlogPost)
class MyAdmin(FSMTransitionMixin, admin.ModelAdmin):
    default_disallow_transition = False
    ...
```

## Drawing transitions

Render a graphical overview of your model transitions.

1. Install graphviz support:

```bash
uv pip install django-fsm-2[graphviz]
```

or

```bash
uv pip install "graphviz>=0.4"
```

2. Ensure `django_fsm` is in `INSTALLED_APPS`:

```python
INSTALLED_APPS = (
    ...,
    'django_fsm',
    ...,
)
```

3. Run the management command:

```bash
# Create a dot file
./manage.py graph_transitions > transitions.dot

# Create a PNG image file for a specific model
./manage.py graph_transitions -o blog_transitions.png myapp.Blog

# Exclude some transitions
./manage.py graph_transitions -e transition_1,transition_2 myapp.Blog
```

## Extensions

Transition logging support could be achieved with help of django-fsm-log
package : <https://github.com/gizmag/django-fsm-log>

## Contributing

### Quick Development Setup

```bash
# Clone and setup
git clone https://github.com/django-commons/django-fsm-2.git
cd django-fsm
uv sync

# Run tests
uv run pytest -v
# or
uv run tox

# Run linting
uv run ruff format .
uv run ruff check .
```
