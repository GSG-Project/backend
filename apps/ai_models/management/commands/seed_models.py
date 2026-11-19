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
    ('inclusionai/ling-3.2-flash:free', 'Ling 3.2 Flash (free)'),
    ('baidu/ernie-5.5-flash-preview:free', 'ERNIE 5.5 Flash (free)'),
    ('cohere/north-mini-code:free', 'North Mini Code (free)'),
    ('google/gemma-4-31b-it:free', 'Gemma 4 31B (free)'),
]


class Command(BaseCommand):
    help = (
        'Create the supported AI models that are missing. '
        'Existing rows (names, prices, active flag) are left untouched.'
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

        self._upsert(
            identifier=settings.JUDGE_MODEL,
            name=settings.JUDGE_MODEL,
            provider=AIModel.Provider.GROQ,
            is_active=True,
            is_judge=True,
        )

    def _upsert(self, identifier, name, provider, is_active, is_judge=False, price=None):
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
                'output_price_per_million': price,
            },
        )
        self.stdout.write(f"{'Created' if created else 'Kept existing'} {identifier}")
