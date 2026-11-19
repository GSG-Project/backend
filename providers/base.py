"""Shared interface that every AI provider integration implements."""

import random
import time
from abc import ABC, abstractmethod
from typing import Any

from django.conf import settings

from providers.exceptions import ProviderRateLimitError, ProviderUnavailableError

# Only temporary failures are retried. A timeout already waited the full
# request timeout, and auth or model errors would fail the same way again.
RETRYABLE_ERRORS = (ProviderUnavailableError, ProviderRateLimitError)


class BaseProvider(ABC):
    """Common interface for all AI providers."""

    def generate(self, model_id: str, prompt: str) -> dict[str, Any]:
        """
        Generate a response from an AI model, retrying temporary failures
        (provider overloaded or rate limited) with a growing delay.

        Returns:
            A standardized response containing text,
            latency, and token usage. The latency is the one of the
            successful attempt, not of the waiting between attempts.
        """
        retries = settings.AI_MAX_RETRIES
        attempt = 0

        while True:
            try:
                return self._generate_once(model_id, prompt)
            except RETRYABLE_ERRORS:
                if attempt >= retries:
                    raise
                delay = settings.AI_RETRY_BASE_DELAY_SECONDS * (2 ** attempt)
                self._sleep(delay + random.uniform(0, delay / 2))
                attempt += 1

    @staticmethod
    def _sleep(seconds: float) -> None:
        time.sleep(seconds)

    @abstractmethod
    def _generate_once(self, model_id: str, prompt: str) -> dict[str, Any]:
        """Send one request to the provider. Raise a ProviderError on failure."""
        raise NotImplementedError
