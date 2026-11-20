"""The seed offers Groq models to compare, and switches off models providers retired."""
import pytest
from django.core.management import call_command

from apps.ai_models.models import AIModel

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def judge(settings):
    settings.JUDGE_MODEL = 'openai/gpt-oss-120b'


def test_groq_models_are_seeded_free_and_selectable():
    call_command('seed_models')

    compared = AIModel.objects.filter(provider='groq', is_judge=False)
    assert set(compared.values_list('api_model_identifier', flat=True)) == {
        'qwen/qwen3.8-27b', 'openai/gpt-oss-20b', 'allam-2-7b',
    }
    assert all(m.is_active and m.input_price_per_million == 0 for m in compared)


def test_judge_is_not_offered_for_comparison():
    call_command('seed_models')

    judge = AIModel.objects.get(api_model_identifier='openai/gpt-oss-120b')
    assert judge.is_judge


RETIRED = [
    'cohere/north-mini-code:free',
    'inclusionai/ling-3.2-flash:free',
    'google/gemma-4-31b-it:free',
]


@pytest.mark.parametrize('identifier', RETIRED)
def test_retired_model_is_switched_off_not_deleted(identifier):
    AIModel.objects.create(name='Old', provider='openrouter', api_model_identifier=identifier, is_active=True)

    call_command('seed_models')

    assert AIModel.objects.get(api_model_identifier=identifier).is_active is False


def test_retired_models_are_not_created_on_a_new_database():
    call_command('seed_models')

    assert not AIModel.objects.filter(api_model_identifier__in=RETIRED).exists()


def test_working_openrouter_models_stay_active():
    call_command('seed_models')

    active = AIModel.objects.filter(provider='openrouter', is_active=True)
    assert set(active.values_list('api_model_identifier', flat=True)) == {
        'nvidia/nemotron-3-ultra-550b-a55b:free', 'baidu/ernie-5.5-flash-preview:free',
    }


def test_reseeding_keeps_admin_changes():
    call_command('seed_models')
    AIModel.objects.filter(api_model_identifier='allam-2-7b').update(is_active=False, name='Renamed')

    call_command('seed_models')

    allam = AIModel.objects.get(api_model_identifier='allam-2-7b')
    assert (allam.is_active, allam.name) == (False, 'Renamed')
