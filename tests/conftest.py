from __future__ import annotations

import pytest
from django.core.management import call_command


@pytest.fixture(scope="session", autouse=True)  # type: ignore[untyped-decorator]
def load_test_states_data(django_db_setup, django_db_blocker) -> None:  # type: ignore[no-untyped-def]
    with django_db_blocker.unblock():
        call_command("loaddata", "test_states_data")
