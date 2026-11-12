import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

from apps.ai_models.models import AIModel
from apps.comparisons.models import Experiment
from apps.comparisons.services.comparison_service import ComparisonService
from apps.comparisons.tests.fakes import FakeJudge, FakeProvider

pytestmark = pytest.mark.django_db

User = get_user_model()


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


def client_for(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def test_a_signed_in_comparison_is_saved_with_its_owner(sara, monkeypatch):
    monkeypatch.setattr(
        'apps.comparisons.views.ComparisonService',
        lambda: ComparisonService(judge_service=FakeJudge(), provider_factory=FakeProvider().factory),
    )

    response = client_for(sara).post(
        '/api/comparisons/', {'prompt': 'Explain REST.', 'model_ids': ['m-1', 'm-2']}, format='json',
    )

    assert response.status_code == 200
    assert Experiment.objects.get().user == sara


def test_an_anonymous_comparison_has_no_owner(monkeypatch):
    monkeypatch.setattr(
        'apps.comparisons.views.ComparisonService',
        lambda: ComparisonService(judge_service=FakeJudge(), provider_factory=FakeProvider().factory),
    )

    response = client_for().post(
        '/api/comparisons/', {'prompt': 'Explain REST.', 'model_ids': ['m-1', 'm-2']}, format='json',
    )

    assert response.status_code == 200
    assert Experiment.objects.get().user is None
