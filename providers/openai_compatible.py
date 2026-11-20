import time
from typing import Any

import httpx
from django.conf import settings

from providers.base import BaseProvider
from providers.exceptions import (
    ProviderAuthenticationError,
    ProviderError,
    ProviderModelError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
)


class OpenAICompatibleProvider(BaseProvider):
    """Base for providers that speak the OpenAI chat completions protocol over plain HTTP.

    A concrete provider only sets its name, endpoint and the setting that holds its API key.
    """

    name = ''  # shown in error messages, e.g. "OpenRouter"
    url = ''  # the chat completions endpoint
    api_key_setting = ''  # name of the Django setting that holds the key
    key_required = True  # False for providers with an anonymous free tier

    def __init__(self):
        api_key = getattr(settings, self.api_key_setting)

        if not api_key and self.key_required:
            raise ProviderAuthenticationError(f'{self.api_key_setting} is not configured.')

        self.api_key = api_key

    def _generate_once(self, model_id: str, prompt: str) -> dict[str, Any]:
        if not model_id:
            raise ValueError('model_id cannot be empty.')

        if not prompt or not prompt.strip():
            raise ValueError('prompt cannot be empty.')

        start_time = time.perf_counter()

        try:
            response = httpx.post(
                self.url,
                headers={'Authorization': f'Bearer {self.api_key}'} if self.api_key else {},
                json={
                    'model': model_id,
                    'messages': [{'role': 'user', 'content': prompt}],
                    'temperature': 0.2,
                    'max_tokens': 1000,
                },
                timeout=settings.AI_REQUEST_TIMEOUT_SECONDS,
            )
        except httpx.TimeoutException as error:
            raise ProviderTimeoutError(f'{self.name} request timed out.') from error
        except httpx.HTTPError as error:
            raise ProviderUnavailableError(f'{self.name} is unreachable: {type(error).__name__}') from error

        self._raise_for_status(response)

        latency_ms = round((time.perf_counter() - start_time) * 1000, 2)

        try:
            data = response.json()
        except ValueError as error:
            raise ProviderUnavailableError(f'{self.name} returned a response that is not JSON.') from error

        # Some gateways (OpenRouter) can answer 200 with an error body when the upstream model fails.
        if data.get('error'):
            raise self._error_for(data['error'].get('code'), data['error'].get('message'))

        choices = data.get('choices') or []
        text = (choices[0].get('message') or {}).get('content') if choices else None

        if not text:
            raise ProviderUnavailableError(f'{self.name} returned an empty answer.')

        usage = data.get('usage') or {}

        return {
            'model_id': model_id,
            'text': text,
            'latency_ms': latency_ms,
            'input_tokens': usage.get('prompt_tokens'),
            'output_tokens': usage.get('completion_tokens'),
            'total_tokens': usage.get('total_tokens'),
        }

    def _raise_for_status(self, response: httpx.Response) -> None:
        if response.is_success:
            return

        try:
            message = response.json().get('error', {}).get('message')
        except ValueError:
            message = None

        raise self._error_for(response.status_code, message)

    def _error_for(self, code, message) -> ProviderError:
        message = message or f'{self.name} API request failed.'

        try:
            code = int(code)
        except (TypeError, ValueError):
            return ProviderError(message)

        if code in (401, 402, 403):
            return ProviderAuthenticationError(message)

        if code == 429:
            return ProviderRateLimitError(message)

        if code == 404:
            return ProviderModelError(message)

        if code in (408, 504):
            return ProviderTimeoutError(message)

        if code >= 500:
            return ProviderUnavailableError(message)

        return ProviderError(message)
