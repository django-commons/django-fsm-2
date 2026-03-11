# Signals

`django_fsm.signals.pre_transition` and `django_fsm.signals.post_transition`
fire before and after an allowed transition. No signals fire for invalid
transitions.

Arguments sent with these signals:

- `sender` The model class.
- `instance` The actual instance being processed.
- `name` Transition name.
- `source` Source model state.
- `target` Target model state.
