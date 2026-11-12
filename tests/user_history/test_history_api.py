from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.ai_models.models import AIModel
from apps.comparisons.models import Experiment, Run
from apps.comparisons.services.comparison_service import ComparisonService
from apps.comparisons.tests.fakes import FakeJudge, FakeProvider, provider_error

pytestmark = pytest.mark.django_db

User = get_user_model()
LIST_URL = '/api/experiments/'


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
    return User.objects.create_user(
        email='sara@example.com', first_name='Sara', password='a-long-passphrase-42',
    )


@pytest.fixture
def omar():
    return User.objects.create_user(
        email='omar@example.com', first_name='Omar', password='a-long-passphrase-42',
    )


def client_for(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def compare(user=None, prompt='Explain REST.', provider=None):
    provider = provider or FakeProvider()
    service = ComparisonService(judge_service=FakeJudge(), provider_factory=provider.factory)
    return service.compare(prompt, ['m-1', 'm-2'], user=user)


# The list

def test_the_list_requires_a_token():
    assert client_for().get(LIST_URL).status_code == 401


def test_the_list_only_shows_my_experiments_newest_first(sara, omar):
    first = compare(sara, prompt='First')['experiment_id']
    compare(omar, prompt='Not mine')
    compare(None, prompt='Anonymous')
    second = compare(sara, prompt='Second')['experiment_id']

    body = client_for(sara).get(LIST_URL).json()

    assert body['count'] == 2
    assert [item['id'] for item in body['results']] == [second, first]
    assert [item['prompt'] for item in body['results']] == ['Second', 'First']


def test_the_list_summarizes_models_runs_and_the_winner(sara):
    compare(sara)

    item = client_for(sara).get(LIST_URL).json()['results'][0]

    assert [m['id'] for m in item['models']] == ['m-1', 'm-2']
    assert item['run_count'] == 1
    assert item['latest_run']['status'] == 'completed'
    assert item['latest_run']['evaluation_status'] == 'completed'
    assert item['latest_run']['winner_model_id'] == 'm-1'


def test_the_list_shows_no_winner_when_one_model_failed(sara):
    compare(sara, provider=FakeProvider({'m-2': provider_error()}))

    item = client_for(sara).get(LIST_URL).json()['results'][0]

    assert item['latest_run']['evaluation_status'] == 'skipped'
    assert item['latest_run']['winner_model_id'] is None


def test_the_list_is_paginated(sara):
    for index in range(25):
        compare(sara, prompt=f'Prompt {index}')
    client = client_for(sara)

    first = client.get(LIST_URL).json()
    second = client.get(LIST_URL, {'page': 2}).json()
    small = client.get(LIST_URL, {'page_size': 5}).json()

    assert first['count'] == 25 and len(first['results']) == 20 and first['next']
    assert len(second['results']) == 5 and second['next'] is None
    assert len(small['results']) == 5


def test_the_list_does_not_query_per_experiment(sara, django_assert_max_num_queries):
    for index in range(6):
        compare(sara, prompt=f'Prompt {index}')

    with django_assert_max_num_queries(8):
        response = client_for(sara).get(LIST_URL)

    assert response.status_code == 200 and len(response.json()['results']) == 6


# The detail

def detail_url(experiment_id):
    return f'{LIST_URL}{experiment_id}/'


def test_the_detail_requires_a_token(sara):
    experiment_id = compare(sara)['experiment_id']

    assert client_for().get(detail_url(experiment_id)).status_code == 401


def test_the_detail_returns_the_full_results_and_scores(sara):
    experiment_id = compare(sara)['experiment_id']

    body = client_for(sara).get(detail_url(experiment_id)).json()

    assert body['id'] == experiment_id and body['prompt'] == 'Explain REST.'
    assert len(body['runs']) == 1
    run = body['runs'][0]
    assert run['winner_model_id'] == 'm-1'
    assert run['judge_reasoning'] == 'A is clearer.'
    first, second = run['results']
    assert first['model_id'] == 'm-1' and first['answer'] == 'answer from m-1'
    assert first['metadata'] == {
        'latency_ms': 120, 'input_tokens': 10, 'output_tokens': 20, 'total_tokens': 30,
        'cost': 0.00005, 'cost_currency': 'USD',
    }
    assert first['error'] is None
    scores = {score['criterion']: score['score'] for score in first['scores']}
    assert scores == {'accuracy': 8, 'relevance': 9, 'clarity': 7, 'completeness': 6}
    assert second['metadata']['cost'] is None  # model two has no price


def test_the_detail_shows_failed_models_without_an_answer(sara):
    experiment_id = compare(sara, provider=FakeProvider({'m-2': provider_error()}))['experiment_id']

    run = client_for(sara).get(detail_url(experiment_id)).json()['runs'][0]

    failed = run['results'][1]
    assert failed['status'] == 'failed'
    assert failed['answer'] is None and failed['metadata'] is None
    assert failed['error']['code'] == 'provider_error' and failed['error']['message']
    assert failed['scores'] == []
    assert run['evaluation_status'] == 'skipped'


def test_the_detail_lists_every_run_newest_first(sara):
    experiment_id = compare(sara)['experiment_id']
    experiment = Experiment.objects.get(pk=experiment_id)
    earlier = experiment.runs.get()
    later = Run.objects.create(experiment=experiment, status=Run.Status.RUNNING)

    body = client_for(sara).get(detail_url(experiment_id)).json()

    assert [run['id'] for run in body['runs']] == [later.pk, earlier.pk]
    assert client_for(sara).get(LIST_URL).json()['results'][0]['run_count'] == 2


@pytest.mark.parametrize('owner', ['other', 'nobody'])
def test_someone_elses_experiment_is_not_found(sara, omar, owner):
    experiment_id = compare(omar if owner == 'other' else None)['experiment_id']

    assert client_for(sara).get(detail_url(experiment_id)).status_code == 404


def test_an_unknown_experiment_is_not_found(sara):
    assert client_for(sara).get(detail_url(9999)).status_code == 404


def test_the_detail_does_not_query_per_run_or_response(sara, django_assert_max_num_queries):
    experiment_id = compare(sara)['experiment_id']
    experiment = Experiment.objects.get(pk=experiment_id)
    for _ in range(3):
        Run.objects.create(experiment=experiment, status=Run.Status.RUNNING)

    with django_assert_max_num_queries(8):
        response = client_for(sara).get(detail_url(experiment_id))

    assert response.status_code == 200 and len(response.json()['runs']) == 4
