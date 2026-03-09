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
import django_fsm as fsm

class BlogPost(fsm.FSMModelMixin, models.Model):
    state = fsm.FSMField(default='new')

    @fsm.transition(field=state, source='new', target='published')
    def publish(self, **kwargs):
        pass
```

```python
import django_fsm as fsm

post = BlogPost.objects.get(pk=1)
if fsm.can_proceed(post.publish):
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

Add `django_fsm` to your Django apps (required to [graph transitions](#drawing-transitions) or use [Admin integration](#admin-integration)):

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
- Declare transitions once with the `@fsm.transition` decorator.
- Transition methods can contain business logic and side effects.
- The in-memory state changes on success; `save()` persists it.

### Adding an FSM field

```python
import django_fsm as fsm

class BlogPost(fsm.FSMModelMixin, models.Model):
    state = fsm.FSMField(default='new')
```

### Declaring a transition

```python
import django_fsm as fsm

@fsm.transition(field=state, source='new', target='published')
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
import django_fsm as fsm

def publish_view(request, post_id, **kwargs):
    post = get_object_or_404(BlogPost, pk=post_id)
    if not fsm.can_proceed(post.publish):
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
import django_fsm as fsm

def can_publish(instance):
    # No publishing after 17 hours
    return datetime.datetime.now().hour <= 17

class XXX(fsm.FSMModelMixin, models.Model):
    @fsm.transition(
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
import django_fsm as fsm
class XXX(fsm.FSMModelMixin, models.Model):
    def can_destroy(self):
        return self.is_under_investigation()

    @fsm.transition(
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

Because `refresh_from_db` assigns to the field, protected fields raise there
as well unless you use `FSMModelMixin`. Use `FSMModelMixin` by default to
allow refresh without enabling arbitrary writes elsewhere.

```python
import django_fsm as fsm

class BlogPost(fsm.FSMModelMixin, models.Model):
    state = fsm.FSMField(default='new', protected=True)

model = BlogPost()
model.state = 'invalid'  # Raises AttributeError
model.refresh_from_db()  # Works
```

### Source and target states

`source` accepts a list of states, a single state, or a `django_fsm.State`
implementation.

- `source="*"` allows switching to `target` from any state (accessible as ANY_STATE constant).
- `source="+"` allows switching to `target` from any state except `target`(accessible as ANY_OTHER_STATE constant).

`target` can be a specific state or a `django_fsm.State` implementation.

```python
import django_fsm as fsm

@fsm.transition(
    field=state,
    source='*',
    target=fsm.RETURN_VALUE('for_moderators', 'published'),
)
def publish(self, is_public=False, **kwargs):
    return 'for_moderators' if is_public else 'published'

@fsm.transition(
    field=state,
    source='for_moderators',
    target=fsm.GET_STATE(
        lambda self, allowed: 'published' if allowed else 'rejected',
        states=['published', 'rejected'],
    ),
)
def moderate(self, allowed, **kwargs):
    pass

@fsm.transition(
    field=state,
    source='for_moderators',
    target=fsm.GET_STATE(
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
@fsm.transition(
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
@fsm.transition(
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
@fsm.transition(
    field=state,
    source='*',
    target='published',
    permission=lambda instance, user: not user.has_perm('myapp.can_make_mistakes'),
)
def publish(self, **kwargs):
    pass

@fsm.transition(
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
import django_fsm as fsm

def publish_view(request, post_id):
    post = get_object_or_404(BlogPost, pk=post_id)
    if not fsm.has_transition_perm(post.publish, request.user):
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
import django_fsm as fsm
class DbState(fsm.FSMModelMixin, models.Model):
    id = models.CharField(primary_key=True)
    label = models.CharField()

    def __str__(self):
        return self.label


class BlogPost(fsm.FSMModelMixin, models.Model):
    state = fsm.FSMKeyField(DbState, default='new')

    @fsm.transition(field=state, source='new', target='published')
    def publish(self, **kwargs):
        pass
```

In your fixtures/initial_data.json:
```json
[
    {
        "pk": "_NEW_",
        "model": "myapp.dbstate",
        "fields": {
            "label": "New"
        }
    },
    {
        "pk": "_PUBLISHED_",
        "model": "myapp.dbstate",
        "fields": {
            "label": "Published"
        }
    }
]
```

Note: `source` and `target` use the PK values of the `DbState` model as
names, even if the field is accessed without the `_id` postfix.

### FSMIntegerField (enum-style states)

```python
import django_fsm as fsm

class BlogPostStateChoices(models.IntegerChoices):
    NEW = 10, "New"
    PUBLISHED = 20, "Published"
    HIDDEN = 30, "Hidden"

class BlogPostWithIntegerField(fsm.FSMModelMixin, models.Model):
    state = fsm.FSMIntegerField(default=BlogPostStateChoices.NEW)

    @fsm.transition(
        field=state,
        source=BlogPostStateChoices.NEW,
        target=BlogPostStateChoices.PUBLISHED,
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
import django_fsm as fsm

class BlogPost(fsm.ConcurrentTransitionMixin, models.Model):
    state = fsm.FSMField(default='new')
```

For guaranteed protection against race conditions caused by concurrently
executed transitions, make sure:

- Your transitions do not have side effects except for database changes.
- You always call `save()` within a `django.db.transaction.atomic()` block.

Following these recommendations, `ConcurrentTransitionMixin` will cause a
rollback of all changes executed in an inconsistent state.

## Admin Integration

> NB: If you're migrating from [django-fsm-admin](https://github.com/gadventures/django-fsm-admin) (or any alternative), make sure it's not installed anymore to avoid installing the old django-fsm.

Update import path:

``` python
- from django_fsm_admin.mixins import FSMTransitionMixin
+ from django_fsm.admin import FSMAdminMixin
```

1. In your admin.py file, use FSMAdminMixin to add behaviour to your ModelAdmin. FSMAdminMixin should be before ModelAdmin, the order is important.

``` python
from django_fsm.admin import FSMAdminMixin

@admin.register(AdminBlogPost)
class MyAdmin(FSMAdminMixin, admin.ModelAdmin):
    # Declare the fsm fields you want to manage
    fsm_fields = ['my_fsm_field']
    ...
```

2. You can customize the buttons by adding `label` and `help_text` to the `custom` attribute of the transition decorator

``` python
@fsm.transition(
    field='state',
    source=['startstate'],
    target='finalstate',
    custom={
        "label": "My awesome transition",  # this
        "help_text": "Rename blog post",  # and this
    },
)
def do_something(self, **kwargs):
       ...
```

or by overriding some methods in FSMAdminMixin

``` python
from django_fsm.admin import FSMAdminMixin

@admin.register(AdminBlogPost)
class MyAdmin(FSMAdminMixin, admin.ModelAdmin):
    ...

    def get_fsm_label(self, transition):  # this method
        if transition.name == "do_something":
            return "My awesome transition"
        return super().get_fsm_label(transition)

    def get_help_text(self, transition):  # and this method
        if transition.name == "do_something":
            return "Rename blog post"
        return super().get_help_text(transition)
```

3. For forms in the admin transition flow, see the Custom Forms section below.

4. Hiding a transition is possible by adding ``custom={"admin": False}`` to the transition decorator:

``` python
    @fsm.transition(
        field='state',
        source=['startstate'],
        target='finalstate',
        custom={
            "admin": False,  # this
        },
    )
    def do_something(self, **kwargs):
       # will not add a button "Do Something" to your admin model interface
```
or from the admin:

``` python
from django_fsm.admin import FSMAdminMixin

@admin.register(AdminBlogPost)
class MyAdmin(FSMAdminMixin, admin.ModelAdmin):
    ...

    def is_fsm_transition_visible(self, transition: fsm.Transition) -> bool:
        if transition.name == "do_something":
            return False
        return super().is_fsm_transition_visible(transition)

```

NB: By adding `FSM_ADMIN_FORCE_PERMIT = True` to your configuration settings (or `fsm_default_disallow_transition = False` to your admin), the above restriction becomes the default.
Then one must explicitly allow that a transition method shows up in the admin interface using `custom={"admin": True}`

``` python
from django_fsm.admin import FSMAdminMixin

@admin.register(AdminBlogPost)
class MyAdmin(FSMAdminMixin, admin.ModelAdmin):
    fsm_default_disallow_transition = False
    ...
```

### Custom Forms

You can attach a custom form to a transition so the admin prompts for input
before the transition runs. Add a `form` entry to `custom` on the transition,
or define an admin-level mapping via `fsm_forms`. Both accept a `forms.Form`/
`forms.ModelForm` class or a dotted import path.

```python
from django import forms
import django_fsm as fsm

class RenameForm(forms.Form):
    new_title = forms.CharField(max_length=255)
    # it's also possible to declare fsm log description
    description = forms.CharField(max_length=255)

class BlogPost(fsm.FSMModelMixin, models.Model):
    title = models.CharField(max_length=255)
    state = fsm.FSMField(default="created")

    @fsm.transition(
        field=state,
        source="*",
        target="created",
        custom={
            "label": "Rename",
            "help_text": "Rename blog post",
            "form": "path.to.RenameForm",
        },
    )
    def rename(self, new_title, **kwargs):
        self.title = new_title
```

You can also define forms directly on your `ModelAdmin` without touching the
transition definition:

```python
from django_fsm.admin import FSMAdminMixin

from .admin_forms import RenameForm

@admin.register(AdminBlogPost)
class MyAdmin(FSMAdminMixin, admin.ModelAdmin):
    fsm_fields = ["state"]
    fsm_forms = {
        "rename": "path.to.RenameForm",  # use import path
        "rename": RenameForm,  # or FormClass
    }
```

Behavior details:

- When `form` is set, the transition button redirects to a form view instead of
  executing immediately.
- If both are defined, `fsm_forms` on the admin takes precedence over
  `custom["form"]` on the transition.
- On submit, `cleaned_data` is passed to the transition method as keyword
  arguments and the object is saved.
- `RenameForm` receives the current instance automatically.
- You can override the transition form template by setting
  `fsm_transition_form_template` on your `ModelAdmin` (or override globally `templates/django_fsm/fsm_admin_transition_form.html`).

### Unfold support

If you use [Django Unfold](https://github.com/unfoldadmin/django-unfold), this package provide a contrib that contains templates tailored to the Unfold admin UI.

```python
INSTALLED_APPS = (
    ...,
    'unfold',
    'django_fsm.contrib.unfold',
    ...,
)
```

## Transition tracking

Use `@django_fsm.track()` to write state changes to a log table.
By default, it writes to `django_fsm.StateLog` (single table).
If you prefer one table per model, define your own log model and pass it in.
You can also capture `author` and `description` for each transition.

```python
import django_fsm
from django.db import models


@django_fsm.track()
class BlogPost(models.Model):
    state = django_fsm.FSMField(default="new")

    @django_fsm.transition(field=state, source="new", target="published")
    def publish(self):
        pass
```

```python
import django_fsm
from django.db import models


class BlogPostLog(django_fsm.TransitionLogBase):
    post = models.ForeignKey("BlogPost", on_delete=models.CASCADE, related_name="transition_logs")


@django_fsm.track(log_model=BlogPostLog, relation_field="post")
class BlogPost(models.Model):
    state = django_fsm.FSMField(default="new")
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

## Contributing

We welcome contributions. See `CONTRIBUTING.md` for detailed setup
instructions.

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
