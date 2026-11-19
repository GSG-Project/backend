"""Temporary provider failures are retried; permanent ones are not."""
import pytest

from providers.base import BaseProvider
from providers.exceptions import (
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class ScriptedProvider(BaseProvider):
    """Raises or returns the next scripted outcome on every attempt."""

    def __init__(self, outcomes):
        self.outcomes = list(outcomes)
        self.calls = 0
        self.sleeps = []

    def _sleep(self, seconds):
        self.sleeps.append(seconds)

    def _generate_once(self, model_id, prompt):
        self.calls += 1
        outcome = self.outcomes.pop(0)
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


OK = {'text': 'hi', 'latency_ms': 5, 'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2}


def test_overloaded_provider_is_retried_until_it_answers():
    provider = ScriptedProvider([ProviderUnavailableError('busy'), ProviderRateLimitError('slow'), OK])

    assert provider.generate('m', 'p') == OK
    assert provider.calls == 3
    assert len(provider.sleeps) == 2
    assert provider.sleeps[1] > provider.sleeps[0]


def test_gives_up_after_the_configured_number_of_retries(settings):
    settings.AI_MAX_RETRIES = 1
    provider = ScriptedProvider([ProviderUnavailableError('busy')] * 3)

    with pytest.raises(ProviderUnavailableError):
        provider.generate('m', 'p')

    assert provider.calls == 2


@pytest.mark.parametrize('error', [ProviderAuthenticationError('key'), ProviderTimeoutError('slow')])
def test_permanent_failures_and_timeouts_are_not_retried(error):
    provider = ScriptedProvider([error, OK])

    with pytest.raises(type(error)):
        provider.generate('m', 'p')

    assert provider.calls == 1
    assert provider.sleeps == []
