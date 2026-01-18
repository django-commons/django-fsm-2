# Contributing to django-fsm-2

Thank you for your interest in contributing to django-fsm-2! This document provides guidelines and instructions for contributing.

## Prerequisites

- **uv** (recommended) or pip for package management
- **graphviz** system package (for graph visualization tests)

### Installing graphviz

```bash
# macOS
brew install graphviz

# Ubuntu/Debian
sudo apt-get install graphviz

# Fedora
sudo dnf install graphviz

# Windows (with chocolatey)
choco install graphviz
```

## Development Setup

### Quick Start with uv (Recommended)

[uv](https://github.com/astral-sh/uv) is a fast Python package manager that handles virtual environments automatically.

```bash
# Clone the repository
git clone https://github.com/django-commons/django-fsm-2.git
cd django-fsm

# Install dependencies (creates .venv automatically)
uv sync

# Run tests
uv run pytest

# Run tests with coverage
uv run pytest --cov=django_fsm --cov-report=term-missing
```

### Alternative: pip with venv

```bash
# Clone the repository
git clone https://github.com/django-commons/django-fsm-2.git
cd django-fsm

# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install in development mode with dev dependencies
pip install -e ".[graphviz]"
pip install pytest pytest-django pytest-cov django-guardian pre-commit

# Run tests
pytest
```

## Running Tests

### Basic test run

```bash
uv run pytest
```

### With verbose output

```bash
uv run pytest -v
```

### Run specific test file

```bash
uv run pytest tests/test_basic_transitions.py -v
```

### Run specific test

```bash
uv run pytest tests/test_basic_transitions.py::test_initial_state -v
```

### With coverage report

```bash
uv run pytest --cov=django_fsm --cov-report=term-missing --cov-report=html
```

### Multi-version testing with tox

To test against multiple Python and Django versions:

```bash
# Install tox
pip install tox

# Run all environments
tox

# Run specific environment
tox -e py312-dj52
```

## Code Style

We use [ruff](https://github.com/astral-sh/ruff) for linting and formatting.

### Check for issues

```bash
uv run ruff check .
```

### Auto-fix issues

```bash
uv run ruff check --fix .
```

### Format code

```bash
uv run ruff format .
```

## Pre-commit Hooks

We use pre-commit to ensure code quality before commits.

### Setup

```bash
# Install pre-commit hooks
uv run pre-commit install

# Run manually on all files
uv run pre-commit run --all-files
```

## Type Checking

We use mypy for type checking:

```bash
uv run mypy django_fsm
```

## Pull Request Guidelines

### Before submitting

1. **Write tests** for any new functionality
2. **Run the full test suite** and ensure all tests pass
3. **Run linting** and fix any issues
4. **Update documentation** if you're adding/changing features

### PR Checklist

- [ ] Tests added/updated for the changes
- [ ] All tests pass (`uv run pytest`)
- [ ] Linting passes (`uv run ruff check .`)
- [ ] Documentation updated (if applicable)
- [ ] CHANGELOG.rst updated (for user-facing changes)

### Commit Messages

- Use clear, descriptive commit messages
- Start with a verb (Add, Fix, Update, Remove, etc.)
- Reference issues when applicable: "Fix #123: Handle edge case in transition"

## Getting Help

- **Issues**: Open a [GitHub issue](https://github.com/django-commons/django-fsm-2/issues) for bugs or feature requests
- **Discussions**: Use GitHub Discussions for questions and ideas

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
