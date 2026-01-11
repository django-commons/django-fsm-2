from __future__ import annotations

USE_TZ = True

PROJECT_APPS = (
    "django_fsm_2",
    "tests.testapp",
)

INSTALLED_APPS = (
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.admin",
    "guardian",
    *PROJECT_APPS,
)

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

ROOT_URLCONF = "tests.urls"

MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
]

AUTHENTICATION_BACKENDS = (
    "django.contrib.auth.backends.ModelBackend",  # this is default
    "guardian.backends.ObjectPermissionBackend",
)

DATABASE_ENGINE = "sqlite3"
SECRET_KEY = "nokey"
MIDDLEWARE_CLASSES = ()
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
    }
}

MIGRATION_MODULES = {
    "auth": None,
    "contenttypes": None,
    "guardian": None,
}

ANONYMOUS_USER_ID = 0

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"
