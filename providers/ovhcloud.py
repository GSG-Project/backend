from providers.openai_compatible import OpenAICompatibleProvider


class OvhCloudProvider(OpenAICompatibleProvider):
    """Provider for OVHcloud AI Endpoints (EU hosted open models, e.g. DeepSeek V4.1 Flash).

    The free tier needs no API key: anonymous use is limited to 2 requests per minute per IP
    and per model. An optional OVH_AI_ENDPOINTS_API_KEY raises the limit (400/min per model).
    """

    name = 'OVHcloud'
    url = 'https://oai.endpoints.kepler.ai.cloud.ovh.net/v1/chat/completions'
    api_key_setting = 'OVH_AI_ENDPOINTS_API_KEY'
    key_required = False
