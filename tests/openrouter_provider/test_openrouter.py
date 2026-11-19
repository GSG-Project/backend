"""OpenRouter provider: success, error mapping and seeding. Nothing here calls the real API."""
import httpx
import pytest
from django.core.management import call_command

from apps.ai_models.models import AIModel
from providers.exceptions import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderModelError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)
from providers.factory import get_provider
from providers.openrouter import OpenRouterProvider


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.OPENROUTER_API_KEY = 'sk-or-test'
    settings.AI_MAX_RETRIES = 0


def reply(monkeypatch, status=200, json=None, raises=None):
    calls = []

    def post(url, **kwargs):
        calls.append({'url': url, **kwargs})
        if raises:
            raise raises
        return httpx.Response(status, json=json, request=httpx.Request('POST', url))

    monkeypatch.setattr(httpx, 'post', post)
    return calls


OK = {
    'choices': [{'message': {'content': 'hello'}}],
    'usage': {'prompt_tokens': 3, 'completion_tokens': 5, 'total_tokens': 8},
}


def test_successful_answer_maps_text_and_usage(monkeypatch):
    calls = reply(monkeypatch, json=OK)

    result = OpenRouterProvider().generate('vendor/model:free', 'hi')

    assert result['text'] == 'hello'
    assert (result['input_tokens'], result['output_tokens'], result['total_tokens']) == (3, 5, 8)
    assert result['latency_ms'] >= 0
    assert calls[0]['json']['model'] == 'vendor/model:free'
    assert calls[0]['headers']['Authorization'] == 'Bearer sk-or-test'


@pytest.mark.parametrize('status, error', [
    (401, ProviderAuthenticationError),
    (402, ProviderAuthenticationError),
    (404, ProviderModelError),
    (429, ProviderRateLimitError),
    (504, ProviderTimeoutError),
    (503, ProviderUnavailableError),
    (400, ProviderError),
])
def test_http_errors_are_mapped(monkeypatch, status, error):
    reply(monkeypatch, status=status, json={'error': {'message': 'nope'}})

    with pytest.raises(error):
        OpenRouterProvider().generate('m', 'hi')


def test_error_inside_a_200_response_is_raised(monkeypatch):
    reply(monkeypatch, json={'error': {'code': 429, 'message': 'upstream limit'}})

    with pytest.raises(ProviderRateLimitError):
        OpenRouterProvider().generate('m', 'hi')


def test_empty_answer_counts_as_a_failure(monkeypatch):
    reply(monkeypatch, json={'choices': [{'message': {'content': ''}}]})

    with pytest.raises(ProviderUnavailableError):
        OpenRouterProvider().generate('m', 'hi')


def test_timeout_and_network_errors(monkeypatch):
    reply(monkeypatch, raises=httpx.ReadTimeout('slow'))
    with pytest.raises(ProviderTimeoutError):
        OpenRouterProvider().generate('m', 'hi')

    reply(monkeypatch, raises=httpx.ConnectError('down'))
    with pytest.raises(ProviderUnavailableError):
        OpenRouterProvider().generate('m', 'hi')


def test_overloaded_openrouter_is_retried(monkeypatch, settings):
    settings.AI_MAX_RETRIES = 1
    settings.AI_RETRY_BASE_DELAY_SECONDS = 0
    outcomes = [httpx.Response(503, json={}), httpx.Response(200, json=OK)]
    monkeypatch.setattr(
        httpx, 'post', lambda url, **kw: outcomes.pop(0),
    )
    # httpx.Response without a request cannot raise_for_status, which the provider does not use.
    assert OpenRouterProvider().generate('m', 'hi')['text'] == 'hello'


def test_missing_key_is_reported(settings):
    settings.OPENROUTER_API_KEY = ''

    with pytest.raises(ProviderAuthenticationError):
        OpenRouterProvider()


def test_factory_returns_the_provider():
    assert isinstance(get_provider('openrouter'), OpenRouterProvider)


@pytest.mark.django_db
def test_seed_creates_free_models_with_zero_price():
    call_command('seed_models')

    free = AIModel.objects.filter(provider='openrouter')
    assert free.count() == 5
    assert all(m.input_price_per_million == 0 and m.output_price_per_million == 0 for m in free)
    assert all(m.is_active and not m.is_judge for m in free)
