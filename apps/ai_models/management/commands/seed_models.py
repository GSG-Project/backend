from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ai_models.models import AIModel

# Models users can compare. Prices are not seeded; enter them in the admin.
SUPPORTED_MODELS = [
    ('gemini-3.8-flash', 'Gemini 3.8 Flash'),
    ('gemini-3.6-flash', 'Gemini 3.6 Flash'),
    ('gemini-3.5-flash-lite', 'Gemini 3.5 Flash-Lite'),
    ('gemini-3.1-flash-lite', 'Gemini 3.1 Flash-Lite'),
]

# Free models served by OpenRouter. They cost nothing, so their price is seeded as 0
# and a comparison shows $0 instead of "unavailable". Each comes from a different
# maker so one outage does not remove all of them.
OPENROUTER_FREE_MODELS = [
    ('nvidia/nemotron-3-ultra-550b-a55b:free', 'Nemotron 3 Ultra (free)'),
    ('baidu/ernie-5.5-flash-preview:free', 'ERNIE 5.5 Flash (free)'),
]

# Free Groq models to compare. Groq is also the judge's provider, so these share the
# account's quota with the judge. The judge model itself is never offered here.
# allam-2-7b is a small Arabic-focused model (4,096 token context), included to test
# Arabic prompts.
GROQ_FREE_MODELS = [
    ('qwen/qwen3.8-27b', 'Qwen 3.8 27B (Groq)'),
    ('openai/gpt-oss-20b', 'GPT-OSS 20B (Groq)'),
    ('allam-2-7b', 'ALLaM 2 7B (Groq)'),
]

# OVHcloud AI Endpoints models. The free tier needs no key (2 requests/min per IP and per
# model), so the limit is shared by everyone using the deployed backend.
OVHCLOUD_FREE_MODELS = [
    ('DeepSeek-V4.1-Flash-1017', 'DeepSeek V4.1 Flash (OVHcloud)'),
]

# NVIDIA NIM models (needs NVIDIA_API_KEY). Each one was called with a real key before being
# listed; NVIDIA retires models without notice (Llama 3.3 70B ended 2026-08-26), so re-check them.
NVIDIA_FREE_MODELS = [
    ('nvidia/nemotron-3-ultra-550b-a55b', 'Nemotron 3 Ultra (NVIDIA)'),
    ('minimaxai/minimax-m3.1-flash', 'MiniMax M3.1 Flash (NVIDIA)'),
    ('poolside/laguna-xs-2.1', 'Laguna XS 2.1 (NVIDIA)'),
    ('nvidia/nemotron-3.5-lightning-30b-a3b', 'Nemotron 3.5 Lightning (NVIDIA)'),
    ('nvidia/nemotron-3-nano-omni-30b-a3b-reasoning', 'Nemotron 3 Nano Omni (NVIDIA)'),
]

# Together AI models (needs TOGETHER_API_KEY). Pay per token, so prices are real (USD per million
# tokens, input and output). Each one answered a real request with our key before being listed;
# models that only stream, need a dedicated endpoint or have no capacity were left out.
TOGETHER_MODELS = [
    ('moonshotai/Kimi-K3.1-Pro', 'Kimi K3.1 Pro (Together)', Decimal('2'), Decimal('10')),
    ('deepseek-ai/DeepSeek-V4-Pro-0813', 'DeepSeek V4 Pro (Together)', Decimal('1.32'), Decimal('3.96')),
    ('zai-org/GLM-5.3', 'GLM 5.3 (Together)', Decimal('1.4'), Decimal('4.4')),
    ('zai-org/GLM-5.3-Flash', 'GLM 5.3 Flash (Together)', Decimal('0.15'), Decimal('0.5')),
    ('deepseek-ai/DeepSeek-V4.1-Flash', 'DeepSeek V4.1 Flash (Together)', Decimal('0.3'), Decimal('1.2')),
    ('MiniMaxAI/MiniMax-M3.1-Flash', 'MiniMax M3.1 Flash (Together)', Decimal('0.15'), Decimal('0.6')),
]

# Models that are gone or fail almost every request. They are switched off, not
# deleted, because past experiments refer to them.
RETIRED_MODELS = [
    'cohere/north-mini-code:free',  # no longer served by OpenRouter
    'inclusionai/ling-3.2-flash:free',  # temporarily rate-limited upstream on every call
    'google/gemma-4-31b-it:free',  # rate-limited upstream on every call (shared Google capacity)
]


class Command(BaseCommand):
    help = (
        'Create the supported AI models that are missing and switch off retired ones. '
        'Other existing rows (names, prices, active flag) are left untouched.'
    )

    def handle(self, *args, **options):
        for identifier, name in SUPPORTED_MODELS:
            self._upsert(
                identifier=identifier,
                name=name,
                provider=AIModel.Provider.GEMINI,
                is_active=True,
            )

        for identifier, name in OPENROUTER_FREE_MODELS:
            self._upsert(
                identifier=identifier,
                name=name,
                provider=AIModel.Provider.OPENROUTER,
                is_active=True,
                price=Decimal('0'),
            )

        for identifier, name in GROQ_FREE_MODELS:
            self._upsert(
                identifier=identifier,
                name=name,
                provider=AIModel.Provider.GROQ,
                is_active=True,
                price=Decimal('0'),
            )

        for identifier, name in NVIDIA_FREE_MODELS:
            self._upsert(
                identifier=identifier,
                name=name,
                provider=AIModel.Provider.NVIDIA,
                is_active=True,
                price=Decimal('0'),
            )

        for identifier, name, input_price, output_price in TOGETHER_MODELS:
            self._upsert(
                identifier=identifier,
                name=name,
                provider=AIModel.Provider.TOGETHER,
                is_active=True,
                price=input_price,
                output_price=output_price,
            )

        for identifier, name in OVHCLOUD_FREE_MODELS:
            self._upsert(
                identifier=identifier,
                name=name,
                provider=AIModel.Provider.OVHCLOUD,
                is_active=True,
                price=Decimal('0'),
            )

        for identifier in RETIRED_MODELS:
            retired = AIModel.objects.filter(
                api_model_identifier=identifier, is_active=True,
            ).update(is_active=False)
            if retired:
                self.stdout.write(f'Deactivated retired model {identifier}')

        self._upsert(
            identifier=settings.JUDGE_MODEL,
            name=settings.JUDGE_MODEL,
            provider=AIModel.Provider.GROQ,
            is_active=True,
            is_judge=True,
        )

    def _upsert(self, identifier, name, provider, is_active, is_judge=False, price=None, output_price=None):
        # Values are only used when the row is created, so re-running the seed
        # never undoes changes made in the admin.
        _, created = AIModel.objects.update_or_create(
            api_model_identifier=identifier,
            defaults={},
            create_defaults={
                'name': name,
                'provider': provider,
                'is_active': is_active,
                'is_judge': is_judge,
                'input_price_per_million': price,
                'output_price_per_million': price if output_price is None else output_price,
            },
        )
        self.stdout.write(f"{'Created' if created else 'Kept existing'} {identifier}")
