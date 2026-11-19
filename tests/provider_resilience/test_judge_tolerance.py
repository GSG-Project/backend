"""The judge's answer is accepted when it uses decimals, and asked again when it is unusable."""
import json

import pytest

from apps.evaluations.services.judge_service import JudgeService
from providers.exceptions import ProviderError


def judgement(**scores):
    base = {'accuracy': 8, 'relevance': 9, 'clarity': 8, 'completeness': 8, 'overall_score': 8.25}
    base.update(scores)
    return {
        'winner': 'A',
        'evaluations': [
            {'label': 'A', 'strengths': 's', 'weaknesses': 'w', **base},
            {'label': 'B', 'strengths': 's', 'weaknesses': 'w', **base},
        ],
        'reasoning': 'because',
    }


class ScriptedJudgeProvider:
    def __init__(self, texts):
        self.texts = list(texts)
        self.calls = 0

    def generate(self, model_id, prompt):
        self.calls += 1
        return {
            'text': self.texts.pop(0), 'latency_ms': 1,
            'input_tokens': 1, 'output_tokens': 1, 'total_tokens': 2,
        }


def make_judge(texts):
    judge = JudgeService.__new__(JudgeService)
    judge.provider = ScriptedJudgeProvider(texts)
    return judge


ANSWERS = [{'model_id': 'm1', 'text': 'one'}, {'model_id': 'm2', 'text': 'two'}]


def test_decimal_criterion_scores_are_rounded():
    judge = make_judge([json.dumps(judgement(clarity=8.5, accuracy='7.4'))])

    result = judge.evaluate('prompt', ANSWERS)

    scores = result['evaluations'][0]
    assert scores['clarity'] == 9
    assert scores['accuracy'] == 7
    assert judge.provider.calls == 1


def test_out_of_range_score_is_still_rejected():
    judge = make_judge([json.dumps(judgement(clarity=11))] * 2)

    with pytest.raises(ProviderError):
        judge.evaluate('prompt', ANSWERS)


def test_unusable_answer_is_retried_once():
    judge = make_judge(['not json', json.dumps(judgement())])

    result = judge.evaluate('prompt', ANSWERS)

    assert result['winner_model_id'] == 'm1'
    assert judge.provider.calls == 2


def test_gives_up_after_the_second_unusable_answer():
    judge = make_judge(['not json', 'still not json'])

    with pytest.raises(ProviderError, match='invalid JSON'):
        judge.evaluate('prompt', ANSWERS)

    assert judge.provider.calls == 2
