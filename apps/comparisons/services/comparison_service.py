"""
Runs a comparison: sends the prompt to the selected models concurrently, saves each
response with its metrics, and asks the judge to evaluate the successful answers.
"""
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db import transaction

from apps.ai_models.models import AIModel
from apps.ai_models.services.catalog import get_judge_model, get_selectable_model
from apps.comparisons.models import Run
from apps.comparisons.services import persistence
from apps.evaluations.services.judge_service import JudgeService
from apps.evaluations.services.persistence import save_scores
from providers.exceptions import ProviderError
from providers.factory import get_provider


class ComparisonService:

    def __init__(self, judge_service=None, provider_factory=get_provider):
        # The judge is created on demand, so a missing judge key only fails
        # the evaluation instead of the whole comparison.
        self.judge_service = judge_service
        self.provider_factory = provider_factory

    def compare(self, prompt: str, model_ids: list[str], user=None) -> dict:
        if not prompt or not prompt.strip():
            raise ValueError("Prompt cannot be empty.")

        if not isinstance(model_ids, list) or len(model_ids) < 2:
            raise ValueError("At least two models must be selected.")

        if len(model_ids) != len(set(model_ids)):
            raise ValueError("Duplicate model IDs are not allowed.")

        # Validate selected models.
        models = []

        for model_id in model_ids:
            model = get_selectable_model(model_id)

            if model is None:
                raise ValueError(f"Model '{model_id}' is not available.")

            models.append(model)

        run, experiment_models = persistence.start_run(prompt, models, user=user)

        try:
            return self._run_comparison(run, experiment_models, models, prompt)
        except Exception:
            persistence.fail_run(run)
            raise

    def _run_comparison(self, run: Run, experiment_models: dict, models: list[AIModel], prompt: str) -> dict:
        results = self._generate_all(models, prompt)

        # Save every outcome, successful or not, in the order the models were selected.
        responses = []

        for model, result in zip(models, results):
            response = persistence.save_response(
                run, experiment_models[model.api_model_identifier], result
            )
            responses.append(response)

            result["metadata"] = self._with_cost(result["metadata"], model, response)

        responses_by_model_id = {
            model.api_model_identifier: response
            for model, response in zip(models, responses)
        }

        evaluation, evaluation_error, finish = self._evaluate(
            prompt, results, responses_by_model_id, experiment_models
        )

        with transaction.atomic():
            if evaluation is not None:
                save_scores(responses_by_model_id, evaluation)
            persistence.finish_run(run, responses, **finish)

        return {
            "experiment_id": run.experiment_id,
            "run_id": run.pk,
            "prompt": prompt,
            "results": results,
            "evaluation": evaluation,
            "evaluation_error": evaluation_error
        }

    def _generate_all(self, models: list[AIModel], prompt: str) -> list[dict]:
        results_by_id = {}

        # Run model requests concurrently. Worker threads only call the
        # providers; all database work stays in the calling thread.
        with ThreadPoolExecutor(max_workers=len(models)) as executor:

            futures = {
                executor.submit(
                    self._generate_answer,
                    model,
                    prompt
                ): model.api_model_identifier
                for model in models
            }

            for future in as_completed(futures):
                model_id = futures[future]

                try:
                    results_by_id[model_id] = future.result()

                except Exception as error:
                    results_by_id[model_id] = {
                        "model_id": model_id,
                        "answer": None,
                        "metadata": None,
                        "status": "failed",
                        "error": {
                            "code": "provider_error",
                            "message": "This model could not generate a response."
                        },
                        "error_detail": self._describe_error(error),
                    }

        # Preserve the original selection order.
        return [results_by_id[model.api_model_identifier] for model in models]

    def _evaluate(self, prompt, results, responses_by_model_id, experiment_models):
        """Ask the judge to compare the successful answers.

        Returns (evaluation, evaluation_error, finish_run arguments).
        """
        # Only successful answers can be evaluated.
        successful_answers = [
            {
                "model_id": result["model_id"],
                "text": result["answer"]
            }
            for result in results
            if result["status"] == "success"
        ]

        if len(successful_answers) < 2:
            error = (
                "At least two successful model responses are required "
                "for evaluation."
            )
            return None, error, {"evaluation_status": Run.EvaluationStatus.SKIPPED}

        judge_model = get_judge_model()

        try:
            judge = self.judge_service or JudgeService()
            evaluation = judge.evaluate(prompt, successful_answers)
        except ProviderError as error:
            return None, "The Judge could not evaluate the answers.", {
                "evaluation_status": Run.EvaluationStatus.FAILED,
                "evaluation_error": self._describe_error(error),
                "judge_model": judge_model,
            }

        return evaluation, None, {
            "evaluation_status": Run.EvaluationStatus.COMPLETED,
            "judge_model": judge_model,
            "winner": experiment_models[evaluation["winner_model_id"]],
            "judge_reasoning": evaluation["reasoning"],
        }

    def _generate_answer(self, model: AIModel, prompt: str) -> dict:
        provider = self.provider_factory(model.provider)

        response = provider.generate(
            model_id=model.api_model_identifier,
            prompt=prompt
        )

        return {
            "model_id": model.api_model_identifier,
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

    @staticmethod
    def _with_cost(metadata, model: AIModel, response) -> dict | None:
        if metadata is None:
            return None

        return {
            **metadata,
            "cost": float(response.cost) if response.cost is not None else None,
            "cost_currency": model.currency,
        }

    @staticmethod
    def _describe_error(error: Exception) -> str:
        # Provider errors carry messages written by our own code. Anything else
        # is reduced to its type so internal details are not stored.
        if isinstance(error, ProviderError):
            return f"{type(error).__name__}: {error}"
        return f"Unexpected {type(error).__name__}"
