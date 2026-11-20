from providers.openai_compatible import OpenAICompatibleProvider


class OpenRouterProvider(OpenAICompatibleProvider):
    """Provider for the models OpenRouter serves, including its free (`:free`) ones."""

    name = 'OpenRouter'
    url = 'https://openrouter.ai/api/v1/chat/completions'
    api_key_setting = 'OPENROUTER_API_KEY'
