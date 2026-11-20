"""The working NVIDIA models are seeded, free and not the judge."""
import pytest
from django.core.management import call_command

from apps.ai_models.models import AIModel

pytestmark = pytest.mark.django_db


def test_seed_adds_the_nvidia_models():
    call_command('seed_models')

    models = AIModel.objects.filter(provider='nvidia')
    assert set(models.values_list('api_model_identifier', flat=True)) == {
        'nvidia/nemotron-3-ultra-550b-a55b', 'minimaxai/minimax-m3.1-flash', 'poolside/laguna-xs-2.1',
        'nvidia/nemotron-3.5-lightning-30b-a3b', 'nvidia/nemotron-3-nano-omni-30b-a3b-reasoning',
    }
    assert all(m.is_active and not m.is_judge and m.input_price_per_million == 0 for m in models)
