"""The judge's overall score, strengths, weaknesses and label are saved with each response."""

from decimal import Decimal

import pytest
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

from apps.ai_models.models import AIModel
from apps.comparisons.models import ModelResponse
from apps.comparisons.services.comparison_service import ComparisonService
from apps.comparisons.tests.fakes import FakeJudge, FakeProvider, provider_error
from apps.evaluations.models import ResponseEvaluation

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def catalog(settings):
    settings.JUDGE_MODEL = 'judge-model'
    AIModel.objects.create(name='One', provider='gemini', api_model_identifier='m-1')
    AIModel.objects.create(name='Two', provider='groq', api_model_identifier='m-2')


def compare(provider=None):
    provider = provider or FakeProvider()
    service = ComparisonService(judge_service=FakeJudge(), provider_factory=provider.factory)
    return service.compare('Explain REST.', ['m-1', 'm-2'])


def test_the_overall_verdict_is_saved_for_every_judged_response():
    compare()

    saved = {
        item.response.experiment_model.ai_model.api_model_identifier: item
        for item in ResponseEvaluation.objects.select_related('response__experiment_model__ai_model')
    }
    assert set(saved) == {'m-1', 'm-2'}
    assert saved['m-1'].label == 'A' and saved['m-2'].label == 'B'
    assert saved['m-1'].overall_score == Decimal('7.5')
    assert saved['m-1'].strengths == 'Clear.' and saved['m-1'].weaknesses == 'Short.'


def test_nothing_is_saved_when_the_judge_did_not_run():
    compare(FakeProvider({'m-2': provider_error()}))

    assert ResponseEvaluation.objects.count() == 0


def test_a_failed_response_cannot_have_an_evaluation():
    compare(FakeProvider({'m-2': provider_error()}))
    failed = ModelResponse.objects.get(status='failed')

    with pytest.raises(ValidationError):
        ResponseEvaluation.objects.create(response=failed, overall_score=5)


def test_a_response_has_one_evaluation():
    compare()
    existing = ResponseEvaluation.objects.first()

    with pytest.raises(IntegrityError), transaction.atomic():
        ResponseEvaluation.objects.create(response=existing.response, overall_score=5)


@pytest.mark.parametrize('score', [0, Decimal('10.01'), 11])
def test_the_overall_score_must_be_between_1_and_10(score):
    compare()
    response = ModelResponse.objects.filter(status='success').first()
    response.summary.delete()

    with pytest.raises(IntegrityError), transaction.atomic():
        ResponseEvaluation.objects.create(response=response, overall_score=score)
