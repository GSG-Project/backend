"""Saves experiments, runs, and model responses."""

from django.db import transaction
from django.utils import timezone

from apps.ai_models.services.pricing_service import calculate_cost
from apps.comparisons.models import Experiment, ExperimentModel, ModelResponse, Run
from apps.comparisons.services.metrics_service import normalize_latency_ms, normalize_token_count

MAX_ERROR_LENGTH = 500


def start_run(prompt: str, ai_models: list) -> tuple[Run, dict]:
    """Create the experiment and its first run. Returns the run and a model id -> ExperimentModel map."""
    with transaction.atomic():
        experiment = Experiment.objects.create(prompt=prompt)
        experiment_models = ExperimentModel.objects.bulk_create(
            ExperimentModel(experiment=experiment, ai_model=ai_model) for ai_model in ai_models
        )
        run = Run.objects.create(experiment=experiment, status=Run.Status.RUNNING)

    return run, {em.ai_model.api_model_identifier: em for em in experiment_models}


def save_response(run: Run, experiment_model: ExperimentModel, result: dict) -> ModelResponse:
    """Save one model's outcome. result has the shape returned by ComparisonService."""
    ai_model = experiment_model.ai_model

    if result['status'] != 'success':
        return ModelResponse.objects.create(
            run=run,
            experiment_model=experiment_model,
            status=ModelResponse.Status.FAILED,
            error_message=result.get('error_detail', '')[:MAX_ERROR_LENGTH],
        )

    metadata = result['metadata']
    input_tokens = normalize_token_count(metadata['input_tokens'])
    output_tokens = normalize_token_count(metadata['output_tokens'])

    return ModelResponse.objects.create(
        run=run,
        experiment_model=experiment_model,
        response_text=result['answer'],
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        latency_ms=normalize_latency_ms(metadata['latency_ms']),
        cost=calculate_cost(ai_model, input_tokens, output_tokens),
        status=ModelResponse.Status.SUCCESS,
    )


def finish_run(
    run: Run,
    responses: list,
    evaluation_status: str,
    evaluation_error: str = '',
    judge_model=None,
    winner: ExperimentModel | None = None,
    judge_reasoning: str = '',
) -> None:
    """Close the run: it failed only if no model answered."""
    any_success = any(r.status == ModelResponse.Status.SUCCESS for r in responses)
    run.status = Run.Status.COMPLETED if any_success else Run.Status.FAILED
    run.completed_at = timezone.now()
    run.evaluation_status = evaluation_status
    run.evaluation_error = evaluation_error[:MAX_ERROR_LENGTH]
    run.judge_model = judge_model
    run.winner = winner
    run.judge_reasoning = judge_reasoning
    run.save()


def fail_run(run: Run) -> None:
    """Close a run that stopped on an unexpected error so it is not left running."""
    run.status = Run.Status.FAILED
    run.completed_at = timezone.now()
    run.save()
