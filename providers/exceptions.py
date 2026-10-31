"""Base exceptions for provider failures (API errors, timeouts, rate limits)."""


class ProviderError(Exception):
    """Base exception for errors raised by an AI provider."""


class ProviderAuthenticationError(ProviderError):
    """Raised when provider authentication fails."""


class ProviderRateLimitError(ProviderError):
    """Raised when the provider rate limit is exceeded."""


class ProviderTimeoutError(ProviderError):
    """Raised when a provider request times out."""


class ProviderUnavailableError(ProviderError):
    """Raised when the provider is temporarily unavailable."""


class ProviderModelError(ProviderError):
    """Raised when the requested model is invalid or unavailable."""
