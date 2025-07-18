# Django friendly finite state machine support

[![CI tests](https://github.com/django-commons/django-fsm-2/actions/workflows/test.yml/badge.svg)](https://github.com/django-commons/django-fsm-2/actions/workflows/test.yml)
[![codecov](https://codecov.io/github/django-commons/django-fsm-2/graph/badge.svg?token=gxsNL3cBl3)](https://codecov.io/github/django-commons/django-fsm-2)
[![Documentation](https://img.shields.io/static/v1?label=Docs&message=READ&color=informational&style=plastic)](https://github.com/django-commons/django-fsm-2#settings)
[![MIT License](https://img.shields.io/static/v1?label=License&message=MIT&color=informational&style=plastic)](https://github.com/django-commons/anymail-history/LICENSE)


django-fsm adds simple declarative state management for django models.

> [!IMPORTANT]
> Django FSM-2 is a maintained fork of [Django FSM](https://github.com/viewflow/django-fsm).
>
> Big thanks to Mikhail Podgurskiy for starting this awesome project and maintaining it for so many years.
>
> Unfortunately, after 2 years without any releases, the project was brutally archived. [Viewflow](https://github.com/viewflow/viewflow) is presented as an alternative but the transition is not that easy.
>
> If what you need is just a simple state machine, tailor-made for Django, Django FSM-2 is the successor of Django FSM, with dependencies updates, typing (planned)

## Introduction

**FSM really helps to structure the code, and centralize the lifecycle of your Models.**

Instead of adding a CharField field to a django model and manage its
values by hand everywhere, `FSMFields` offer the ability to declare your
`transitions` once with the decorator. These methods could contain side-effects, permissions, or logic to make the lifecycle management easier.

Nice introduction is available here: <https://gist.github.com/Nagyman/9502133>

## Installation

First, install the package with pip.

``` bash
$ pip install django-fsm-2
```

Or, for the latest git version

``` bash
$ pip install -e git://github.com/django-commons/django-fsm-2.git#egg=django-fsm
```

Register django_fsm in your list of Django applications

```python
INSTALLED_APPS = (
    ...,
    'django_fsm',
    ...,
)
```

## Migration from django-fsm

django-fsm-2 is a drop-in replacement, it's actually the same project but from a different source.
So all you need to do is to replace `django-fsm` dependency with `django-fsm-2`. And voila!

``` bash
$ pip install django-fsm-2
```


## Usage

Add FSMState field to your model

``` python
from django_fsm import FSMField, transition

class BlogPost(models.Model):
    state = FSMField(default='new')
```

Use the `transition` decorator to annotate model methods

``` python
@transition(field=state, source='new', target='published')
def publish(self):
    """
    This function may contain side-effects,
    like updating caches, notifying users, etc.
    The return value will be discarded.
    """
```

The `field` parameter accepts both a string attribute name or an actual
field instance.

If calling publish() succeeds without raising an exception, the state
field will be changed, but not written to the database.

``` python
from django_fsm import can_proceed

def publish_view(request, post_id):
    post = get_object_or_404(BlogPost, pk=post_id)
    if not can_proceed(post.publish):
        raise PermissionDenied

    post.publish()
    post.save()
    return redirect('/')
```

If some conditions are required to be met before changing the state, use
the `conditions` argument to `transition`. `conditions` must be a list
of functions taking one argument, the model instance. The function must
return either `True` or `False` or a value that evaluates to `True` or
`False`. If all functions return `True`, all conditions are considered
to be met and the transition is allowed to happen. If one of the
functions returns `False`, the transition will not happen. These
functions should not have any side effects.

You can use ordinary functions

``` python
def can_publish(instance):
    # No publishing after 17 hours
    if datetime.datetime.now().hour > 17:
        return False
    return True
```

Or model methods

``` python
def can_destroy(self):
    return self.is_under_investigation()
```

Use the conditions like this:

``` python
@transition(field=state, source='new', target='published', conditions=[can_publish])
def publish(self):
    """
    Side effects galore
    """

@transition(field=state, source='*', target='destroyed', conditions=[can_destroy])
def destroy(self):
    """
    Side effects galore
    """
```

You can instantiate a field with `protected=True` option to prevent
direct state field modification.

``` python
class BlogPost(models.Model):
    state = FSMField(default='new', protected=True)

model = BlogPost()
model.state = 'invalid' # Raises AttributeError
```

Note that calling
[refresh_from_db](https://docs.djangoproject.com/en/1.8/ref/models/instances/#django.db.models.Model.refresh_from_db)
on a model instance with a protected FSMField will cause an exception.

### `source` state

`source` parameter accepts a list of states, or an individual state or
`django_fsm.State` implementation.

You can use `*` for `source` to allow switching to `target` from any
state.

You can use `+` for `source` to allow switching to `target` from any
state excluding `target` state.

### `target` state

`target` state parameter could point to a specific state or
`django_fsm.State` implementation

``` python
from django_fsm import FSMField, transition, RETURN_VALUE, GET_STATE
@transition(field=state,
            source='*',
            target=RETURN_VALUE('for_moderators', 'published'))
def publish(self, is_public=False):
    return 'for_moderators' if is_public else 'published'

@transition(
    field=state,
    source='for_moderators',
    target=GET_STATE(
        lambda self, allowed: 'published' if allowed else 'rejected',
        states=['published', 'rejected']))
def moderate(self, allowed):
    pass

@transition(
    field=state,
    source='for_moderators',
    target=GET_STATE(
        lambda self, **kwargs: 'published' if kwargs.get("allowed", True) else 'rejected',
        states=['published', 'rejected']))
def moderate(self, allowed=True):
    pass
```

### `custom` properties

Custom properties can be added by providing a dictionary to the `custom`
keyword on the `transition` decorator.

``` python
@transition(field=state,
            source='*',
            target='onhold',
            custom=dict(verbose='Hold for legal reasons'))
def legal_hold(self):
    """
    Side effects galore
    """
```

### `on_error` state

If the transition method raises an exception, you can provide a specific
target state

``` python
@transition(field=state, source='new', target='published', on_error='failed')
def publish(self):
   """
   Some exception could happen here
   """
```

### `state_choices`

Instead of passing a two-item iterable `choices` you can instead use the
three-element `state_choices`, the last element being a string reference
to a model proxy class.

The base class instance would be dynamically changed to the
corresponding Proxy class instance, depending on the state. Even for
queryset results, you will get Proxy class instances, even if the
QuerySet is executed on the base class.

Check the [test
case](https://github.com/kmmbvnr/django-fsm/blob/master/tests/testapp/tests/test_state_transitions.py)
for example usage. Or read about [implementation
internals](http://schinckel.net/2013/06/13/django-proxy-model-state-machine/)

### Permissions

It is common to have permissions attached to each model transition.
`django-fsm` handles this with `permission` keyword on the `transition`
decorator. `permission` accepts a permission string, or callable that
expects `instance` and `user` arguments and returns True if the user can
perform the transition.

``` python
@transition(field=state, source='*', target='published',
            permission=lambda instance, user: not user.has_perm('myapp.can_make_mistakes'))
def publish(self):
    pass

@transition(field=state, source='*', target='removed',
            permission='myapp.can_remove_post')
def remove(self):
    pass
```

You can check permission with `has_transition_permission` method

``` python
from django_fsm import has_transition_perm
def publish_view(request, post_id):
    post = get_object_or_404(BlogPost, pk=post_id)
    if not has_transition_perm(post.publish, request.user):
        raise PermissionDenied

    post.publish()
    post.save()
    return redirect('/')
```

### Model methods

`get_all_FIELD_transitions` Enumerates all declared transitions

`get_available_FIELD_transitions` Returns all transitions data available
in current state

`get_available_user_FIELD_transitions` Enumerates all transitions data
available in current state for provided user

### Foreign Key constraints support

If you store the states in the db table you could use FSMKeyField to
ensure Foreign Key database integrity.

In your model :

``` python
class DbState(models.Model):
    id = models.CharField(primary_key=True)
    label = models.CharField()

    def __str__(self):
        return self.label


class BlogPost(models.Model):
    state = FSMKeyField(DbState, default='new')

    @transition(field=state, source='new', target='published')
    def publish(self):
        pass
```

In your fixtures/initial_data.json :

``` json
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

Note : source and target parameters in \@transition decorator use pk
values of DBState model as names, even if field \"real\" name is used,
without \_id postfix, as field parameter.

### Integer Field support

You can also use `FSMIntegerField`. This is handy when you want to use
enum style constants.

``` python
class BlogPostStateEnum(object):
    NEW = 10
    PUBLISHED = 20
    HIDDEN = 30

class BlogPostWithIntegerField(models.Model):
    state = FSMIntegerField(default=BlogPostStateEnum.NEW)

    @transition(field=state, source=BlogPostStateEnum.NEW, target=BlogPostStateEnum.PUBLISHED)
    def publish(self):
        pass
```

### Signals

`django_fsm.signals.pre_transition` and
`django_fsm.signals.post_transition` are called before and after allowed
transition. No signals on invalid transition are called.

Arguments sent with these signals:

**sender** The model class.

**instance** The actual instance being processed

**name** Transition name

**source** Source model state

**target** Target model state

## Optimistic locking

`django-fsm` provides optimistic locking mixin, to avoid concurrent
model state changes. If model state was changed in database
`django_fsm.ConcurrentTransition` exception would be raised on
model.save()

``` python
from django_fsm import FSMField, ConcurrentTransitionMixin

class BlogPost(ConcurrentTransitionMixin, models.Model):
    state = FSMField(default='new')
```

For guaranteed protection against race conditions caused by concurrently
executed transitions, make sure:

-   Your transitions do not have any side effects except for changes in
    the database,
-   You always run the save() method on the object within
    `django.db.transaction.atomic()` block.

Following these recommendations, you can rely on
ConcurrentTransitionMixin to cause a rollback of all the changes that
have been executed in an inconsistent (out of sync) state, thus
practically negating their effect.

## Drawing transitions

Renders a graphical overview of your models states transitions

1. You need `pip install "graphviz>=0.4"` library

2. Make sure `django_fsm` is in your `INSTALLED_APPS` settings:

``` python
INSTALLED_APPS = (
    ...
    'django_fsm',
    ...
)
```

3. Then you can use `graph_transitions` command:

``` bash
# Create a dot file
$ ./manage.py graph_transitions > transitions.dot

# Create a PNG image file only for specific model
$ ./manage.py graph_transitions -o blog_transitions.png myapp.Blog

# Exclude some transitions
$ ./manage.py graph_transitions -e transition_1,transition_2 myapp.Blog
```

## Extensions

You may also take a look at django-fsm-2-admin project containing a mixin
and template tags to integrate django-fsm-2 state transitions into the
django admin.

<https://github.com/coral-li/django-fsm-2-admin>

Transition logging support could be achieved with help of django-fsm-log
package

<https://github.com/gizmag/django-fsm-log>
