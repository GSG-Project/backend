import os

os.environ.setdefault('SECRET_KEY', 'django-insecure-development-only')
os.environ.setdefault('DATABASE_URL', 'sqlite:///db.sqlite3')

from .base import *  # noqa: F401,F403

DEBUG = True

ALLOWED_HOSTS = ['localhost', '127.0.0.1']

REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] += [  # noqa: F405
    'rest_framework.renderers.BrowsableAPIRenderer',
]
