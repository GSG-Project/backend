import pytest
from rest_framework.test import APIClient

from apps.ai_models.models import AIModel
from apps.comparisons.models import Experiment
from apps.comparisons.serializers import ComparisonResponseSerializer
from apps.comparisons.services.comparison_service import ComparisonService
from apps.comparisons.tests.fakes import FakeJudge, FakeProvider

pytestmark = pytest.mark.django_db

URL = '/api/comparisons/'


@pytest.fixture(autouse=True)
def fake_service(monkeypatch, settings):
    settings.JUDGE_MODEL = 'judge-model'
    AIModel.objects.create(name='One', provider='gemini', api_model_identifier='m-1')
    AIModel.objects.create(name='Two', provider='gemini', api_model_identifier='m-2')
    monkeypatch.setattr(
        'apps.comparisons.views.ComparisonService',
        lambda: ComparisonService(judge_service=FakeJudge(), provider_factory=FakeProvider().factory),
    )


def post(data):
    return APIClient().post(URL, data, format='json')


def test_comparison_returns_results_and_ids():
    response = post({'prompt': 'Explain REST.', 'model_ids': ['m-1', 'm-2']})

    body = response.json()
    assert response.status_code == 200
    assert set(body) == {'experiment_id', 'run_id', 'prompt', 'results', 'evaluation', 'evaluation_error'}
    assert body['experiment_id'] == Experiment.objects.get().pk
    assert [r['model_id'] for r in body['results']] == ['m-1', 'm-2']


@pytest.mark.parametrize('data', [
    {'prompt': '   ', 'model_ids': ['m-1', 'm-2']},
    {'prompt': 'hi', 'model_ids': ['m-1']},
    {'prompt': 'hi', 'model_ids': ['m-1', 'unknown']},
    {'prompt': 'hi', 'model_ids': ['m-1', 'm-1']},
    {'model_ids': ['m-1', 'm-2']},
])
def test_invalid_requests_are_rejected_and_saved_nothing(data):
    response = post(data)

    assert response.status_code == 400
    assert Experiment.objects.count() == 0


def test_the_real_response_matches_the_documented_schema():
    body = post({'prompt': 'Explain REST.', 'model_ids': ['m-1', 'm-2']}).json()

    serializer = ComparisonResponseSerializer(data=body)

    assert serializer.is_valid(), serializer.errors
