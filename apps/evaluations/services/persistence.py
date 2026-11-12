"""Saves the judge's scores and feedback for model responses."""

from apps.evaluations.criteria import CRITERIA
from apps.evaluations.models import Evaluation, EvaluationCriterion, ResponseEvaluation


def save_scores(responses_by_model_id: dict, judge_result: dict) -> None:
    """Save one score per criterion, and the overall verdict, for each evaluated response.

    responses_by_model_id maps a model's API identifier to its saved ModelResponse.
    Criteria missing from the database are created, so scores are never dropped.
    """
    criteria = {
        name: EvaluationCriterion.objects.get_or_create(
            name=name, defaults={'description': description},
        )[0]
        for name, description in CRITERIA
    }

    for item in judge_result['evaluations']:
        response = responses_by_model_id[item['model_id']]
        for name, criterion in criteria.items():
            Evaluation.objects.create(response=response, criterion=criterion, score=item[name])
        ResponseEvaluation.objects.create(
            response=response,
            label=item['label'],
            overall_score=item['overall_score'],
            strengths=item['strengths'],
            weaknesses=item['weaknesses'],
        )
