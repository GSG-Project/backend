from decimal import Decimal

import pytest

from apps.ai_models.models import AIModel
from apps.ai_models.services.pricing_service import calculate_cost

pytestmark = pytest.mark.django_db


def make_model(identifier='m-1', **kwargs):
    return AIModel.objects.create(
        name=identifier, provider='gemini', api_model_identifier=identifier, **kwargs,
    )


def test_cost_uses_price_per_million_tokens():
    model = make_model(input_price_per_million=Decimal('0.30'), output_price_per_million=Decimal('2.50'))

    # 1,000 * 0.30 / 1M + 2,000 * 2.50 / 1M = 0.0003 + 0.005
    assert calculate_cost(model, 1000, 2000) == Decimal('0.005300')


def test_cost_is_zero_for_zero_tokens_when_prices_are_known():
    model = make_model(input_price_per_million=Decimal('1'), output_price_per_million=Decimal('1'))

    assert calculate_cost(model, 0, 0) == Decimal('0.000000')


@pytest.mark.parametrize('input_tokens, output_tokens', [(None, 5), (5, None), (None, None)])
def test_cost_is_unavailable_when_tokens_are_unknown(input_tokens, output_tokens):
    model = make_model(input_price_per_million=Decimal('1'), output_price_per_million=Decimal('1'))

    assert calculate_cost(model, input_tokens, output_tokens) is None


def test_cost_is_unavailable_when_a_price_is_unknown():
    model = make_model(input_price_per_million=Decimal('1'))

    assert calculate_cost(model, 10, 10) is None
