"""Runs a comparison: sends the prompt to the selected models concurrently, collects metrics, and requests the judge evaluation."""
from concurrent.futures import ThreadPoolExecutor, as_completed

from apps.ai_models.services.registry import get_model_by_id
from apps.evaluations.services.judge_service import JudgeService
from providers.gemini import GeminiProvider
from providers.exceptions import ProviderError


class ComparisonService:

    def __init__(self):
        self.judge_service = JudgeService()

    def compare(self, prompt: str, model_ids: list[str]) -> dict:
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        if not isinstance(model_ids, list) or len(model_ids) < 2:
            raise ValueError("At least two models must be selected.")

        if len(model_ids) != len(set(model_ids)):
            raise ValueError("Duplicate model IDs are not allowed.")

        # Validate selected models.
        models = []

        for model_id in model_ids:
            model = get_model_by_id(model_id)

            if model is None:
                raise ValueError(f"Model '{model_id}' is not available.")

            models.append(model)

        results = []

        # Run model requests concurrently.
        with ThreadPoolExecutor(max_workers=len(models)) as executor:

            futures = {
                executor.submit(
                    self._generate_answer,
                    model["id"],
                    prompt
                ): model["id"]
                for model in models
            }

            for future in as_completed(futures):
                model_id = futures[future]

                try:
                    result = future.result()
                    results.append(result)

                except Exception:
                    results.append({
                        "model_id": model_id,
                        "answer": None,
                        "metadata": None,
                        "status": "failed",
                        "error": {
                            "code": "provider_error",
                            "message": "This model could not generate a response."
                        }
                    })

        # Preserve the original selection order.
        results_by_id = {
            result["model_id"]: result
            for result in results
        }

        results = [
            results_by_id[model_id]
            for model_id in model_ids
        ]

        # Only successful answers can be evaluated.
        successful_answers = [
            {
                "model_id": result["model_id"],
                "text": result["answer"]
            }
            for result in results
            if result["status"] == "success"
        ]

        evaluation = None
        evaluation_error = None

        if len(successful_answers) >= 2:
            try:
                evaluation = self.judge_service.evaluate(
                    prompt,
                    successful_answers
                )
            except ProviderError:
                evaluation_error = "The Judge could not evaluate the answers."

        else:
            evaluation_error = (
                "At least two successful model responses are required "
                "for evaluation."
            )

        return {
            "prompt": prompt,
            "results": results,
            "evaluation": evaluation,
            "evaluation_error": evaluation_error
        }

    def _generate_answer(self, model_id: str, prompt: str) -> dict:
        provider = GeminiProvider()

        response = provider.generate(
            model_id=model_id,
            prompt=prompt
        )

        return {
            "model_id": model_id,
            "answer": response["text"],
            "metadata": {
                "latency_ms": response["latency_ms"],
                "input_tokens": response["input_tokens"],
                "output_tokens": response["output_tokens"],
                "total_tokens": response["total_tokens"]
            },
            "status": "success",
            "error": None
        }