"""Test doubles for the AI providers and the judge. Nothing here calls a real API."""

from providers.exceptions import ProviderError


class FakeProvider:
    """Answers per model id. A behavior is a dict of response fields or an exception to raise."""

    def __init__(self, behaviors=None):
        self.behaviors = behaviors or {}
        self.requested_providers = []

    def factory(self, provider_name):
        self.requested_providers.append(provider_name)
        return self

    def generate(self, model_id, prompt):
        behavior = self.behaviors.get(model_id, {})
        if isinstance(behavior, Exception):
            raise behavior
        return {
            'model_id': model_id,
            'text': f'answer from {model_id}',
            'latency_ms': 120.4,
            'input_tokens': 10,
            'output_tokens': 20,
            'total_tokens': 30,
            **behavior,
        }


class FakeJudge:
    """Returns a valid judge result in which the first answer wins, or raises the given error."""

    def __init__(self, error=None):
        self.error = error

    def evaluate(self, prompt, answers):
        if self.error:
            raise self.error
        return {
            'winner': 'A',
            'winner_model_id': answers[0]['model_id'],
            'reasoning': 'A is clearer.',
            'evaluations': [
                {
                    'label': chr(ord('A') + index),
                    'model_id': answer['model_id'],
                    'accuracy': 8 - index,
                    'relevance': 9 - index,
                    'clarity': 7,
                    'completeness': 6,
                    'overall_score': 7.5,
                    'strengths': 'Clear.',
                    'weaknesses': 'Short.',
                }
                for index, answer in enumerate(answers)
            ],
            'judge_model': 'judge-model',
            'latency_ms': 850.0,
            'input_tokens': 500,
            'output_tokens': 200,
            'total_tokens': 700,
        }


def provider_error(message='boom'):
    return ProviderError(message)
