import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.ai_models.models import AIModel
from apps.comparisons.models import Experiment, ExperimentModel, ModelResponse, Run

pytestmark = pytest.mark.django_db


@pytest.fixture
def models_pair():
    return [
        AIModel.objects.create(name=f'M{i}', provider='gemini', api_model_identifier=f'm-{i}')
        for i in (1, 2)
    ]


@pytest.fixture
def experiment(models_pair):
    experiment = Experiment.objects.create(prompt='Explain REST.')
    for model in models_pair:
        ExperimentModel.objects.create(experiment=experiment, ai_model=model)
    return experiment


def test_same_model_cannot_be_picked_twice(experiment, models_pair):
    with pytest.raises(IntegrityError), transaction.atomic():
        ExperimentModel.objects.create(experiment=experiment, ai_model=models_pair[0])


def test_response_keeps_unavailable_metrics_as_null(experiment):
    run = Run.objects.create(experiment=experiment)
    em = experiment.experiment_models.first()

    response = ModelResponse.objects.create(run=run, experiment_model=em, response_text='ok', status='success')

    assert response.input_tokens is None
    assert response.latency_ms is None
    assert response.cost is None


def test_one_response_per_run_and_model(experiment):
    run = Run.objects.create(experiment=experiment)
    em = experiment.experiment_models.first()
    ModelResponse.objects.create(run=run, experiment_model=em, response_text='a', status='success')

    with pytest.raises(IntegrityError), transaction.atomic():
        ModelResponse.objects.create(run=run, experiment_model=em, response_text='b', status='success')


def test_successful_response_requires_text(experiment):
    run = Run.objects.create(experiment=experiment)
    em = experiment.experiment_models.first()

    with pytest.raises(IntegrityError), transaction.atomic():
        ModelResponse.objects.create(run=run, experiment_model=em, status='success')


def test_failed_response_may_have_no_text(experiment):
    run = Run.objects.create(experiment=experiment)
    em = experiment.experiment_models.first()

    response = ModelResponse.objects.create(
        run=run, experiment_model=em, status='failed', error_message='timeout',
    )

    assert response.response_text is None


def test_response_cannot_mix_experiments(experiment, models_pair):
    other = Experiment.objects.create(prompt='Other prompt.')
    other_em = ExperimentModel.objects.create(experiment=other, ai_model=models_pair[0])
    run = Run.objects.create(experiment=experiment)

    with pytest.raises(ValidationError):
        ModelResponse.objects.create(run=run, experiment_model=other_em, response_text='x', status='success')


def test_run_starts_with_pending_evaluation_and_no_judge(experiment):
    run = Run.objects.create(experiment=experiment)

    assert run.evaluation_status == Run.EvaluationStatus.PENDING
    assert run.judge_model is None


def test_rerun_keeps_earlier_results(experiment):
    em = experiment.experiment_models.first()
    first, second = Run.objects.create(experiment=experiment), Run.objects.create(experiment=experiment)
    ModelResponse.objects.create(run=first, experiment_model=em, response_text='a', status='success')
    ModelResponse.objects.create(run=second, experiment_model=em, response_text='b', status='success')

    assert experiment.runs.count() == 2
    assert first.responses.get().response_text == 'a'


def test_clean_skips_check_when_fields_are_missing(experiment):
    run = Run.objects.create(experiment=experiment)

    ModelResponse(run=run, status='failed').clean()  # must not raise
    ModelResponse(status='failed').clean()
