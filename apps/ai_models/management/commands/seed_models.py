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

        self._upsert(
            identifier=settings.JUDGE_MODEL,
            name=settings.JUDGE_MODEL,
            provider=AIModel.Provider.GROQ,
            is_active=True,
            is_judge=True,
        )

    def _upsert(self, identifier, name, provider, is_active, is_judge=False):
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
            },
        )
        self.stdout.write(f"{'Created' if created else 'Kept existing'} {identifier}")
