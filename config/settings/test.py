"""Settings for pytest. Whatever is in .env, tests use a local SQLite database and no real API keys."""

from .development import *  # noqa: F401,F403

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'test.sqlite3',  # noqa: F405 (pytest-django uses an in-memory copy)
    },
}

# Tests use fake providers; blank keys make sure nothing can reach a real API.
GEMINI_API_KEY = ''
GROQ_API_KEY = ''
