from django.conf import settings
from django.core.management.base import BaseCommand

from apps.ai_models.models import AIModel
from apps.ai_models.services.registry import GEMINI_MODELS


class Command(BaseCommand):
    help = 'Create the supported AI models that are missing. Existing rows (names, prices, active flag) are left untouched.'

    def handle(self, *args, **options):
        for entry in GEMINI_MODELS:
            self._upsert(
                identifier=entry['id'],
                name=entry['name'],
                provider=AIModel.Provider.GEMINI,
                is_active=entry['is_active'],
            )

        # The judge is not offered for comparison, so it is stored as inactive.
        self._upsert(
            identifier=settings.JUDGE_MODEL,
            name=settings.JUDGE_MODEL,
            provider=AIModel.Provider.GROQ,
            is_active=False,
        )

    def _upsert(self, identifier, name, provider, is_active):
        # Values are only used when the row is created, so re-running the seed
        # never undoes changes made in the admin.
        _, created = AIModel.objects.update_or_create(
            api_model_identifier=identifier,
            defaults={},
            create_defaults={'name': name, 'provider': provider, 'is_active': is_active},
        )
        self.stdout.write(f"{'Created' if created else 'Kept existing'} {identifier}")
