from django.core.management.base import BaseCommand

from apps.evaluations.models import EvaluationCriterion

# These match the criteria the judge prompt currently scores.
CRITERIA = [
    ('accuracy', 'Is the information correct?'),
    ('relevance', "Does it answer the user's prompt?"),
    ('clarity', 'Is it clear and understandable?'),
    ('completeness', 'Does it cover the important points?'),
]


class Command(BaseCommand):
    help = 'Create or update the evaluation criteria. Safe to run repeatedly.'

    def handle(self, *args, **options):
        for name, description in CRITERIA:
            _, created = EvaluationCriterion.objects.update_or_create(
                name=name, defaults={'description': description},
            )
            self.stdout.write(f"{'Created' if created else 'Updated'} {name}")
