
import time
from typing import Any

import httpx
from django.conf import settings
from google import genai
from google.genai import types as genai_types
from google.genai import errors as genai_errors

from providers.base import BaseProvider
from providers.exceptions import (
    ProviderError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderModelError,
)


class GeminiProvider(BaseProvider):
    """Provider for generating responses using Google Gemini models."""

    def __init__(self):
        api_key = settings.GEMINI_API_KEY

        if not api_key:
            raise ValueError("GEMINI_API_KEY is missing.")

        # The SDK takes the timeout in milliseconds. Without it a slow call
        # waits forever and can outlive the web server's own timeout.
        self.client = genai.Client(
            api_key=api_key,
            http_options=genai_types.HttpOptions(
                timeout=settings.AI_REQUEST_TIMEOUT_SECONDS * 1000,
            ),
        )

    def _generate_once(self, model_id: str, prompt: str) -> dict[str, Any]:
        """Generate a response and collect performance metrics."""

        if not model_id:
            raise ValueError("Model ID is required.")

        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        start_time = time.perf_counter()

        try:
            response = self.client.models.generate_content(
                model=model_id,
                contents=prompt,
            )

        except genai_errors.APIError as error:
            status_code = error.code
            message = error.message or "Gemini API request failed."

            if status_code in (401, 403):
                raise ProviderAuthenticationError(message) from error

            if status_code == 429:
                raise ProviderRateLimitError(message) from error

            if status_code == 404:
                raise ProviderModelError(message) from error

            if status_code in (408, 504):
                raise ProviderTimeoutError(message) from error

            if status_code >= 500:
                raise ProviderUnavailableError(message) from error

            raise ProviderError(message) from error

        except (TimeoutError, httpx.TimeoutException) as error:
            raise ProviderTimeoutError(
                "Gemini request timed out."
            ) from error

        except Exception as error:
            raise ProviderError(
                f"Unexpected Gemini error: {error}"
            ) from error

        latency_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2,
        )

        usage = response.usage_metadata

        return {
            "model_id": model_id,
            "text": response.text,
            "latency_ms": latency_ms,
            "input_tokens": (
                usage.prompt_token_count if usage else None
            ),
            "output_tokens": (
                usage.candidates_token_count if usage else None
            ),
            "total_tokens": (
                usage.total_token_count if usage else None
            ),
        }
