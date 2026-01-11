# Django Friendly Finite State Machine Support

[![CI tests](https://github.com/django-commons/django-fsm-2/actions/workflows/test.yml/badge.svg)](https://github.com/django-commons/django-fsm-2/actions/workflows/test.yml)
[![codecov](https://codecov.io/github/django-commons/django-fsm-2/branch/master/graph/badge.svg?token=GWGDR6AR6D)](https://codecov.io/github/django-commons/django-fsm-2)
[![Documentation](https://img.shields.io/static/v1?label=Docs&message=READ&color=informational&style=plastic)](https://github.com/django-commons/django-fsm-2#settings)
[![MIT License](https://img.shields.io/static/v1?label=License&message=MIT&color=informational&style=plastic)](https://github.com/django-commons/anymail-history/LICENSE)
[![Typed](https://img.shields.io/badge/typed-yes-blue.svg)](https://github.com/django-commons/django-fsm-2)

Django-fsm-2 adds simple declarative state management for Django models with full type hint support.

> [!IMPORTANT]
> Django FSM-2 started as a fork of [Django FSM](https://github.com/viewflow/django-fsm).
>
> Big thanks to Mikhail Podgurskiy for starting this awesome project and maintaining it for so many years.
>
> Unfortunately, development has stalled for almost 2 years and it was officially announced there will be no new releases. [Viewflow](https://github.com/viewflow/viewflow) is presented as an alternative but the transition is not that easy.
>
> If what you need is just a simple state machine, tailor-made for Django, Django FSM-2 is the successor of Django FSM, with dependency updates, full type hints, and active maintenance.

## Table of Contents

- [Introduction](#introduction)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Core Concepts](#core-concepts)
  - [FSMField Types](#fsmfield-types)
  - [Transitions](#transitions)
  - [Conditions](#conditions)
  - [Permissions](#permissions)
- [Advanced Features](#advanced-features)
  - [Protected Fields](#protected-fields)
  - [Dynamic State Resolution](#dynamic-state-resolution)
  - [Error Handling](#error-handling)
  - [Proxy Models with state_choices](#proxy-models-with-state_choices)
  - [Concurrent Transition Protection](#concurrent-transition-protection)
- [Signals](#signals)
- [Model Methods](#model-methods)
- [Type Hints](#type-hints)
- [Visualization](#visualization)
- [Real-World Examples](#real-world-examples)
- [Admin Integration](#admin-integration)
- [FSM Logging](#fsm-logging)
- [Extensions](#extensions)
- [API Reference](#api-reference)

## Introduction

**FSM really helps to structure the code, and centralize the lifecycle of your Models.**

Instead of adding a CharField field to a django model and managing its
values by hand everywhere, `FSMFields` offer the ability to declare your
`transitions` once with the decorator. These methods could contain side-effects, permissions, or logic to make the lifecycle management easier.

Nice introduction is available here: <https://gist.github.com/Nagyman/9502133>

## Installation

```bash
pip install django-fsm-2
```

Or, for the latest git version:

```bash
pip install -e git://github.com/django-commons/django-fsm-2.git#egg=django-fsm-2
```

## Quick Start

```python
from django.db import models
from django_fsm_2 import FSMField, transition, can_proceed

class BlogPost(models.Model):
    state = FSMField(default='draft')
    title = models.CharField(max_length=200)
    content = models.TextField()

    @transition(field=state, source='draft', target='published')
    def publish(self):
        """Publish the blog post."""
        self.published_at = timezone.now()

    @transition(field=state, source='published', target='archived')
    def archive(self):
        """Archive the blog post."""
        pass

# Usage
post = BlogPost(title="Hello World", content="...")
print(post.state)  # 'draft'

if can_proceed(post.publish):
    post.publish()
    post.save()

print(post.state)  # 'published'
```

## Core Concepts

### FSMField Types

Django-fsm-2 provides three field types for different use cases:

#### FSMField (CharField-based)

The most common choice, stores state as a string:

```python
class BlogPost(models.Model):
    state = FSMField(default='draft', max_length=50)
```

#### FSMIntegerField

Stores state as an integer, ideal for enum-style states:

```python
class OrderState:
    PENDING = 1
    PROCESSING = 2
    SHIPPED = 3
    DELIVERED = 4

class Order(models.Model):
    state = FSMIntegerField(default=OrderState.PENDING)

    @transition(field=state, source=OrderState.PENDING, target=OrderState.PROCESSING)
    def process(self):
        pass
```

#### FSMKeyField (ForeignKey-based)

Stores states in a separate table with referential integrity:

```python
class WorkflowState(models.Model):
    id = models.CharField(primary_key=True, max_length=50)
    label = models.CharField(max_length=255)

class Document(models.Model):
    state = FSMKeyField(WorkflowState, default='draft', on_delete=models.PROTECT)

    @transition(field=state, source='draft', target='review')
    def submit_for_review(self):
        pass
```

### Transitions

The `@transition` decorator marks methods that perform state changes:

```python
@transition(field=state, source='new', target='published')
def publish(self):
    """Side effects like notifications can go here."""
    send_notification(self.author, "Your post was published!")
```

#### Source State Options

```python
# Single source state
@transition(field=state, source='draft', target='published')

# Multiple source states
@transition(field=state, source=['draft', 'pending'], target='published')

# Any state (wildcard)
@transition(field=state, source='*', target='cancelled')

# Any state except target (useful for "reset" transitions)
@transition(field=state, source='+', target='draft')
```

### Conditions

Conditions are functions that must return `True` for the transition to proceed:

```python
def is_approved(instance):
    return instance.approval_status == 'approved'

def has_content(instance):
    return bool(instance.content)

class BlogPost(models.Model):
    state = FSMField(default='draft')

    @transition(
        field=state,
        source='draft',
        target='published',
        conditions=[is_approved, has_content]
    )
    def publish(self):
        pass
```

Using model methods as conditions:

```python
class BlogPost(models.Model):
    state = FSMField(default='draft')

    def is_valid(self):
        return self.title and self.content

    @transition(field=state, source='draft', target='published', conditions=[is_valid])
    def publish(self):
        pass
```

### Permissions

Control who can execute transitions:

```python
# Permission string (checks Django permissions)
@transition(
    field=state,
    source='draft',
    target='published',
    permission='blog.can_publish'
)
def publish(self):
    pass

# Callable permission (custom logic)
@transition(
    field=state,
    source='*',
    target='approved',
    permission=lambda instance, user: user.is_staff or instance.author == user
)
def approve(self):
    pass
```

Checking permissions in views:

```python
from django_fsm_2 import has_transition_perm

def publish_view(request, post_id):
    post = get_object_or_404(BlogPost, pk=post_id)

    if not has_transition_perm(post.publish, request.user):
        raise PermissionDenied("You cannot publish this post")

    post.publish()
    post.save()
    return redirect('post_detail', pk=post_id)
```

## Advanced Features

### Protected Fields

Prevent direct field modification:

```python
class BlogPost(models.Model):
    state = FSMField(default='draft', protected=True)

post = BlogPost()
post.state = 'published'  # Raises AttributeError!
```

For models with protected FSM fields that need `refresh_from_db()`:

```python
from django_fsm_2 import FSMField, FSMModelMixin

class BlogPost(FSMModelMixin, models.Model):
    state = FSMField(default='draft', protected=True)

post = BlogPost.objects.get(pk=1)
post.refresh_from_db()  # Works! Protected fields are skipped.
```

### Dynamic State Resolution

#### RETURN_VALUE - Use Method Return

```python
from django_fsm_2 import RETURN_VALUE

class Order(models.Model):
    state = FSMField(default='pending')

    @transition(
        field=state,
        source='pending',
        target=RETURN_VALUE('approved', 'rejected')
    )
    def review(self, approved: bool):
        return 'approved' if approved else 'rejected'

order = Order()
order.review(approved=True)
print(order.state)  # 'approved'
```

#### GET_STATE - Use Callable

```python
from django_fsm_2 import GET_STATE

def determine_priority_state(instance, priority):
    return 'urgent' if priority > 5 else 'normal'

class Task(models.Model):
    state = FSMField(default='new')

    @transition(
        field=state,
        source='new',
        target=GET_STATE(determine_priority_state, states=['urgent', 'normal'])
    )
    def assign(self, priority: int):
        self.priority = priority
```

### Error Handling

Specify a fallback state when exceptions occur:

```python
class Payment(models.Model):
    state = FSMField(default='pending')

    @transition(
        field=state,
        source='pending',
        target='completed',
        on_error='failed'
    )
    def process(self):
        result = payment_gateway.charge(self.amount)
        if not result.success:
            raise PaymentError(result.message)
        self.transaction_id = result.transaction_id

# If process() raises an exception:
# - state becomes 'failed' (not 'completed')
# - the exception is re-raised
# - post_transition signal is sent with exception info
```

### Proxy Models with state_choices

Dynamically change model class based on state:

```python
class BaseDocument(models.Model):
    state = FSMField(
        default='draft',
        state_choices=[
            ('draft', 'Draft', 'DraftDocument'),
            ('published', 'Published', 'PublishedDocument'),
        ]
    )

    class Meta:
        abstract = False

class DraftDocument(BaseDocument):
    class Meta:
        proxy = True

    def edit(self):
        """Only drafts can be edited."""
        pass

class PublishedDocument(BaseDocument):
    class Meta:
        proxy = True

    def get_public_url(self):
        """Only published documents have public URLs."""
        return f"/docs/{self.pk}/"

# When state changes, instance.__class__ changes automatically
doc = BaseDocument.objects.create()
print(type(doc))  # <class 'DraftDocument'>

doc.publish()
doc.save()
print(type(doc))  # <class 'PublishedDocument'>
```

### Concurrent Transition Protection

Prevent race conditions with optimistic locking:

```python
from django.db import transaction
from django_fsm_2 import FSMField, ConcurrentTransitionMixin, ConcurrentTransition

class Order(ConcurrentTransitionMixin, models.Model):
    state = FSMField(default='pending')

    @transition(field=state, source='pending', target='processing')
    def process(self):
        pass

# Safe usage pattern
try:
    with transaction.atomic():
        order = Order.objects.get(pk=1)
        order.process()
        order.save()
except ConcurrentTransition:
    # Another request modified the state - handle accordingly
    order.refresh_from_db()
    messages.error(request, "Order state was modified by another user.")
```

### Custom Properties

Attach metadata to transitions:

```python
@transition(
    field=state,
    source='*',
    target='on_hold',
    custom={
        'verbose': 'Hold for legal review',
        'icon': 'pause',
        'css_class': 'btn-warning'
    }
)
def legal_hold(self):
    pass

# Access custom properties
for transition in post.get_available_state_transitions():
    print(transition.custom.get('verbose'))
    print(transition.custom.get('icon'))
```

## Signals

Django-fsm-2 provides signals for transition lifecycle hooks:

```python
from django.dispatch import receiver
from django_fsm_2.signals import pre_transition, post_transition

@receiver(pre_transition)
def log_transition_start(sender, instance, name, source, target, **kwargs):
    print(f"Starting {name}: {source} -> {target}")

@receiver(post_transition)
def log_transition_complete(sender, instance, name, source, target, **kwargs):
    if 'exception' in kwargs:
        print(f"Transition {name} failed: {kwargs['exception']}")
    else:
        print(f"Completed {name}: {source} -> {target}")

# Filter by model
@receiver(post_transition, sender=BlogPost)
def notify_on_publish(sender, instance, name, target, **kwargs):
    if target == 'published':
        send_notification(instance.author, "Your post is live!")
```

Signal kwargs:
- `sender`: Model class
- `instance`: Model instance
- `name`: Transition method name
- `field`: FSM field instance
- `source`: Original state
- `target`: New state
- `method_args`: Positional args passed to transition
- `method_kwargs`: Keyword args passed to transition
- `exception`: (post_transition only) Exception if on_error was triggered

## Model Methods

FSM fields add helper methods to your models:

```python
post = BlogPost.objects.get(pk=1)

# Get all declared transitions for this field
for t in post.get_all_state_transitions():
    print(f"{t.name}: {t.source} -> {t.target}")

# Get transitions available from current state (conditions checked)
for t in post.get_available_state_transitions():
    print(f"Can {t.name}")

# Get transitions available to a specific user (conditions + permissions)
for t in post.get_available_user_state_transitions(request.user):
    print(f"User can {t.name}")
```

## Type Hints

Django-fsm-2 is fully typed. Type aliases are exported for your convenience:

```python
from django_fsm_2 import (
    StateValue,        # str | int
    ConditionFunc,     # Callable[[Any], bool]
    PermissionFunc,    # Callable[[Any, AbstractBaseUser], bool]
    PermissionType,    # str | PermissionFunc | None
    StateTarget,       # StateValue | State | None
    StateSource,       # StateValue | Sequence[StateValue] | str
    CustomDict,        # dict[str, Any]
)

def my_condition(instance: BlogPost) -> bool:
    return instance.is_valid()

def my_permission(instance: BlogPost, user: User) -> bool:
    return user.is_staff or instance.author == user
```

## Visualization

Generate GraphViz diagrams of your state machines:

```bash
# Install graphviz support
pip install "django-fsm-2[graphviz]"

# Add to INSTALLED_APPS
INSTALLED_APPS = [
    ...
    'django_fsm_2',
    ...
]

# Generate DOT file
./manage.py graph_transitions > transitions.dot

# Generate PNG image
./manage.py graph_transitions -o transitions.png

# Specific model
./manage.py graph_transitions myapp.BlogPost -o blogpost.png

# Different layout
./manage.py graph_transitions -l neato -o transitions.png
```

## Real-World Examples

### E-Commerce Order Workflow

```python
from django.db import models
from django_fsm_2 import FSMField, transition, ConcurrentTransitionMixin

class Order(ConcurrentTransitionMixin, models.Model):
    class State:
        PENDING = 'pending'
        CONFIRMED = 'confirmed'
        PROCESSING = 'processing'
        SHIPPED = 'shipped'
        DELIVERED = 'delivered'
        CANCELLED = 'cancelled'
        REFUNDED = 'refunded'

    state = FSMField(default=State.PENDING, protected=True)
    customer = models.ForeignKey('Customer', on_delete=models.PROTECT)
    total = models.DecimalField(max_digits=10, decimal_places=2)
    tracking_number = models.CharField(max_length=100, blank=True)

    def can_be_cancelled(self):
        return self.state not in [self.State.SHIPPED, self.State.DELIVERED]

    @transition(
        field=state,
        source=State.PENDING,
        target=State.CONFIRMED,
        permission='orders.can_confirm'
    )
    def confirm(self):
        """Confirm the order and reserve inventory."""
        self.reserve_inventory()
        self.send_confirmation_email()

    @transition(
        field=state,
        source=State.CONFIRMED,
        target=State.PROCESSING
    )
    def start_processing(self):
        """Begin order fulfillment."""
        pass

    @transition(
        field=state,
        source=State.PROCESSING,
        target=State.SHIPPED
    )
    def ship(self, tracking_number: str):
        """Ship the order."""
        self.tracking_number = tracking_number
        self.send_shipping_notification()

    @transition(
        field=state,
        source=State.SHIPPED,
        target=State.DELIVERED
    )
    def mark_delivered(self):
        """Mark order as delivered."""
        pass

    @transition(
        field=state,
        source=[State.PENDING, State.CONFIRMED, State.PROCESSING],
        target=State.CANCELLED,
        conditions=[can_be_cancelled]
    )
    def cancel(self, reason: str = ''):
        """Cancel the order."""
        self.release_inventory()
        self.cancellation_reason = reason

    @transition(
        field=state,
        source=[State.DELIVERED, State.CANCELLED],
        target=State.REFUNDED,
        permission='orders.can_refund'
    )
    def refund(self):
        """Process refund."""
        self.process_refund()
```

### Content Publishing Pipeline

```python
from django.db import models
from django.utils import timezone
from django_fsm_2 import FSMField, transition, RETURN_VALUE

class Article(models.Model):
    class State:
        DRAFT = 'draft'
        IN_REVIEW = 'in_review'
        APPROVED = 'approved'
        REJECTED = 'rejected'
        SCHEDULED = 'scheduled'
        PUBLISHED = 'published'
        ARCHIVED = 'archived'

    state = FSMField(default=State.DRAFT)
    title = models.CharField(max_length=200)
    content = models.TextField()
    author = models.ForeignKey('auth.User', on_delete=models.PROTECT)
    reviewer = models.ForeignKey(
        'auth.User', null=True, blank=True,
        on_delete=models.SET_NULL, related_name='reviewed_articles'
    )
    publish_at = models.DateTimeField(null=True, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)

    def has_content(self):
        return len(self.content) >= 100

    def is_author(self, user):
        return self.author == user

    @transition(
        field=state,
        source=State.DRAFT,
        target=State.IN_REVIEW,
        conditions=[has_content],
        permission=is_author
    )
    def submit_for_review(self):
        """Submit article for editorial review."""
        pass

    @transition(
        field=state,
        source=State.IN_REVIEW,
        target=RETURN_VALUE(State.APPROVED, State.REJECTED),
        permission='articles.can_review'
    )
    def review(self, approved: bool, feedback: str = ''):
        """Review the article."""
        self.reviewer = self.current_user  # Set by view
        self.review_feedback = feedback
        return self.State.APPROVED if approved else self.State.REJECTED

    @transition(
        field=state,
        source=[State.APPROVED, State.REJECTED],
        target=State.DRAFT
    )
    def revise(self):
        """Send back for revision."""
        self.reviewer = None

    @transition(
        field=state,
        source=State.APPROVED,
        target=State.SCHEDULED
    )
    def schedule(self, publish_at: timezone.datetime):
        """Schedule for future publication."""
        self.publish_at = publish_at

    @transition(
        field=state,
        source=[State.APPROVED, State.SCHEDULED],
        target=State.PUBLISHED
    )
    def publish(self):
        """Publish immediately."""
        self.published_at = timezone.now()
        self.publish_at = None

    @transition(
        field=state,
        source=State.PUBLISHED,
        target=State.ARCHIVED
    )
    def archive(self):
        """Archive the article."""
        pass
```

### Support Ticket System

```python
from django.db import models
from django_fsm_2 import FSMIntegerField, transition, GET_STATE

class Ticket(models.Model):
    class Priority:
        LOW = 1
        MEDIUM = 2
        HIGH = 3
        CRITICAL = 4

    class State:
        NEW = 10
        TRIAGED = 20
        IN_PROGRESS = 30
        WAITING_CUSTOMER = 40
        RESOLVED = 50
        CLOSED = 60

    state = FSMIntegerField(default=State.NEW)
    priority = models.IntegerField(choices=[
        (Priority.LOW, 'Low'),
        (Priority.MEDIUM, 'Medium'),
        (Priority.HIGH, 'High'),
        (Priority.CRITICAL, 'Critical'),
    ], default=Priority.MEDIUM)
    title = models.CharField(max_length=200)
    description = models.TextField()
    customer = models.ForeignKey('Customer', on_delete=models.PROTECT)
    assignee = models.ForeignKey(
        'auth.User', null=True, blank=True, on_delete=models.SET_NULL
    )
    resolution = models.TextField(blank=True)

    def auto_assign_state(self, assignee):
        """Determine state based on whether ticket is assigned."""
        return self.State.IN_PROGRESS if assignee else self.State.TRIAGED

    @transition(
        field=state,
        source=State.NEW,
        target=GET_STATE(auto_assign_state, states=[State.TRIAGED, State.IN_PROGRESS])
    )
    def triage(self, priority: int, assignee=None):
        """Triage the ticket."""
        self.priority = priority
        self.assignee = assignee

    @transition(
        field=state,
        source=[State.TRIAGED, State.WAITING_CUSTOMER],
        target=State.IN_PROGRESS
    )
    def assign(self, assignee):
        """Assign to support agent."""
        self.assignee = assignee

    @transition(
        field=state,
        source=State.IN_PROGRESS,
        target=State.WAITING_CUSTOMER
    )
    def request_info(self):
        """Request more information from customer."""
        pass

    @transition(
        field=state,
        source=[State.IN_PROGRESS, State.WAITING_CUSTOMER],
        target=State.RESOLVED
    )
    def resolve(self, resolution: str):
        """Mark ticket as resolved."""
        self.resolution = resolution

    @transition(
        field=state,
        source=State.RESOLVED,
        target=State.CLOSED
    )
    def close(self):
        """Close the resolved ticket."""
        pass

    @transition(
        field=state,
        source=[State.RESOLVED, State.CLOSED],
        target=State.IN_PROGRESS
    )
    def reopen(self):
        """Reopen a closed ticket."""
        self.resolution = ''
```

## Admin Integration

Django-fsm-2 includes built-in admin support via `FSMAdminMixin`:

```python
from django.contrib import admin
from django_fsm_2.admin import FSMAdminMixin
from myapp.models import BlogPost

@admin.register(BlogPost)
class BlogPostAdmin(FSMAdminMixin, admin.ModelAdmin):
    list_display = ['title', 'state']
    fsm_fields = ['state']  # List of FSM fields to manage
```

### Features

- **Transition Buttons**: Displays available transitions as buttons in the change form
- **Secure POST Requests**: All transitions use secure POST requests with CSRF protection
- **Protected Fields**: FSM fields marked as `protected=True` are automatically read-only
- **Custom Labels**: Use `custom={'label': 'Button Text'}` in your transition decorator
- **Transition Forms**: Support for transitions requiring arguments via custom forms

### Transition with Arguments

For transitions that require user input:

```python
# forms.py
from django import forms

class RejectionForm(forms.Form):
    reason = forms.CharField(widget=forms.Textarea)

# models.py
@transition(
    field=state,
    source='pending',
    target='rejected',
    custom={
        'form': 'myapp.forms.RejectionForm',
        'label': 'Reject with Reason',
    }
)
def reject(self, reason=None):
    self.rejection_reason = reason
```

### Hiding Transitions from Admin

```python
# Hide a specific transition
@transition(
    field=state,
    source='draft',
    target='scheduled',
    custom={'admin': False}  # Won't show in admin
)
def schedule(self):
    pass
```

Or use `FSM_ADMIN_FORCE_PERMIT = True` in settings to require explicit `admin=True`:

```python
# settings.py
FSM_ADMIN_FORCE_PERMIT = True

# models.py - only this transition shows in admin
@transition(field=state, source='draft', target='published', custom={'admin': True})
def publish(self):
    pass
```

### Customization

```python
class BlogPostAdmin(FSMAdminMixin, admin.ModelAdmin):
    fsm_fields = ['state']

    # Custom message templates
    fsm_transition_success_msg = "Successfully changed to '{transition_name}'"
    fsm_transition_error_msg = "Failed: {error}"

    # Override redirect after transition
    def get_fsm_redirect_url(self, request, obj):
        return reverse('admin:myapp_blogpost_changelist')
```

## FSM Logging

Django-fsm-2 provides decorators for logging integration with [django-fsm-log](https://github.com/jazzband/django-fsm-log):

```python
from django_fsm_2 import FSMField, transition
from django_fsm_2.log import fsm_log_by, fsm_log_description

class BlogPost(models.Model):
    state = FSMField(default='draft')

    @fsm_log_by
    @fsm_log_description
    @transition(field=state, source='draft', target='published')
    def publish(self, by=None, description=None):
        """The 'by' and 'description' are captured for logging."""
        pass

# Usage
post.publish(by=request.user, description="Approved by editor")
post.save()
```

### Log Decorators

- `@fsm_log_by`: Captures the `by` parameter for user attribution
- `@fsm_log_description`: Captures the `description` parameter for audit trails
- `fsm_log_context(instance, by=None, description=None)`: Context manager for setting log metadata

### Using with django-fsm-log

```bash
pip install django-fsm-log
```

```python
# settings.py
INSTALLED_APPS = [
    ...
    'django_fsm_log',
]

# admin.py
from django.contrib import admin
from django_fsm_log.admin import StateLogInline
from django_fsm_2.admin import FSMAdminMixin

@admin.register(BlogPost)
class BlogPostAdmin(FSMAdminMixin, admin.ModelAdmin):
    fsm_fields = ['state']
    inlines = [StateLogInline]  # Shows transition history
```

## Extensions

### django-fsm-log

Transition logging with full audit trails:

<https://github.com/jazzband/django-fsm-log>

## API Reference

### Exceptions

- `TransitionNotAllowed`: Raised when transition is not allowed from current state or conditions not met
- `ConcurrentTransition`: Raised when optimistic locking detects a concurrent modification
- `InvalidResultState`: Raised when RETURN_VALUE or GET_STATE returns an invalid state

### Fields

- `FSMField(default, protected=False, state_choices=None, **kwargs)`: CharField-based state field
- `FSMIntegerField(default, protected=False, state_choices=None, **kwargs)`: IntegerField-based state field
- `FSMKeyField(to, default, protected=False, state_choices=None, **kwargs)`: ForeignKey-based state field

### Decorators

- `@transition(field, source, target, on_error=None, conditions=None, permission=None, custom=None)`: Mark method as state transition

### Functions

- `can_proceed(bound_method, check_conditions=True) -> bool`: Check if transition is allowed
- `has_transition_perm(bound_method, user) -> bool`: Check if user can execute transition

### Mixins

- `FSMModelMixin`: Enables refresh_from_db() with protected FSM fields
- `ConcurrentTransitionMixin`: Adds optimistic locking for concurrent safety

### Dynamic State Resolution

- `RETURN_VALUE(*allowed_states)`: Use method return value as target state
- `GET_STATE(func, states=None)`: Use callable to compute target state

### Signals

- `pre_transition`: Sent before transition execution
- `post_transition`: Sent after transition (success or on_error failure)
