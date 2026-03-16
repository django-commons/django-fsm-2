# Graphing transitions

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
