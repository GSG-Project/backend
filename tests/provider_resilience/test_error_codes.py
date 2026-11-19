"""A failed model reports why it failed, so the user knows whether to try again."""
import pytest

from apps.ai_models.models import AIModel
from apps.comparisons.services.comparison_service import ComparisonService
from apps.comparisons.tests.fakes import FakeJudge, FakeProvider
from providers.exceptions import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)

pytestmark = pytest.mark.django_db


@pytest.mark.parametrize('error, code', [
    (ProviderUnavailableError('503 high demand'), 'provider_overloaded'),
    (ProviderRateLimitError('429'), 'provider_rate_limited'),
    (ProviderTimeoutError('slow'), 'provider_timeout'),
    (ProviderAuthenticationError('bad key'), 'provider_error'),
])
def test_failed_model_gets_a_specific_code(error, code):
    AIModel.objects.create(name='One', provider='gemini', api_model_identifier='m-1')
    AIModel.objects.create(name='Two', provider='groq', api_model_identifier='m-2')
    ids = ['m-1', 'm-2']
    provider = FakeProvider({ids[0]: error})
    service = ComparisonService(judge_service=FakeJudge(), provider_factory=provider.factory)

    result = service.compare('hello', ids)

    failed = result['results'][0]
    assert failed['status'] == 'failed'
    assert failed['error']['code'] == code
    # The provider's own text is never shown to the user.
    assert '503' not in failed['error']['message']
