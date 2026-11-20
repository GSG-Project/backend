from providers.openai_compatible import OpenAICompatibleProvider


class NvidiaProvider(OpenAICompatibleProvider):
    """Provider for the free endpoints of NVIDIA NIM (build.nvidia.com).

    Model ids look like `moonshotai/kimi-k3.1-pro`. The key starts with `nvapi-`.
    """

    name = 'NVIDIA'
    url = 'https://integrate.api.nvidia.com/v1/chat/completions'
    api_key_setting = 'NVIDIA_API_KEY'
