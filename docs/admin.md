# Admin integration

If you're migrating from
[django-fsm-admin](https://github.com/gadventures/django-fsm-admin) (or any
alternative), make sure it is not installed anymore to avoid installing the
old django-fsm.

Update import path:

```python
- from django_fsm_admin.mixins import FSMTransitionMixin
+ from django_fsm.admin import FSMAdminMixin
```

1. In your admin.py file, use `FSMAdminMixin` to add behaviour to your
   `ModelAdmin`. `FSMAdminMixin` should be before `ModelAdmin`, the order is
   important.

```python
from django_fsm.admin import FSMAdminMixin

@admin.register(AdminBlogPost)
class MyAdmin(FSMAdminMixin, admin.ModelAdmin):
    # Declare the fsm fields you want to manage
    fsm_fields = ['my_fsm_field']
    ...
```

2. You can customize the buttons by adding `label` and `help_text` to the
   `custom` attribute of the transition decorator.

```python
@transition(
    field='state',
    source=['startstate'],
    target='finalstate',
    custom={
        "label": "My awesome transition",
        "help_text": "Rename blog post",
    },
)
def do_something(self, **kwargs):
    ...
```

Or by overriding some methods in `FSMAdminMixin`:

```python
@admin.register(AdminBlogPost)
class MyAdmin(FSMAdminMixin, admin.ModelAdmin):
    ...

    def get_fsm_label(self, transition):
        if transition.name == "do_something":
            return "My awesome transition"
        return super().get_fsm_label(transition)

    def get_help_text(self, transition):
        if transition.name == "do_something":
            return "Rename blog post"
        return super().get_help_text(transition)
```

3. For forms in the admin transition flow, see the Custom Forms section below.

4. Hide a transition by adding `custom={"admin": False}` to the transition
   decorator:

```python
@transition(
    field='state',
    source=['startstate'],
    target='finalstate',
    custom={
        "admin": False,
    },
)
def do_something(self, **kwargs):
    ...
```

Or from the admin:

```python
@admin.register(AdminBlogPost)
class MyAdmin(FSMAdminMixin, admin.ModelAdmin):
    ...

    def is_fsm_transition_visible(self, transition: fsm.Transition) -> bool:
        if transition.name == "do_something":
            return False
        return super().is_fsm_transition_visible(transition)
```

By adding `FSM_ADMIN_FORCE_PERMIT = True` to your configuration settings (or
`fsm_default_disallow_transition = False` to your admin), the above
restriction becomes the default. Then one must explicitly allow that a
transition method shows up in the admin interface using
`custom={"admin": True}`.

```python
@admin.register(AdminBlogPost)
class MyAdmin(FSMAdminMixin, admin.ModelAdmin):
    fsm_default_disallow_transition = False
    ...
```

## Custom forms

You can attach a custom form to a transition so the admin prompts for input
before the transition runs. Add a `form` entry to `custom` on the transition,
or define an admin-level mapping via `fsm_forms`. Both accept a `forms.Form`/
`forms.ModelForm` class or a dotted import path.

```python
from django import forms
from django_fsm import FSMModelMixin, transition

class RenameForm(forms.Form):
    new_title = forms.CharField(max_length=255)
    # it's also possible to declare fsm log description
    description = forms.CharField(max_length=255)

class BlogPost(FSMModelMixin, models.Model):
    title = models.CharField(max_length=255)
    state = FSMField(default="created")

    @transition(
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
        "rename": "path.to.RenameForm",
        "rename": RenameForm,
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
  `fsm_transition_form_template` on your `ModelAdmin` (or override globally
  `templates/django_fsm/fsm_admin_transition_form.html`).
