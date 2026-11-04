import pytest

from apps.comparisons.services.metrics_service import normalize_latency_ms, normalize_token_count


@pytest.mark.parametrize('value, expected', [(120.4, 120), (120.6, 121), (0, 0), (None, None), (-1, None)])
def test_normalize_latency_ms(value, expected):
    assert normalize_latency_ms(value) == expected


@pytest.mark.parametrize('value, expected', [(15, 15), (0, 0), (None, None), (-3, None)])
def test_normalize_token_count(value, expected):
    assert normalize_token_count(value) == expected
