"""
Base Django settings shared by every environment.

Environment-specific overrides live in development.py and production.py.
Secrets and environment-dependent values are read from the .env file.
"""

from datetime import timedelta
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

SECRET_KEY = env('SECRET_KEY')

DEBUG = env.bool('DEBUG', default=False)

ALLOWED_HOSTS = env.list('ALLOWED_HOSTS', default=[])


# Application definition

DJANGO_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

THIRD_PARTY_APPS = [
    'rest_framework',
    'corsheaders',
    'drf_spectacular',
]

LOCAL_APPS = [
    'apps.accounts',
    'apps.ai_models',
    'apps.comparisons',
    'apps.evaluations',
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'
ASGI_APPLICATION = 'config.asgi.application'


# Database (PostgreSQL)

DATABASES = {
    'default': env.db('DATABASE_URL'),
}


# Password validation

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static files

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Django REST Framework

AUTH_USER_MODEL = 'accounts.User'

REST_FRAMEWORK = {
    # Sending a token is optional: the comparison endpoints stay open to anonymous users.
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
}

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'apps.comparisons': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
    },
}

SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME': timedelta(minutes=30),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
}

SPECTACULAR_SETTINGS = {
    'TITLE': 'LLM Effectiveness Sandbox API',
    'DESCRIPTION': 'Compare the response quality, latency, token usage, and cost of LLMs.',
    'VERSION': '0.1.0',
    'SERVE_INCLUDE_SCHEMA': False,
    'TAGS': [
        {'name': 'Health', 'description': 'Check that the service is running.'},
        {'name': 'Auth', 'description': 'Create an account, sign in and refresh tokens.'},
        {'name': 'Models', 'description': 'The AI models available for comparison.'},
        {'name': 'Experiments', 'description': 'Your saved experiments and their results.'},
        {'name': 'Comparisons', 'description': 'Run a prompt against several models and have it judged.'},
    ],
    # Readable names for the choice lists in the generated schema.
    'ENUM_NAME_OVERRIDES': {
        'ProviderEnum': 'apps.ai_models.models.AIModel.Provider',
        'ResultStatusEnum': 'apps.comparisons.models.ModelResponse.Status',
        'RunStatusEnum': 'apps.comparisons.models.Run.Status',
        'EvaluationStatusEnum': 'apps.comparisons.models.Run.EvaluationStatus',
    },
}


# CORS (React frontend)

CORS_ALLOWED_ORIGINS = env.list('CORS_ALLOWED_ORIGINS', default=[])


# AI providers
# Keys stay on the backend only; never expose them to the frontend.

GEMINI_API_KEY = env('GEMINI_API_KEY', default='')

AI_REQUEST_TIMEOUT_SECONDS = env.int(
    'AI_REQUEST_TIMEOUT_SECONDS',
    default=60
)

# Temporary provider failures (overloaded, rate limited) are retried this many
# times, waiting 1s, 2s, ... (plus a little jitter) between attempts.
AI_MAX_RETRIES = env.int('AI_MAX_RETRIES', default=2)
AI_RETRY_BASE_DELAY_SECONDS = env.float('AI_RETRY_BASE_DELAY_SECONDS', default=1.0)


GROQ_API_KEY = env('GROQ_API_KEY', default='')

OPENROUTER_API_KEY = env('OPENROUTER_API_KEY', default='')

JUDGE_MODEL = env(
    'JUDGE_MODEL',
    default='openai/gpt-oss-120b'
)