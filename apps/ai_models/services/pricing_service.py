"""Calculates the estimated cost of a request from token usage and model pricing."""

from decimal import ROUND_HALF_UP, Decimal

from apps.ai_models.models import AIModel

TOKENS_PER_PRICE_UNIT = Decimal(1_000_000)
COST_PRECISION = Decimal('0.000001')


def calculate_cost(ai_model: AIModel, input_tokens: int | None, output_tokens: int | None) -> Decimal | None:
    """Estimated cost in the model's currency, or None when it cannot be calculated.

    Unknown tokens or an unknown price give None (unavailable), never 0.
    """
    if input_tokens is None or output_tokens is None:
        return None
    if ai_model.input_price_per_million is None or ai_model.output_price_per_million is None:
        return None

    total = (
        Decimal(input_tokens) * ai_model.input_price_per_million
        + Decimal(output_tokens) * ai_model.output_price_per_million
    ) / TOKENS_PER_PRICE_UNIT
    return total.quantize(COST_PRECISION, rounding=ROUND_HALF_UP)
