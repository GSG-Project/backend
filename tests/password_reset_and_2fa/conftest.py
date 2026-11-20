import pytest
from django.core.cache import cache


@pytest.fixture(autouse=True)
def locmem_email_and_clean_cache(settings):
    settings.EMAIL_BACKEND = 'django.core.mail.backends.locmem.EmailBackend'
    settings.FRONTEND_URL = 'https://app.example.com'
    cache.clear()
    yield
    cache.clear()
