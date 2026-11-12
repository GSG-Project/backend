"""Migration 0002 gives runs judged before the verdict was stored an overall score."""

from decimal import Decimal

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone

BEFORE = [('evaluations', '0001_initial'), ('comparisons', '0004_experiment_user')]
AFTER = [('evaluations', '0002_response_evaluation'), ('comparisons', '0004_experiment_user')]


@pytest.fixture
def migrate(transactional_db):
    def run(target):
        MigrationExecutor(connection).migrate(target)
        return MigrationExecutor(connection).loader.project_state(target).apps

    yield run
    # Leave the database at the latest migration for the tests that follow.
    executor = MigrationExecutor(connection)
    executor.migrate(executor.loader.graph.leaf_nodes())


def judged_response(apps, scores, status='success'):
    AIModel = apps.get_model('ai_models', 'AIModel')
    Experiment = apps.get_model('comparisons', 'Experiment')
    ExperimentModel = apps.get_model('comparisons', 'ExperimentModel')
    Run = apps.get_model('comparisons', 'Run')
    ModelResponse = apps.get_model('comparisons', 'ModelResponse')
    Criterion = apps.get_model('evaluations', 'EvaluationCriterion')
    Evaluation = apps.get_model('evaluations', 'Evaluation')

    model = AIModel.objects.create(name='One', provider='gemini', api_model_identifier='m-1')
    experiment = Experiment.objects.create(prompt='Hi')
    experiment_model = ExperimentModel.objects.create(experiment=experiment, ai_model=model)
    run = Run.objects.create(experiment=experiment, status='completed', completed_at=timezone.now())
    response = ModelResponse.objects.create(
        run=run, experiment_model=experiment_model, response_text='hello', status=status,
    )
    for index, score in enumerate(scores):
        criterion = Criterion.objects.create(name=f'c{index}')
        Evaluation.objects.create(response=response, criterion=criterion, score=score)
    return response.pk


@pytest.mark.parametrize('scores, expected', [
    ([9, 9, 9, 8], Decimal('8.75')),
    ([9, 9, 8, 9], Decimal('8.75')),
    ([7, 7, 7, 7], Decimal('7.00')),
    ([8, 8, 8, 9], Decimal('8.25')),
    ([10, 9, 9], Decimal('9.33')),
])
def test_the_overall_score_is_the_average_of_the_saved_scores(migrate, scores, expected):
    old_apps = migrate(BEFORE)
    response_id = judged_response(old_apps, scores)

    new_apps = migrate(AFTER)

    summary = new_apps.get_model('evaluations', 'ResponseEvaluation').objects.get(response_id=response_id)
    assert summary.overall_score == expected
    assert summary.label is None and summary.strengths is None and summary.weaknesses is None


def test_responses_that_were_never_scored_get_nothing(migrate):
    old_apps = migrate(BEFORE)
    judged_response(old_apps, [])

    new_apps = migrate(AFTER)

    assert new_apps.get_model('evaluations', 'ResponseEvaluation').objects.count() == 0


def test_the_migration_can_be_reversed(migrate):
    migrate(BEFORE)
    new_apps = migrate(AFTER)
    judged_response(new_apps, [9, 9, 9, 8])

    old_apps = migrate(BEFORE)

    assert old_apps.get_model('evaluations', 'Evaluation').objects.count() == 4
