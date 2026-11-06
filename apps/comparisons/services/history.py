"""Reads saved experiments. Every query is limited to one user, so nobody sees someone else's history."""

from django.db.models import Count, Prefetch

from apps.comparisons.models import Experiment, ModelResponse, Run


def newest_runs_first():
    return Run.objects.select_related('winner__ai_model').order_by('-started_at', '-id')


def list_experiments(user):
    """The user's experiments, newest first, with what the list needs loaded up front."""
    return (
        Experiment.objects.filter(user=user)
        .annotate(run_count=Count('runs'))
        .prefetch_related(
            'ai_models',
            Prefetch('runs', queryset=newest_runs_first()),
        )
        .order_by('-created_at', '-id')
    )


def experiment_detail_queryset(user):
    """The user's experiments with every run, response and score loaded up front."""
    responses = ModelResponse.objects.select_related(
        'experiment_model__ai_model',
    ).prefetch_related('evaluations__criterion').order_by('experiment_model_id')
    runs = newest_runs_first().prefetch_related(Prefetch('responses', queryset=responses))
    return Experiment.objects.filter(user=user).prefetch_related('ai_models', Prefetch('runs', queryset=runs))
