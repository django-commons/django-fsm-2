# Installation

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

## Migration from django-fsm

Django FSM-2 is a drop-in replacement. Update your dependency from
`django-fsm` to `django-fsm-2` and keep your existing code.

```bash
uv pip install django-fsm-2
```
