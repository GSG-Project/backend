import pytest

from apps.ai_models.models import AIModel
from apps.ai_models.services.catalog import get_judge_model, get_selectable_model, get_selectable_models

pytestmark = pytest.mark.django_db


def make_model(identifier='m-1', **kwargs):
    return AIModel.objects.create(
        name=identifier, provider='gemini', api_model_identifier=identifier, **kwargs,
    )


def test_selectable_models_exclude_inactive_and_judges():
    make_model('usable')
    make_model('inactive', is_active=False)
    make_model('judge', is_judge=True)

    assert [m.api_model_identifier for m in get_selectable_models()] == ['usable']
    assert get_selectable_model('usable') is not None
    assert get_selectable_model('inactive') is None
    assert get_selectable_model('judge') is None
    assert get_selectable_model('missing') is None


def test_judge_model_is_created_once_from_settings(settings):
    settings.JUDGE_MODEL = 'judge-model'

    first = get_judge_model()
    second = get_judge_model()

    assert first.pk == second.pk
    assert first.is_judge is True
    assert AIModel.objects.filter(api_model_identifier='judge-model').count() == 1
