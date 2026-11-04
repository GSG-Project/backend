from django.core.management.base import BaseCommand

from apps.evaluations.criteria import CRITERIA
from apps.evaluations.models import EvaluationCriterion


class Command(BaseCommand):
    help = 'Create or update the evaluation criteria. Safe to run repeatedly.'

    def handle(self, *args, **options):
        for name, description in CRITERIA:
            _, created = EvaluationCriterion.objects.update_or_create(
                name=name, defaults={'description': description},
            )
            self.stdout.write(f"{'Created' if created else 'Updated'} {name}")
