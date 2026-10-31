
import time
from typing import Any

from django.conf import settings
from groq import Groq, APIError, AuthenticationError, RateLimitError

from providers.base import BaseProvider
from providers.exceptions import (
    ProviderError,
    ProviderAuthenticationError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    ProviderModelError,
)


class GroqProvider(BaseProvider):

    def __init__(self):
        api_key = settings.GROQ_API_KEY

        if not api_key:
            raise ProviderAuthenticationError(
                "GROQ_API_KEY is not configured."
            )

        self.client = Groq(
            api_key=api_key,
            timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
        )

    def generate(self, model_id: str, prompt: str) -> dict[str, Any]:

        if not model_id:
            raise ValueError("model_id cannot be empty.")

        if not prompt or not prompt.strip():
            raise ValueError("prompt cannot be empty.")

        start_time = time.perf_counter()

        try:
            response = self.client.chat.completions.create(
                model=model_id,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                temperature=0.2,
                max_tokens=1000,
            )

        except AuthenticationError as error:
            raise ProviderAuthenticationError(
                "Groq authentication failed."
            ) from error

        except RateLimitError as error:
            raise ProviderRateLimitError(
                "Groq rate limit exceeded."
            ) from error

        except APIError as error:
            if error.status_code == 404:
                raise ProviderModelError(
                    "Groq model not found or unavailable."
                ) from error

            if error.status_code in (408, 504):
                raise ProviderTimeoutError(
                    "Groq request timed out."
                ) from error

            if error.status_code >= 500:
                raise ProviderUnavailableError(
                    "Groq service is unavailable."
                ) from error

            raise ProviderError(
                f"Groq API error: {error}"
            ) from error

        except Exception as error:
            raise ProviderError(
                f"Unexpected Groq error: {error}"
            ) from error

        latency_ms = round(
            (time.perf_counter() - start_time) * 1000,
            2
        )

        usage = response.usage

        return {
            "model_id": model_id,
            "text": response.choices[0].message.content or "",
            "latency_ms": latency_ms,
            "input_tokens": usage.prompt_tokens if usage else None,
            "output_tokens": usage.completion_tokens if usage else None,
            "total_tokens": usage.total_tokens if usage else None,
        }
