import pytest
from django.core.management import call_command
from django.db import IntegrityError

from apps.ai_models.models import AIModel

pytestmark = pytest.mark.django_db


def test_api_model_identifier_is_unique():
    AIModel.objects.create(name='A', provider='gemini', api_model_identifier='m-1')

    with pytest.raises(IntegrityError):
        AIModel.objects.create(name='B', provider='gemini', api_model_identifier='m-1')


def test_prices_are_unknown_by_default():
    model = AIModel.objects.create(name='A', provider='gemini', api_model_identifier='m-1')

    assert model.input_price_per_million is None
    assert model.output_price_per_million is None


def test_seed_models_is_idempotent_and_keeps_prices(settings):
    settings.JUDGE_MODEL = 'judge-model'
    call_command('seed_models')
    count = AIModel.objects.count()
    AIModel.objects.filter(api_model_identifier='gemini-3.8-flash').update(
        input_price_per_million='0.30',
    )

    call_command('seed_models')

    assert AIModel.objects.count() == count
    assert str(AIModel.objects.get(api_model_identifier='gemini-3.8-flash').input_price_per_million) == '0.300000'


def test_seed_models_marks_the_judge(settings):
    settings.JUDGE_MODEL = 'judge-model'

    call_command('seed_models')

    judge = AIModel.objects.get(api_model_identifier='judge-model')
    assert judge.is_judge is True
    assert judge.is_active is True
    assert AIModel.objects.filter(is_judge=True).count() == 1


def test_seed_models_does_not_undo_admin_changes(settings):
    settings.JUDGE_MODEL = 'judge-model'
    call_command('seed_models')
    AIModel.objects.filter(api_model_identifier='gemini-3.8-flash').update(is_active=False, name='Renamed')

    call_command('seed_models')

    model = AIModel.objects.get(api_model_identifier='gemini-3.8-flash')
    assert model.is_active is False
    assert model.name == 'Renamed'
