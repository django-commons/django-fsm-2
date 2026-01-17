# Django FSM RX - Remanufactured Finite State Machine

[![CI tests](https://github.com/specialorange/django-fsm-rx/actions/workflows/test.yml/badge.svg)](https://github.com/specialorange/django-fsm-rx/actions/workflows/test.yml)
[![MIT License](https://img.shields.io/static/v1?label=License&message=MIT&color=informational&style=plastic)](https://github.com/specialorange/django-fsm-rx/LICENSE)

Django-fsm-rx adds simple declarative state management for Django models.

## What does RX mean?

**RX = Remanufactured**

In the automotive and mechanic shop world, "RX" commonly denotes a remanufactured part - rebuilt to meet or exceed original specifications, often with improvements. This project follows that philosophy: taking the battle-tested django-fsm codebase and remanufacturing it with modern enhancements.

## About This Project

Django FSM RX is an independent fork that combines the best features from the django-fsm ecosystem:

- **Core FSM functionality** from the original [django-fsm](https://github.com/viewflow/django-fsm) by Mikhail Podgurskiy
- **Admin integration** inspired by [django-fsm-admin](https://github.com/gadventures/django-fsm-admin) and [django-fsm-2-admin](https://github.com/coral-li/django-fsm-2-admin)
- **Transition logging** inspired by [django-fsm-log](https://github.com/gizmag/django-fsm-log)
- **Full type hints** for modern Python development

This is a new independent branch, separate from both [Django Commons](https://github.com/django-commons) and [Jazzband](https://github.com/jazzband). The goal is to provide a unified, actively maintained package that combines all essential FSM features in one place.

### Why a new fork?

The original django-fsm was archived after 2 years without releases. While django-fsm-2 under Django Commons continued maintenance, this project takes a different approach by:

1. **Combining features** - Admin, logging, and core FSM in one package
2. **Independent governance** - Not tied to any organization's processes
3. **Opinionated defaults** - Built for mechanic shop / automotive industry workflows

## Installation

```bash
pip install django-fsm-rx
```

Add to your Django settings:

```python
INSTALLED_APPS = [
    ...,
    'django_fsm_rx',
    ...,
]
```

## Migration Guide

### From django-fsm

```bash
pip uninstall django-fsm
pip install django-fsm-rx
```

Your existing `from django_fsm import ...` imports will continue to work (with a deprecation warning). Update imports at your convenience:

```python
# Old (still works)
from django_fsm import FSMField, transition

# New (recommended)
from django_fsm_rx import FSMField, transition
```

### From django-fsm-2

```bash
pip uninstall django-fsm-2
pip install django-fsm-rx
```

Your existing `from django_fsm_2 import ...` imports will continue to work (with a deprecation warning). Update imports at your convenience:

```python
# Old (still works)
from django_fsm_2 import FSMField, transition

# New (recommended)
from django_fsm_rx import FSMField, transition
```

## Quick Start

```python
from django.db import models
from django_fsm_rx import FSMField, transition

class RepairOrder(models.Model):
    state = FSMField(default='intake')

    @transition(field=state, source='intake', target='diagnosis')
    def begin_diagnosis(self):
        """Vehicle moved to diagnostic bay."""
        pass

    @transition(field=state, source='diagnosis', target='awaiting_approval')
    def submit_estimate(self):
        """Estimate ready for customer approval."""
        pass

    @transition(field=state, source='awaiting_approval', target='in_progress')
    def approve_repair(self):
        """Customer approved the repair."""
        pass

    @transition(field=state, source='in_progress', target='complete')
    def complete_repair(self):
        """Repair finished, ready for pickup."""
        pass
```

## Usage

### Basic Transitions

Add an FSMField to your model and use the `transition` decorator:

```python
from django_fsm_rx import FSMField, transition

class BlogPost(models.Model):
    state = FSMField(default='draft')

    @transition(field=state, source='draft', target='published')
    def publish(self):
        """This method may contain side effects."""
        pass
```

Call the transition method to change state:

```python
post = BlogPost()
post.publish()
post.save()  # State change is not persisted until save()
```

### Checking if Transition is Allowed

```python
from django_fsm_rx import can_proceed

if can_proceed(post.publish):
    post.publish()
    post.save()
```

### Conditions

Add conditions that must be met before a transition can occur:

```python
def is_business_hours(instance):
    return 9 <= datetime.now().hour < 17

@transition(field=state, source='draft', target='published', conditions=[is_business_hours])
def publish(self):
    pass
```

### Protected Fields

Prevent direct state assignment:

```python
class BlogPost(FSMModelMixin, models.Model):
    state = FSMField(default='draft', protected=True)

post = BlogPost()
post.state = 'published'  # Raises AttributeError
```

### Source State Options

```python
# From any state
@transition(field=state, source='*', target='cancelled')
def cancel(self):
    pass

# From any state except target
@transition(field=state, source='+', target='reset')
def reset(self):
    pass

# From multiple specific states
@transition(field=state, source=['draft', 'review'], target='published')
def publish(self):
    pass
```

### Dynamic Target State

```python
from django_fsm_rx import RETURN_VALUE, GET_STATE

@transition(field=state, source='review', target=RETURN_VALUE('published', 'rejected'))
def moderate(self, approved):
    return 'published' if approved else 'rejected'

@transition(
    field=state,
    source='review',
    target=GET_STATE(
        lambda self, approved: 'published' if approved else 'rejected',
        states=['published', 'rejected']
    )
)
def moderate(self, approved):
    pass
```

### Permissions

```python
@transition(field=state, source='draft', target='published', permission='blog.can_publish')
def publish(self):
    pass

@transition(
    field=state,
    source='*',
    target='deleted',
    permission=lambda instance, user: user.is_superuser
)
def delete(self):
    pass
```

Check permissions:

```python
from django_fsm_rx import has_transition_perm

if has_transition_perm(post.publish, user):
    post.publish()
    post.save()
```

### Error Handling

Specify a fallback state if transition raises an exception:

```python
@transition(field=state, source='processing', target='complete', on_error='failed')
def process(self):
    # If this raises, state becomes 'failed'
    do_risky_operation()
```

### Signals

```python
from django_fsm_rx.signals import pre_transition, post_transition

@receiver(pre_transition)
def on_pre_transition(sender, instance, name, source, target, **kwargs):
    print(f"{instance} transitioning from {source} to {target}")

@receiver(post_transition)
def on_post_transition(sender, instance, name, source, target, **kwargs):
    print(f"{instance} transitioned to {target}")
```

### Optimistic Locking

Prevent concurrent state changes:

```python
from django_fsm_rx import ConcurrentTransitionMixin

class BlogPost(ConcurrentTransitionMixin, models.Model):
    state = FSMField(default='draft')
```

### Integer States

```python
class OrderStatus:
    PENDING = 10
    PROCESSING = 20
    SHIPPED = 30

class Order(models.Model):
    status = FSMIntegerField(default=OrderStatus.PENDING)

    @transition(field=status, source=OrderStatus.PENDING, target=OrderStatus.PROCESSING)
    def process(self):
        pass
```

### Foreign Key States

```python
class OrderState(models.Model):
    id = models.CharField(primary_key=True, max_length=50)
    label = models.CharField(max_length=100)

class Order(models.Model):
    state = FSMKeyField(OrderState, default='pending', on_delete=models.PROTECT)
```

### Model Methods

```python
# Get all declared transitions
post.get_all_state_transitions()

# Get transitions available from current state
post.get_available_state_transitions()

# Get transitions available for a specific user
post.get_available_user_state_transitions(user)
```

## Graph Visualization

Generate a visual representation of your state machine:

```bash
# Output as DOT format
python manage.py graph_transitions myapp.BlogPost > states.dot

# Output as PNG
python manage.py graph_transitions -o states.png myapp.BlogPost
```

Requires the `graphviz` package:

```bash
pip install django-fsm-rx[graphviz]
```

## Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md) for detailed setup instructions.

### Quick Development Setup

```bash
# Clone and setup
git clone https://github.com/specialorange/django-fsm-rx.git
cd django-fsm-rx
uv sync

# Run tests
uv run pytest -v

# Run linting
uv run ruff check .
```

## Credits

- **Mikhail Podgurskiy** - Original django-fsm creator
- **Django Commons** - django-fsm-2 maintenance
- **Jazzband** - Original community support
- All contributors to the django-fsm ecosystem

## License

MIT License - see [LICENSE](LICENSE) for details.
