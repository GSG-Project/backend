from decimal import Decimal

import pytest

from apps.ai_models.models import AIModel
from apps.comparisons.models import Experiment, ExperimentModel, ModelResponse, Run
from apps.comparisons.services.comparison_service import ComparisonService
from apps.comparisons.tests.fakes import FakeJudge, FakeProvider, provider_error
from apps.evaluations.models import Evaluation, EvaluationCriterion

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def judge_setting(settings):
    settings.JUDGE_MODEL = 'judge-model'


@pytest.fixture
def catalog():
    AIModel.objects.create(
        name='One', provider='gemini', api_model_identifier='m-1',
        input_price_per_million=Decimal('1'), output_price_per_million=Decimal('2'),
    )
    AIModel.objects.create(name='Two', provider='groq', api_model_identifier='m-2')


def compare(provider=None, judge=None, model_ids=('m-1', 'm-2')):
    provider = provider or FakeProvider()
    service = ComparisonService(judge_service=judge or FakeJudge(), provider_factory=provider.factory)
    return service.compare('Explain REST.', list(model_ids))


def test_successful_comparison_is_fully_saved(catalog):
    payload = compare()

    experiment = Experiment.objects.get()
    run = Run.objects.get()
    assert payload['experiment_id'] == experiment.pk
    assert payload['run_id'] == run.pk
    assert experiment.prompt == 'Explain REST.'
    assert experiment.experiment_models.count() == 2

    assert run.status == Run.Status.COMPLETED
    assert run.completed_at is not None
    assert run.evaluation_status == Run.EvaluationStatus.COMPLETED
    assert run.judge_model.api_model_identifier == 'judge-model'
    assert run.winner.ai_model.api_model_identifier == 'm-1'
    assert run.judge_reasoning == 'A is clearer.'

    first = ModelResponse.objects.get(experiment_model__ai_model__api_model_identifier='m-1')
    assert first.status == ModelResponse.Status.SUCCESS
    assert first.response_text == 'answer from m-1'
    assert (first.input_tokens, first.output_tokens, first.latency_ms) == (10, 20, 120)
    # 10 * 1 / 1M + 20 * 2 / 1M
    assert first.cost == Decimal('0.000050')

    assert Evaluation.objects.count() == 8
    assert Evaluation.objects.get(response=first, criterion__name='accuracy').score == 8


def test_payload_keeps_the_existing_shape_and_adds_cost(catalog):
    payload = compare()

    assert [r['model_id'] for r in payload['results']] == ['m-1', 'm-2']
    first, second = payload['results']
    assert first['status'] == 'success'
    assert first['metadata']['cost'] == pytest.approx(0.00005)
    assert first['metadata']['cost_currency'] == 'USD'
    assert second['metadata']['cost'] is None  # no prices for m-2
    assert payload['evaluation']['winner_model_id'] == 'm-1'
    assert payload['evaluation_error'] is None


def test_each_model_uses_its_own_provider(catalog):
    provider = FakeProvider()

    compare(provider)

    assert sorted(provider.requested_providers) == ['gemini', 'groq']


def test_missing_token_usage_is_saved_as_unavailable(catalog):
    provider = FakeProvider({'m-1': {'input_tokens': None, 'output_tokens': None}})

    payload = compare(provider)

    response = ModelResponse.objects.get(experiment_model__ai_model__api_model_identifier='m-1')
    assert response.input_tokens is None
    assert response.output_tokens is None
    assert response.cost is None
    assert payload['results'][0]['metadata']['cost'] is None


