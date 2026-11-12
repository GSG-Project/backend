"""History returns the judge's evaluation in the same shape as the comparison response."""

import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.ai_models.models import AIModel
from apps.comparisons.services.comparison_service import ComparisonService
from apps.comparisons.tests.fakes import FakeJudge, FakeProvider, provider_error
from apps.evaluations.models import ResponseEvaluation

pytestmark = pytest.mark.django_db

User = get_user_model()
USAGE_FIELDS = ('latency_ms', 'input_tokens', 'output_tokens', 'total_tokens')


@pytest.fixture(autouse=True)
def catalog(settings):
    settings.JUDGE_MODEL = 'judge-model'
    AIModel.objects.create(name='One', provider='gemini', api_model_identifier='m-1')
    AIModel.objects.create(name='Two', provider='groq', api_model_identifier='m-2')


@pytest.fixture
def sara():
    return User.objects.create_user(
        email='sara@example.com', first_name='Sara', password='a-long-passphrase-42',
    )


def compare(user, provider=None):
    provider = provider or FakeProvider()
    service = ComparisonService(judge_service=FakeJudge(), provider_factory=provider.factory)
    return service.compare('Explain REST.', ['m-1', 'm-2'], user=user)


def history_run(user, experiment_id):
    client = APIClient()
    client.force_authenticate(user)
    response = client.get(f'/api/experiments/{experiment_id}/')
    assert response.status_code == 200
    return response.json()['runs'][0]


def test_history_has_the_same_evaluation_as_the_comparison_response(sara):
    live = compare(sara)

    saved = history_run(sara, live['experiment_id'])['evaluation']

    live_evaluation = {k: v for k, v in live['evaluation'].items() if k not in USAGE_FIELDS}
    saved_evaluation = {k: v for k, v in saved.items() if k not in USAGE_FIELDS}
    assert saved_evaluation == live_evaluation
    # The judge's own usage is not stored.
    assert all(saved[field] is None for field in USAGE_FIELDS)
    assert set(saved) == set(live['evaluation'])


def test_the_history_evaluation_includes_what_the_judge_wrote(sara):
    live = compare(sara)

    evaluation = history_run(sara, live['experiment_id'])['evaluation']

    first = evaluation['evaluations'][0]
    assert first['model_id'] == 'm-1' and first['label'] == 'A'
    assert first['overall_score'] == 7.5
    assert first['strengths'] == 'Clear.' and first['weaknesses'] == 'Short.'
    assert evaluation['winner'] == 'A' and evaluation['winner_model_id'] == 'm-1'
    assert evaluation['reasoning'] == 'A is clearer.' and evaluation['judge_model'] == 'judge-model'


def test_runs_judged_before_the_verdict_was_saved_show_what_is_known(sara):
    live = compare(sara)
    ResponseEvaluation.objects.update(label=None, strengths=None, weaknesses=None)

    evaluation = history_run(sara, live['experiment_id'])['evaluation']

    first = evaluation['evaluations'][0]
    assert first['label'] is None and first['strengths'] is None and first['weaknesses'] is None
    assert first['accuracy'] == 8 and first['overall_score'] == 7.5
    assert evaluation['winner'] is None and evaluation['winner_model_id'] == 'm-1'


def test_runs_with_no_saved_verdict_at_all_still_return_the_scores(sara):
    live = compare(sara)
    ResponseEvaluation.objects.all().delete()

    first = history_run(sara, live['experiment_id'])['evaluation']['evaluations'][0]

    assert first['overall_score'] is None and first['accuracy'] == 8


def test_there_is_no_evaluation_when_the_judge_did_not_run(sara):
    live = compare(sara, FakeProvider({'m-2': provider_error()}))

    run = history_run(sara, live['experiment_id'])

    assert run['evaluation'] is None and run['evaluation_status'] == 'skipped'


def test_the_existing_fields_are_unchanged(sara):
    live = compare(sara)

    run = history_run(sara, live['experiment_id'])

    assert run['judge_reasoning'] == 'A is clearer.'
    assert [s['criterion'] for s in run['results'][0]['scores']] == [
        'accuracy', 'relevance', 'clarity', 'completeness',
    ]


def test_the_evaluation_does_not_add_a_query_per_run(sara, django_assert_max_num_queries):
    live = compare(sara)
    for _ in range(3):
        compare(sara)

    client = APIClient()
    client.force_authenticate(sara)
    with django_assert_max_num_queries(9):
        response = client.get(f"/api/experiments/{live['experiment_id']}/")

    assert response.status_code == 200
