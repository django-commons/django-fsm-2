# Contributing

We welcome contributions. See `CONTRIBUTING.md` for detailed setup
instructions.

## Quick development setup

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
