import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import IntegrityError, transaction

from apps.ai_models.models import AIModel
from apps.comparisons.models import Experiment, ExperimentModel, ModelResponse, Run
from apps.evaluations.models import Evaluation, EvaluationCriterion

pytestmark = pytest.mark.django_db


@pytest.fixture
def response():
    model = AIModel.objects.create(name='M', provider='gemini', api_model_identifier='m-1')
    experiment = Experiment.objects.create(prompt='Explain REST.')
    em = ExperimentModel.objects.create(experiment=experiment, ai_model=model)
    run = Run.objects.create(experiment=experiment)
    return ModelResponse.objects.create(run=run, experiment_model=em, response_text='ok', status='success')


@pytest.fixture
def criterion():
    return EvaluationCriterion.objects.create(name='accuracy')


def test_one_score_per_response_and_criterion(response, criterion):
    Evaluation.objects.create(response=response, criterion=criterion, score=8)

    with pytest.raises(IntegrityError), transaction.atomic():
        Evaluation.objects.create(response=response, criterion=criterion, score=9)


@pytest.mark.parametrize('score', [0, 11])
def test_score_must_be_between_1_and_10(response, criterion, score):
    with pytest.raises(IntegrityError), transaction.atomic():
        Evaluation.objects.create(response=response, criterion=criterion, score=score)


def test_criterion_with_scores_cannot_be_deleted(response, criterion):
    from django.db.models import ProtectedError

    Evaluation.objects.create(response=response, criterion=criterion, score=8)

    with pytest.raises(ProtectedError):
        criterion.delete()


def test_deleting_a_response_deletes_its_scores(response, criterion):
    Evaluation.objects.create(response=response, criterion=criterion, score=8)

    response.delete()

    assert Evaluation.objects.count() == 0


def test_seed_criteria_is_idempotent():
    call_command('seed_criteria')
    call_command('seed_criteria')

    assert EvaluationCriterion.objects.count() == 4


def test_failed_response_cannot_be_scored(response, criterion):
    response.status = 'failed'
    response.response_text = None
    response.save()

    with pytest.raises(ValidationError):
        Evaluation.objects.create(response=response, criterion=criterion, score=5)
