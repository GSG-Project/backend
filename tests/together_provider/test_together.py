"""Together AI provider and its seeded models. Nothing here calls the real API."""
from decimal import Decimal

import httpx
import pytest
from django.core.management import call_command

from apps.ai_models.models import AIModel
from providers.exceptions import ProviderModelError
from providers.factory import get_provider
from providers.together import TogetherProvider

OK = {
    'choices': [{'message': {'content': 'hello'}}],
    'usage': {'prompt_tokens': 3, 'completion_tokens': 5, 'total_tokens': 8},
}


@pytest.fixture(autouse=True)
def key(settings):
    settings.TOGETHER_API_KEY = 'tg-test'
    settings.AI_MAX_RETRIES = 0


def reply(monkeypatch, status=200, json=None):
    calls = []

    def post(url, **kwargs):
        calls.append((url, kwargs))
        return httpx.Response(status, json=json or OK, request=httpx.Request('POST', url))

    monkeypatch.setattr(httpx, 'post', post)
    return calls


def test_the_request_goes_to_together_with_the_key(monkeypatch):
    calls = reply(monkeypatch)

    result = TogetherProvider().generate('zai-org/GLM-5.3', 'hi')

    url, kwargs = calls[0]
    assert url == 'https://api.together.xyz/v1/chat/completions'
    assert kwargs['headers']['Authorization'] == 'Bearer tg-test'
    assert kwargs['json']['model'] == 'zai-org/GLM-5.3'
    assert result['text'] == 'hello' and result['output_tokens'] == 5


def test_a_non_serverless_model_is_a_model_error(monkeypatch):
    reply(monkeypatch, 404, {'error': {'message': 'Unable to access non-serverless model'}})

    with pytest.raises(ProviderModelError):
        TogetherProvider().generate('meta-llama/Llama-3.3-70B-Instruct-Turbo', 'hi')


def test_factory_returns_the_provider():
    assert isinstance(get_provider('together'), TogetherProvider)


@pytest.mark.django_db
def test_seed_adds_the_models_with_real_prices():
    call_command('seed_models')

    models = AIModel.objects.filter(provider='together')
    assert models.count() == 6
    assert all(m.is_active and not m.is_judge for m in models)
    kimi = models.get(api_model_identifier='moonshotai/Kimi-K3.1-Pro')
    assert (kimi.input_price_per_million, kimi.output_price_per_million) == (2, 10)
    flash = models.get(api_model_identifier='zai-org/GLM-5.3-Flash')
    prices = (flash.input_price_per_million, flash.output_price_per_million)
    assert prices == (Decimal('0.15'), Decimal('0.5'))
