# Field definitions

## Field types

### FSMField

Use `FSMField` to store state as a string value.

```python
from django_fsm import FSMField, FSMModelMixin

class BlogPost(FSMModelMixin, models.Model):
    state = FSMField(default='new')
```

### FSMIntegerField

Use `FSMIntegerField` for enum-style states.

```python
class BlogPostStateEnum(object):
    NEW = 10
    PUBLISHED = 20
    HIDDEN = 30

class BlogPostWithIntegerField(FSMModelMixin, models.Model):
    state = FSMIntegerField(default=BlogPostStateEnum.NEW)
```

### FSMKeyField

Use `FSMKeyField` to store state values in a table and maintain FK
integrity.

```python
class DbState(FSMModelMixin, models.Model):
    id = models.CharField(primary_key=True)
    label = models.CharField()

    def __str__(self):
        return self.label


class BlogPost(FSMModelMixin, models.Model):
    state = FSMKeyField(DbState, default='new')
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

## Field options

### protected

Use `protected=True` to prevent direct assignment. Only transitions may
change the state.

Because `refresh_from_db` assigns to the field, protected fields raise there
as well unless you use `FSMModelMixin`. Use `FSMModelMixin` by default to
allow refresh without enabling arbitrary writes elsewhere.

```python
from django_fsm import FSMModelMixin

class BlogPost(FSMModelMixin, models.Model):
    state = FSMField(default='new', protected=True)

model = BlogPost()
model.state = 'invalid'  # Raises AttributeError
model.refresh_from_db()  # Works
```
