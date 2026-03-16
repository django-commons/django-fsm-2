# Django friendly finite state machine support

[![CI tests](https://github.com/django-commons/django-fsm-2/actions/workflows/test.yml/badge.svg)](https://github.com/django-commons/django-fsm-2/actions/workflows/test.yml)
[![codecov](https://codecov.io/github/django-commons/django-fsm-2/graph/badge.svg?token=gxsNL3cBl3)](https://codecov.io/github/django-commons/django-fsm-2)
[![Documentation](https://img.shields.io/static/v1?label=Docs&message=READ&color=informational&style=plastic)](https://django-commons.github.io/django-fsm-2/)
[![MIT License](https://img.shields.io/static/v1?label=License&message=MIT&color=informational&style=plastic)](https://github.com/django-commons/anymail-history/LICENSE)

Django FSM-2 adds simple, declarative state management to Django models.

## Introduction

FSM helps structure code and centralize the lifecycle of your models.
Instead of managing a `CharField` manually, FSMFields declare transitions
once with a decorator. These methods can contain side-effects, permissions,
or logic to make lifecycle management easier.

Nice introduction is available here: https://gist.github.com/Nagyman/9502133

> [!IMPORTANT]
> Django FSM-2 is a maintained fork of
> [Django FSM](https://github.com/viewflow/django-fsm).
>
> Big thanks to Mikhail Podgurskiy for starting this project and maintaining
> it for so many years.
>
> Unfortunately, after 2 years without any releases, the project was
> brutally archived. Viewflow is presented as an alternative but the
> transition is not that easy.
>
> If what you need is just a simple state machine, tailor-made for Django,
> Django FSM-2 is the successor of Django FSM, with dependencies updates,
> typing (planned)

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

## Installation

Install the package:

```bash
uv pip install django-fsm-2
```

Or install from git:

```bash
uv pip install -e git://github.com/django-commons/django-fsm-2.git#egg=django-fsm
```

Add `django_fsm` to your Django apps (required to graph transitions or use
admin integration):

```python
INSTALLED_APPS = (
    ...,
    'django_fsm',
    ...,
)
```

> [!IMPORTANT] Migration from django-fsm
>
> Django FSM-2 is a drop-in replacement. Update your dependency from
> `django-fsm` to `django-fsm-2` and keep your existing code.
>
> ```bash
> uv pip install django-fsm-2
> ```

## Documentation

- Docs site: https://django-commons.github.io/django-fsm-2/
- Source: `docs/`

## Contributing

We welcome contributions. See `CONTRIBUTING.md` for detailed setup
instructions.
