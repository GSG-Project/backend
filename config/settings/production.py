from .base import *  # noqa: F401,F403

DEBUG = False

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_SSL_REDIRECT = env.bool('SECURE_SSL_REDIRECT', default=True)  # noqa: F405
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SECURE_HSTS_SECONDS = env.int('SECURE_HSTS_SECONDS', default=0)  # noqa: F405

# Never print reset links or sign-in codes to the logs: without a Brevo key, emails are dropped.
if not BREVO_API_KEY:  # noqa: F405
    EMAIL_BACKEND = 'django.core.mail.backends.dummy.EmailBackend'
