"""NVIDIA NIM provider, which shares its HTTP code with OpenRouter. Nothing here calls the real API."""
import httpx
import pytest

from providers.exceptions import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderUnavailableError,
)
from providers.factory import get_provider
from providers.nvidia import NvidiaProvider
from providers.openrouter import OpenRouterProvider

OK = {
    'choices': [{'message': {'content': 'hello'}}],
    'usage': {'prompt_tokens': 3, 'completion_tokens': 5, 'total_tokens': 8},
}


@pytest.fixture(autouse=True)
def keys(settings):
    settings.NVIDIA_API_KEY = 'nvapi-test'
    settings.OPENROUTER_API_KEY = 'sk-or-test'
    settings.AI_MAX_RETRIES = 0


def reply(monkeypatch, status=200, json=None):
    calls = []

    def post(url, **kwargs):
        calls.append({'url': url, **kwargs})
        return httpx.Response(status, json=json, request=httpx.Request('POST', url))

    monkeypatch.setattr(httpx, 'post', post)
    return calls


def test_request_goes_to_nvidia_with_its_own_key(monkeypatch):
    calls = reply(monkeypatch, json=OK)

    result = NvidiaProvider().generate('moonshotai/kimi-k3.1-pro', 'hi')

    assert result['text'] == 'hello'
    assert (result['input_tokens'], result['output_tokens'], result['total_tokens']) == (3, 5, 8)
    assert calls[0]['url'] == 'https://integrate.api.nvidia.com/v1/chat/completions'
    assert calls[0]['headers']['Authorization'] == 'Bearer nvapi-test'
    assert calls[0]['json']['model'] == 'moonshotai/kimi-k3.1-pro'


def test_openrouter_keeps_its_own_endpoint_and_key(monkeypatch):
    calls = reply(monkeypatch, json=OK)

    OpenRouterProvider().generate('vendor/model:free', 'hi')

    assert calls[0]['url'] == 'https://openrouter.ai/api/v1/chat/completions'
    assert calls[0]['headers']['Authorization'] == 'Bearer sk-or-test'


def test_missing_key_names_the_nvidia_setting(settings):
    settings.NVIDIA_API_KEY = ''

    with pytest.raises(ProviderAuthenticationError, match='NVIDIA_API_KEY'):
        NvidiaProvider()


@pytest.mark.parametrize('status, error', [
    (401, ProviderAuthenticationError),
    (429, ProviderRateLimitError),
    (503, ProviderUnavailableError),
])
def test_errors_are_mapped_and_name_the_provider(monkeypatch, status, error):
    reply(monkeypatch, status=status, json={})

    with pytest.raises(error, match='NVIDIA API request failed'):
        NvidiaProvider().generate('m', 'hi')


def test_factory_returns_the_provider():
    assert isinstance(get_provider('nvidia'), NvidiaProvider)
