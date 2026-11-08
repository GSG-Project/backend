import os
from pathlib import Path

import environ

# Load .env first so its values (DATABASE_URL, SECRET_KEY, ...) win over the
# local defaults below. read_env never overrides variables that are already set.
environ.Env.read_env(Path(__file__).resolve().parents[2] / '.env')

os.environ.setdefault('SECRET_KEY', 'django-insecure-development-only')
os.environ.setdefault('DATABASE_URL', 'sqlite:///db.sqlite3')

from .base import *  # noqa: E402,F401,F403

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] += [  # noqa: F405
    'rest_framework.renderers.BrowsableAPIRenderer',
]
