"""Chooses the provider integration for a catalog model."""

from providers.base import BaseProvider
from providers.exceptions import ProviderModelError


def get_provider(provider_name: str) -> BaseProvider:
    # Imported here so a missing SDK or API key only affects its own provider.
    if provider_name == 'gemini':
        from providers.gemini import GeminiProvider

        return GeminiProvider()

    if provider_name == 'groq':
        from providers.groq import GroqProvider

        return GroqProvider()

    if provider_name == 'openrouter':
        from providers.openrouter import OpenRouterProvider

        return OpenRouterProvider()

    raise ProviderModelError(f"Unsupported provider '{provider_name}'.")
