"""Reads saved experiments. Every query is limited to one user, so nobody sees someone else's history."""

from django.db.models import Count, Prefetch

from apps.comparisons.models import Experiment, ModelResponse, Run
from apps.evaluations.criteria import CRITERIA


def newest_runs_first():
    return Run.objects.select_related('winner__ai_model', 'judge_model').order_by('-started_at', '-id')


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
        'experiment_model__ai_model', 'summary',
    ).prefetch_related('evaluations__criterion').order_by('experiment_model_id')
    runs = newest_runs_first().prefetch_related(Prefetch('responses', queryset=responses))
    return Experiment.objects.filter(user=user).prefetch_related('ai_models', Prefetch('runs', queryset=runs))


def build_evaluation(run):
    """The judge's evaluation of a run, in the same shape as the comparison response.

    Returns None unless the evaluation completed. Fields that were not saved for runs
    judged before they were stored (label, strengths, weaknesses) are None. Uses the
    data loaded by experiment_detail_queryset.
    """
    if run.evaluation_status != Run.EvaluationStatus.COMPLETED:
        return None

    labels_by_experiment_model = {}
    evaluations = []
    for response in run.responses.all():
        scores = {evaluation.criterion.name: evaluation.score for evaluation in response.evaluations.all()}
        summary = getattr(response, 'summary', None)
        if not scores and summary is None:
            continue  # this response was not judged (it failed)
        labels_by_experiment_model[response.experiment_model_id] = summary.label if summary else None
        evaluations.append({
            'model_id': response.experiment_model.ai_model.api_model_identifier,
            'label': summary.label if summary else None,
            **{name: scores.get(name) for name, _ in CRITERIA},
            'overall_score': float(summary.overall_score) if summary else None,
            'strengths': summary.strengths if summary else None,
            'weaknesses': summary.weaknesses if summary else None,
        })

    winner = run.winner
    return {
        'winner': labels_by_experiment_model.get(winner.pk) if winner else None,
        'winner_model_id': winner.ai_model.api_model_identifier if winner else None,
        'reasoning': run.judge_reasoning,
        'evaluations': evaluations,
        'judge_model': run.judge_model.api_model_identifier if run.judge_model else None,
        # The judge's own usage is not stored.
        'latency_ms': None,
        'input_tokens': None,
        'output_tokens': None,
        'total_tokens': None,
    }
