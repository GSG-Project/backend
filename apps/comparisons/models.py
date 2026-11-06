from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Experiment(models.Model):
    """A comparison request: one prompt and the models chosen for it."""

    # Who ran it. Empty for anonymous comparisons, which cannot be listed later.
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='experiments',
    )
    prompt = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    ai_models = models.ManyToManyField(
        'ai_models.AIModel',
        through='ExperimentModel',
        related_name='experiments',
    )

    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['-created_at']),
            # A user's history, newest first.
            models.Index(fields=['user', '-created_at']),
        ]

    def __str__(self):
        return f'Experiment {self.pk}'


class ExperimentModel(models.Model):
    """Links an experiment to a model it uses. The MVP allows exactly two per experiment."""

    experiment = models.ForeignKey(
        Experiment, on_delete=models.CASCADE, related_name='experiment_models',
    )
    # PROTECT: a model that has history must be deactivated, not deleted.
    ai_model = models.ForeignKey(
        'ai_models.AIModel', on_delete=models.PROTECT, related_name='experiment_models',
    )

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['experiment', 'ai_model'], name='unique_model_per_experiment',
            ),
        ]

    def __str__(self):
        return f'{self.ai_model} in experiment {self.experiment_id}'


class Run(models.Model):
    """One execution of an experiment. Reruns add runs and keep earlier results."""

    class Status(models.TextChoices):
        PENDING = 'pending', 'Pending'
        RUNNING = 'running', 'Running'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'

    class EvaluationStatus(models.TextChoices):
        PENDING = 'pending', 'Pending'
        COMPLETED = 'completed', 'Completed'
        FAILED = 'failed', 'Failed'
        # Fewer than two successful responses, so there was nothing to compare.
        SKIPPED = 'skipped', 'Skipped'

    experiment = models.ForeignKey(Experiment, on_delete=models.CASCADE, related_name='runs')
    started_at = models.DateTimeField(default=timezone.now)
    completed_at = models.DateTimeField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)

    # Which judge scored this run, and how the evaluation ended. The status is
    # what tells "the judge failed" apart from "not judged yet".
    judge_model = models.ForeignKey(
        'ai_models.AIModel',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='judged_runs',
        limit_choices_to={'is_judge': True},
    )
    evaluation_status = models.CharField(
        max_length=20, choices=EvaluationStatus.choices, default=EvaluationStatus.PENDING,
    )
    evaluation_error = models.TextField(blank=True)
    # The judge's pick and its explanation. Empty until a completed evaluation.
    winner = models.ForeignKey(
        ExperimentModel,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='won_runs',
    )
    judge_reasoning = models.TextField(blank=True)

    class Meta:
        ordering = ['-started_at']
        constraints = [
            models.CheckConstraint(
                condition=~Q(evaluation_status='completed') | Q(judge_model__isnull=False),
                name='completed_evaluation_has_judge',
            ),
            models.CheckConstraint(
                condition=~Q(evaluation_status='failed') | ~Q(evaluation_error=''),
                name='failed_evaluation_has_error',
            ),
            models.CheckConstraint(
                condition=Q(status__in=['pending', 'running']) | Q(completed_at__isnull=False),
                name='finished_run_has_completed_at',
            ),
        ]

    def __str__(self):
        return f'Run {self.pk} of experiment {self.experiment_id}'

    def clean(self):
        # The winner must be one of this experiment's models. This spans two
        # tables, so it is checked here; bulk operations skip it.
        if self.winner_id is not None and self.winner.experiment_id != self.experiment_id:
            raise ValidationError('The winner must be a model of the same experiment.')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)


class ModelResponse(models.Model):
    """The result of sending the prompt to one model in one run."""

    class Status(models.TextChoices):
        SUCCESS = 'success', 'Success'
        FAILED = 'failed', 'Failed'

    run = models.ForeignKey(Run, on_delete=models.CASCADE, related_name='responses')
    experiment_model = models.ForeignKey(
        ExperimentModel, on_delete=models.CASCADE, related_name='responses',
    )
    # Measured or provider-reported values are NULL when unavailable, never 0.
    response_text = models.TextField(null=True, blank=True)
    input_tokens = models.PositiveIntegerField(null=True, blank=True)
    output_tokens = models.PositiveIntegerField(null=True, blank=True)
    latency_ms = models.PositiveIntegerField(null=True, blank=True)
    cost = models.DecimalField(max_digits=12, decimal_places=6, null=True, blank=True)
    status = models.CharField(max_length=20, choices=Status.choices)
    error_message = models.TextField(blank=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=['run', 'experiment_model'], name='unique_response_per_run_and_model',
            ),
            # A failed call must never look like a successful one.
            models.CheckConstraint(
                condition=Q(status='failed') | Q(response_text__isnull=False),
                name='successful_response_has_text',
            ),
        ]

    def __str__(self):
        return f'Response {self.pk} ({self.status})'

    def clean(self):
        # The database cannot check that the run and the experiment model
        # belong to the same experiment, so it is checked here. Bulk operations
        # (bulk_create, update) skip this, so create responses with save().
        if self.run_id is None or self.experiment_model_id is None:
            return  # a missing field is reported by the form or field validation
        if self.run.experiment_id != self.experiment_model.experiment_id:
            raise ValidationError('The run and the model belong to different experiments.')

    def save(self, *args, **kwargs):
        self.clean()
        super().save(*args, **kwargs)