def test_one_failed_model_keeps_the_other_response_and_skips_the_judge(catalog):
    provider = FakeProvider({'m-2': provider_error('rate limited')})

    payload = compare(provider)

    failed = ModelResponse.objects.get(experiment_model__ai_model__api_model_identifier='m-2')
    assert failed.status == ModelResponse.Status.FAILED
    assert failed.response_text is None
    assert failed.error_message == 'ProviderError: rate limited'
    assert ModelResponse.objects.filter(status=ModelResponse.Status.SUCCESS).count() == 1

    run = Run.objects.get()
    assert run.status == Run.Status.COMPLETED
    assert run.evaluation_status == Run.EvaluationStatus.SKIPPED
    assert run.judge_model is None
    assert Evaluation.objects.count() == 0

    assert payload['results'][0]['status'] == 'success'
    assert payload['results'][1]['status'] == 'failed'
    assert payload['results'][1]['error']['code'] == 'provider_error'
    assert payload['evaluation'] is None
    assert 'At least two successful' in payload['evaluation_error']


def test_unexpected_provider_errors_do_not_store_their_message(catalog):
    provider = FakeProvider({'m-1': RuntimeError('key=SECRET'), 'm-2': {}})

    compare(provider)

    failed = ModelResponse.objects.get(experiment_model__ai_model__api_model_identifier='m-1')
    assert failed.error_message == 'Unexpected RuntimeError'


def test_run_fails_when_every_model_fails(catalog):
    provider = FakeProvider({'m-1': provider_error(), 'm-2': provider_error()})

    compare(provider)

    run = Run.objects.get()
    assert run.status == Run.Status.FAILED
    assert run.completed_at is not None
    assert run.evaluation_status == Run.EvaluationStatus.SKIPPED


def test_judge_failure_keeps_the_responses_and_records_the_error(catalog):
    payload = compare(judge=FakeJudge(error=provider_error('invalid JSON')))

    run = Run.objects.get()
    assert run.status == Run.Status.COMPLETED
    assert run.evaluation_status == Run.EvaluationStatus.FAILED
    assert run.evaluation_error == 'ProviderError: invalid JSON'
    assert run.judge_model is not None
    assert run.winner is None
    assert ModelResponse.objects.count() == 2
    assert Evaluation.objects.count() == 0
    assert payload['evaluation'] is None
    assert payload['evaluation_error'] == 'The Judge could not evaluate the answers.'


def test_missing_judge_credentials_only_fail_the_evaluation(catalog, monkeypatch):
    def no_judge():
        raise provider_error('GROQ_API_KEY is not configured.')

    monkeypatch.setattr('apps.comparisons.services.comparison_service.JudgeService', no_judge)
    service = ComparisonService(provider_factory=FakeProvider().factory)

    payload = service.compare('Explain REST.', ['m-1', 'm-2'])

    assert Run.objects.get().evaluation_status == Run.EvaluationStatus.FAILED
    assert len(payload['results']) == 2


def test_unexpected_error_does_not_leave_the_run_running(catalog):
    with pytest.raises(RuntimeError):
        compare(judge=FakeJudge(error=RuntimeError('bug')))

    run = Run.objects.get()
    assert run.status == Run.Status.FAILED
    assert run.completed_at is not None


def test_missing_criteria_are_created_so_scores_are_kept(catalog):
    assert EvaluationCriterion.objects.count() == 0

    compare()

    assert set(EvaluationCriterion.objects.values_list('name', flat=True)) == {
        'accuracy', 'relevance', 'clarity', 'completeness',
    }


def test_a_rerun_of_the_same_models_creates_a_new_experiment(catalog):
    compare()
    compare()

    assert Experiment.objects.count() == 2
    assert Run.objects.count() == 2


@pytest.mark.parametrize('prompt, model_ids, message', [
    ('', ['m-1', 'm-2'], 'Prompt cannot be empty'),
    ('hi', ['m-1'], 'At least two models'),
    ('hi', ['m-1', 'm-1'], 'Duplicate'),
    ('hi', ['m-1', 'unknown'], "Model 'unknown' is not available"),
])
def test_invalid_requests_save_nothing(catalog, prompt, model_ids, message):
    service = ComparisonService(judge_service=FakeJudge(), provider_factory=FakeProvider().factory)

    with pytest.raises(ValueError, match=message):
        service.compare(prompt, model_ids)

    assert Experiment.objects.count() == 0
    assert ExperimentModel.objects.count() == 0
    assert Run.objects.count() == 0
