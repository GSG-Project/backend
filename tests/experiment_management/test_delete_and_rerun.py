from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.ai_models.models import AIModel
from apps.comparisons.models import Experiment, ExperimentModel, ModelResponse, Run
from apps.comparisons.services.comparison_service import ComparisonService
from apps.comparisons.tests.fakes import FakeJudge, FakeProvider, provider_error
from apps.evaluations.models import Evaluation

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture(autouse=True)
def catalog(settings):
    settings.JUDGE_MODEL = 'judge-model'
    AIModel.objects.create(
        name='One', provider='gemini', api_model_identifier='m-1',
        input_price_per_million=Decimal('1'), output_price_per_million=Decimal('2'),
    )
    AIModel.objects.create(name='Two', provider='groq', api_model_identifier='m-2')


@pytest.fixture
def sara():
    return User.objects.create_user(email='sara@example.com', name='Sara', password='a-long-passphrase-42')


@pytest.fixture
def omar():
    return User.objects.create_user(email='omar@example.com', name='Omar', password='a-long-passphrase-42')


@pytest.fixture
def provider(monkeypatch):
    """The provider the rerun endpoint uses. Tests can change its behaviors."""
    fake = FakeProvider()
    monkeypatch.setattr(
        'apps.comparisons.history_views.ComparisonService',
        lambda: ComparisonService(judge_service=FakeJudge(), provider_factory=fake.factory),
    )
    return fake


