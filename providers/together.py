from providers.openai_compatible import OpenAICompatibleProvider


class TogetherProvider(OpenAICompatibleProvider):
    """Provider for Together AI (together.ai). Pay per token, with no rate limit at normal use.

    Model ids look like `zai-org/GLM-5.3`. Only models that Together serves on its
    pay-per-use ("serverless") API work; others answer "non-serverless" and models that
    only support streaming answer 400, because this client does not stream.
    """

    name = 'Together AI'
    url = 'https://api.together.xyz/v1/chat/completions'
    api_key_setting = 'TOGETHER_API_KEY'
