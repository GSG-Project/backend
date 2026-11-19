"""
Sends model responses to the judge model using a predefined rubric and validates
its structured JSON evaluation. Model identities are hidden and response order is
varied to reduce judge bias.
"""


import json

from django.conf import settings

from providers.groq import GroqProvider
from providers.exceptions import ProviderError
from apps.evaluations.serializers import JudgeResponseSerializer


JUDGE_ATTEMPTS = 2


class JudgeService:

    def __init__(self):
        self.provider = GroqProvider()

    def evaluate(self, prompt: str, answers: list[dict]) -> dict:
        """
        Evaluate multiple model answers using Groq.

        Each answer must contain:
        {
            "model_id": "...",
            "text": "..."
        }
        """

        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        if not isinstance(answers, list) or len(answers) < 2:
            raise ValueError("At least two answers are required.")

        if any(
            not isinstance(answer, dict)
            or not answer.get("model_id")
            or not isinstance(answer.get("text"), str)
            or not answer["text"].strip()
            for answer in answers
        ):
            raise ValueError("Every answer must have a model_id and non-empty text.")

        model_ids = [answer["model_id"] for answer in answers]

        if len(model_ids) != len(set(model_ids)):
            raise ValueError("Duplicate model IDs are not allowed.")

        # Give answers anonymous labels to reduce evaluation bias.
        labels = [
            chr(ord("A") + index)
            for index in range(len(answers))
        ]

        label_to_model = {
            label: answer["model_id"]
            for label, answer in zip(labels, answers)
        }

        anonymous_answers = [
            {
                "label": label,
                "answer": answer["text"]
            }
            for label, answer in zip(labels, answers)
        ]

        judge_prompt = f"""
You are an impartial evaluator comparing AI-generated answers.

Original user prompt:
{prompt}

Answers to evaluate:
{json.dumps(anonymous_answers, ensure_ascii=False)}

Evaluate every answer using these criteria:
1. Accuracy: Is the information correct?
2. Relevance: Does it answer the user's prompt?
3. Clarity: Is it clear and understandable?
4. Completeness: Does it cover the important points?

Give each criterion a score from 1 to 10.
Calculate an overall_score from 1 to 10 for each answer.

Choose the answer that performs best overall.
Do not assume that a longer answer is better.
Do not favor an answer simply because it sounds confident.

Return ONLY valid JSON with this exact structure:
{{
    "winner": "A",
    "evaluations": [
        {{
            "label": "A",
            "accuracy": 8,
            "relevance": 9,
            "clarity": 8,
            "completeness": 8,
            "overall_score": 8.25,
            "strengths": "Explanation of strengths",
            "weaknesses": "Explanation of weaknesses"
        }}
    ],
    "reasoning": "Explain why the winning answer was selected."
}}

Include exactly one evaluation for every supplied label.
The winner must be one of the supplied labels.
Scores must be between 1 and 10.
The four criterion scores must be whole numbers; only overall_score may have decimals.
"""

        # A judge sometimes answers with malformed JSON or breaks the format.
        # One more try usually fixes it and saves the comparison.
        for attempt in range(JUDGE_ATTEMPTS):
            result = self.provider.generate(
                model_id=settings.JUDGE_MODEL,
                prompt=judge_prompt
            )

            try:
                serializer = self._parse(result["text"], labels)
                break
            except ProviderError:
                if attempt == JUDGE_ATTEMPTS - 1:
                    raise

        validated = serializer.validated_data

        # Map anonymous labels back to the actual model IDs.
        validated["winner_model_id"] = label_to_model[
            validated["winner"]
        ]

        for evaluation in validated["evaluations"]:
            evaluation["model_id"] = label_to_model[
                evaluation["label"]
            ]

        return {
            **validated,
            "judge_model": settings.JUDGE_MODEL,
            "latency_ms": result["latency_ms"],
            "input_tokens": result["input_tokens"],
            "output_tokens": result["output_tokens"],
            "total_tokens": result["total_tokens"],
        }

    @staticmethod
    def _parse(text, labels):
        try:
            judge_data = json.loads(text)
        except (json.JSONDecodeError, TypeError) as error:
            raise ProviderError("Judge returned invalid JSON.") from error

        serializer = JudgeResponseSerializer(
            data=judge_data,
            context={"expected_labels": labels}
        )

        if not serializer.is_valid():
            raise ProviderError(
                f"Judge response failed validation: {serializer.errors}"
            )

        return serializer