def client_for(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def compare(user=None, prompt='Explain REST.', model_ids=('m-1', 'm-2')):
    service = ComparisonService(judge_service=FakeJudge(), provider_factory=FakeProvider().factory)
    return service.compare(prompt, list(model_ids), user=user)


def detail_url(experiment_id):
    return f'/api/experiments/{experiment_id}/'


def rerun_url(experiment_id):
    return f'/api/experiments/{experiment_id}/rerun/'


# Delete

def test_delete_requires_a_token(sara):
    experiment_id = compare(sara)['experiment_id']

    assert client_for().delete(detail_url(experiment_id)).status_code == 401
    assert Experiment.objects.filter(pk=experiment_id).exists()


def test_the_owner_deletes_the_experiment_and_everything_in_it(sara):
    experiment_id = compare(sara)['experiment_id']
    other_id = compare(sara, prompt='Keep me')['experiment_id']

    response = client_for(sara).delete(detail_url(experiment_id))

    assert response.status_code == 204
    assert not Experiment.objects.filter(pk=experiment_id).exists()
    assert not Run.objects.filter(experiment_id=experiment_id).exists()
    assert not ExperimentModel.objects.filter(experiment_id=experiment_id).exists()
    assert not ModelResponse.objects.filter(run__experiment_id=experiment_id).exists()
    assert not Evaluation.objects.filter(response__run__experiment_id=experiment_id).exists()
    # Other experiments and the models themselves are untouched.
    assert Experiment.objects.filter(pk=other_id).exists()
    assert AIModel.objects.filter(api_model_identifier__in=['m-1', 'm-2']).count() == 2
    assert client_for(sara).get(detail_url(experiment_id)).status_code == 404


@pytest.mark.parametrize('owner', ['other', 'nobody'])
def test_nobody_else_can_delete_an_experiment(sara, omar, owner):
    experiment_id = compare(omar if owner == 'other' else None)['experiment_id']

    assert client_for(sara).delete(detail_url(experiment_id)).status_code == 404
    assert Experiment.objects.filter(pk=experiment_id).exists()


def test_deleting_an_unknown_experiment_is_not_found(sara):
    assert client_for(sara).delete(detail_url(9999)).status_code == 404


# Rerun

def test_rerun_requires_a_token(sara, provider):
    experiment_id = compare(sara)['experiment_id']

    assert client_for().post(rerun_url(experiment_id)).status_code == 401
    assert Run.objects.filter(experiment_id=experiment_id).count() == 1


def test_rerun_adds_a_run_to_the_same_experiment(sara, provider):
    first = compare(sara)

    response = client_for(sara).post(rerun_url(first['experiment_id']))

    assert response.status_code == 201
    body = response.json()
    assert body['experiment_id'] == first['experiment_id']
    assert body['run_id'] != first['run_id']
    assert body['prompt'] == 'Explain REST.'
    assert [result['model_id'] for result in body['results']] == ['m-1', 'm-2']
    assert body['evaluation']['winner_model_id'] == 'm-1'
    # No new experiment, and the first run is kept.
    assert Experiment.objects.count() == 1
    assert Run.objects.filter(experiment_id=first['experiment_id']).count() == 2
    new_run = Run.objects.get(pk=body['run_id'])
    assert new_run.status == Run.Status.COMPLETED
    assert new_run.evaluation_status == Run.EvaluationStatus.COMPLETED
    assert new_run.responses.count() == 2


def test_rerun_keeps_the_original_model_order(sara, provider):
    experiment_id = compare(sara, model_ids=('m-2', 'm-1'))['experiment_id']

    body = client_for(sara).post(rerun_url(experiment_id)).json()

    assert [result['model_id'] for result in body['results']] == ['m-2', 'm-1']


def test_the_new_run_shows_up_in_the_history(sara, provider):
    experiment_id = compare(sara)['experiment_id']
    run_id = client_for(sara).post(rerun_url(experiment_id)).json()['run_id']

    detail = client_for(sara).get(detail_url(experiment_id)).json()
    listed = client_for(sara).get('/api/experiments/').json()['results'][0]

    assert detail['runs'][0]['id'] == run_id and len(detail['runs']) == 2
    assert listed['run_count'] == 2 and listed['latest_run']['id'] == run_id


def test_rerun_reports_a_failed_model_without_failing(sara, provider):
    experiment_id = compare(sara)['experiment_id']
    provider.behaviors['m-2'] = provider_error()

    response = client_for(sara).post(rerun_url(experiment_id))

    assert response.status_code == 201
    body = response.json()
    assert body['results'][1]['status'] == 'failed'
    assert body['evaluation'] is None and body['evaluation_error']
    assert Run.objects.get(pk=body['run_id']).evaluation_status == Run.EvaluationStatus.SKIPPED


def test_rerun_rejects_a_deactivated_model(sara, provider):
    experiment_id = compare(sara)['experiment_id']
    AIModel.objects.filter(api_model_identifier='m-2').update(is_active=False)

    response = client_for(sara).post(rerun_url(experiment_id))

    assert response.status_code == 400
    assert 'm-2' in response.json()['error']
    assert Run.objects.filter(experiment_id=experiment_id).count() == 1


@pytest.mark.parametrize('owner', ['other', 'nobody'])
def test_nobody_else_can_rerun_an_experiment(sara, omar, provider, owner):
    experiment_id = compare(omar if owner == 'other' else None)['experiment_id']

    assert client_for(sara).post(rerun_url(experiment_id)).status_code == 404
    assert Run.objects.filter(experiment_id=experiment_id).count() == 1


def test_rerunning_an_unknown_experiment_is_not_found(sara, provider):
    assert client_for(sara).post(rerun_url(9999)).status_code == 404


def test_an_unexpected_error_closes_the_run_as_failed(sara, monkeypatch):
    experiment_id = compare(sara)['experiment_id']

    def explode(*args, **kwargs):
        raise RuntimeError('boom')

    monkeypatch.setattr(ComparisonService, '_generate_all', explode)

    response = client_for(sara).post(rerun_url(experiment_id))

    assert response.status_code == 500
    assert 'boom' not in response.json()['error']
    newest = Run.objects.filter(experiment_id=experiment_id).order_by('-id').first()
    assert newest.status == Run.Status.FAILED and newest.completed_at is not None
