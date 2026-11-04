import pytest
from rest_framework.test import APIClient

from apps.ai_models.models import AIModel

pytestmark = pytest.mark.django_db


def test_model_list_returns_only_selectable_models():
    AIModel.objects.create(name='Usable', provider='gemini', api_model_identifier='usable')
    AIModel.objects.create(name='Off', provider='gemini', api_model_identifier='off', is_active=False)
    AIModel.objects.create(name='Judge', provider='groq', api_model_identifier='judge', is_judge=True)

    response = APIClient().get('/api/models/')

    assert response.status_code == 200
    assert response.json() == {
        'models': [{'id': 'usable', 'name': 'Usable', 'provider': 'gemini', 'is_active': True}],
    }
