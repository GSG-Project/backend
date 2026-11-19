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


# What the user is told for each kind of failure, and the code the API returns.
# The provider's own message stays in the stored error detail only.
USER_FACING_ERRORS = {
    ProviderUnavailableError: (
        'provider_overloaded',
        'This model is overloaded right now. Please try again in a moment.',
    ),
    ProviderRateLimitError: (
        'provider_rate_limited',
        'This model has hit its rate limit. Please try again in a moment.',
    ),
    ProviderTimeoutError: (
        'provider_timeout',
        'This model took too long to respond. Please try again.',
    ),
}

DEFAULT_USER_FACING_ERROR = ('provider_error', 'This model could not generate a response.')


def describe_for_user(error: Exception) -> dict:
    """The error code and message the API shows for a model that failed."""
    code, message = DEFAULT_USER_FACING_ERROR
    for error_type, described in USER_FACING_ERRORS.items():
        if isinstance(error, error_type):
            code, message = described
            break
    return {'code': code, 'message': message}
