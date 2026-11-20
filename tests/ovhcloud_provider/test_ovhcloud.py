"""OVHcloud AI Endpoints: works without a key, and DeepSeek V4.1 Flash is seeded. No real API calls."""
import httpx
import pytest
from django.core.management import call_command

from apps.ai_models.models import AIModel
from providers.exceptions import ProviderRateLimitError
from providers.factory import get_provider
from providers.ovhcloud import OvhCloudProvider

pytestmark = pytest.mark.django_db

OK = {
    'choices': [{'message': {'content': 'DNS is the internet phone book.'}}],
    'usage': {'prompt_tokens': 3, 'completion_tokens': 9, 'total_tokens': 12},
}


@pytest.fixture(autouse=True)
def no_retries(settings):
    settings.AI_MAX_RETRIES = 0


def reply(monkeypatch, status=200, json=None):
    calls = []

    def post(url, **kwargs):
        calls.append({'url': url, **kwargs})
        return httpx.Response(status, json=json, request=httpx.Request('POST', url))

    monkeypatch.setattr(httpx, 'post', post)
    return calls


def test_works_without_an_api_key_and_sends_no_authorization(monkeypatch, settings):
    settings.OVH_AI_ENDPOINTS_API_KEY = ''
    calls = reply(monkeypatch, json=OK)

    result = get_provider('ovhcloud').generate('DeepSeek-V4.1-Flash-1017', 'hi')

    assert isinstance(get_provider('ovhcloud'), OvhCloudProvider)
    assert result['text'].startswith('DNS')
    assert calls[0]['url'] == 'https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions'
    assert calls[0]['headers'] == {}


def test_optional_key_is_sent_when_configured(monkeypatch, settings):
    settings.OVH_AI_ENDPOINTS_API_KEY = 'ovh-secret'
    calls = reply(monkeypatch, json=OK)

    OvhCloudProvider().generate('m', 'hi')

    assert calls[0]['headers']['Authorization'] == 'Bearer ovh-secret'


def test_anonymous_rate_limit_is_reported_as_rate_limited(monkeypatch):
    reply(monkeypatch, status=429, json={'error': {'message': 'too many requests'}})

    with pytest.raises(ProviderRateLimitError):
        OvhCloudProvider().generate('m', 'hi')


def test_seed_adds_deepseek_free():
    call_command('seed_models')

    model = AIModel.objects.get(api_model_identifier='DeepSeek-V4.1-Flash-1017')
    assert model.provider == 'ovhcloud'
    assert model.is_active and not model.is_judge
    assert model.input_price_per_million == 0
