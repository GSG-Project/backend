from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q


class EvaluationCriterion(models.Model):
    """A rubric criterion the judge scores. Shared by all responses so scores stay comparable."""

    name = models.CharField(max_length=50, unique=True)
    description = models.TextField(blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ['id']
        verbose_name_plural = 'evaluation criteria'

    def __str__(self):
        return self.name


class Evaluation(models.Model):
    """The judge's score for one response on one criterion."""

    # A string reference (not an import) keeps this app independent of the
    # comparisons code; only the database link points at comparisons.
    response = models.ForeignKey(
        'comparisons.ModelResponse', on_delete=models.CASCADE, related_name='evaluations',
    )
    # PROTECT: a criterion that has scores must be deactivated, not deleted.
    criterion = models.ForeignKey(
        EvaluationCriterion, on_delete=models.PROTECT, related_name='evaluations',
    )
    score = models.PositiveSmallIntegerField()
    feedback = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['response', 'criterion'], name='unique_score_per_response_and_criterion',
            ),
            models.CheckConstraint(
                condition=Q(score__gte=1) & Q(score__lte=10), name='score_between_1_and_10',
            ),
        ]

    def __str__(self):
        return f'{self.criterion}: {self.score}'

    def clean(self):
        # A failed response has nothing to score. This spans two tables, so the
        # database cannot check it; bulk operations skip it, so use save().
        if self.response_id is not None and self.response.status == 'failed':
            raise ValidationError('A failed response cannot be scored.')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
