from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from django.test import TestCase


class TypingImportTests(TestCase):
    project_root: Path
    env: dict[str, str]

    def setUp(self) -> None:
        self.project_root = Path(__file__).resolve().parents[3]
        self.env = os.environ.copy()
        self.env.pop("DJANGO_SETTINGS_MODULE", None)
        python_path = self.env.get("PYTHONPATH")
        self.env["PYTHONPATH"] = (
            f"{self.project_root}{os.pathsep}{python_path}"
            if python_path
            else str(self.project_root)
        )

    def test_admin_module_imports_without_django_stubs_monkeypatch(self) -> None:
        completed_process = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-c",
                (
                    "from django.conf import settings; "
                    "settings.configure(SECRET_KEY='test', USE_I18N=False); "
                    "import django_fsm.admin"
                ),
            ],
            capture_output=True,
            check=False,
            cwd=self.project_root,
            env=self.env,
            text=True,
        )

        assert completed_process.returncode == 0, completed_process.stderr

    def test_main_module_imports_without_django_stubs_monkeypatch(self) -> None:
        completed_process = subprocess.run(  # noqa: S603
            [
                sys.executable,
                "-c",
                (
                    "from django.conf import settings; "
                    "settings.configure(SECRET_KEY='test', USE_I18N=False); "
                    "import django_fsm"
                ),
            ],
            capture_output=True,
            check=False,
            cwd=self.project_root,
            env=self.env,
            text=True,
        )

        assert completed_process.returncode == 0, completed_process.stderr
