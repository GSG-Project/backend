from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.comparisons.serializers import ComparisonRequestSerializer, ComparisonResponseSerializer
from apps.comparisons.services.comparison_service import ComparisonService

RESULT_A = {
    "model_id": "gemini-3.8-flash",
    "answer": "A REST API lets programs talk to each other over HTTP...",
    "metadata": {
        "latency_ms": 1200.4,
        "input_tokens": 15,
        "output_tokens": 80,
        "total_tokens": 95,
        "cost": 0.000212,
        "cost_currency": "USD",
    },
    "status": "success",
    "error": None,
}

RESULT_B = {
    "model_id": "gemini-3.6-flash",
    "answer": "REST is a way to build web services using standard HTTP methods...",
    "metadata": {
        "latency_ms": 1800.9,
        "input_tokens": 15,
        "output_tokens": 95,
        "total_tokens": 110,
        "cost": None,
        "cost_currency": "USD",
    },
    "status": "success",
    "error": None,
}

RESULT_FAILED = {
    "model_id": "gemini-3.6-flash",
    "answer": None,
    "metadata": None,
    "status": "failed",
    "error": {"code": "provider_error", "message": "This model could not generate a response."},
}

EVALUATION = {
    "winner": "A",
    "winner_model_id": "gemini-3.8-flash",
    "reasoning": "Answer A is clearer and covers the main points.",
    "evaluations": [
        {
            "model_id": "gemini-3.8-flash",
            "label": "A",
            "accuracy": 9,
            "relevance": 9,
            "clarity": 8,
            "completeness": 8,
            "overall_score": 8.5,
            "strengths": "Clear and well structured.",
            "weaknesses": "Could include an example.",
        },
        {
            "model_id": "gemini-3.6-flash",
            "label": "B",
            "accuracy": 8,
            "relevance": 8,
            "clarity": 7,
            "completeness": 7,
            "overall_score": 7.5,
            "strengths": "Accurate.",
            "weaknesses": "Wordy.",
        },
    ],
    "judge_model": "openai/gpt-oss-120b",
    "latency_ms": 900.2,
    "input_tokens": 600,
    "output_tokens": 220,
    "total_tokens": 820,
}

SUCCESS_EXAMPLE = {
    "experiment_id": 12,
    "run_id": 12,
    "prompt": "Explain REST APIs in simple terms.",
    "results": [RESULT_A, RESULT_B],
    "evaluation": EVALUATION,
    "evaluation_error": None,
}

PARTIAL_FAILURE_EXAMPLE = {
    "experiment_id": 13,
    "run_id": 13,
    "prompt": "Explain REST APIs in simple terms.",
    "results": [RESULT_A, RESULT_FAILED],
    "evaluation": None,
    "evaluation_error": "At least two successful model responses are required for evaluation.",
}


@extend_schema(
    tags=["Comparisons"],
    auth=[],  # open to anonymous users; a token is optional
    summary="Compare models on one prompt",
    description=(
        "Sends the same prompt to every selected model at the same time, saves the comparison, "
        "and asks a judge model to score the answers with the same rubric "
        "(accuracy, relevance, clarity, completeness).\n\n"
        "**Failures do not fail the request.** If one model fails, its entry has `status: failed` "
        "and the other answers are returned. The judge needs at least two successful answers; "
        "otherwise `evaluation` is `null` and `evaluation_error` says why.\n\n"
        "**Unavailable values are `null`, never 0:** tokens the provider did not report, and a cost "
        "that cannot be calculated because a token count or the model's price is unknown.\n\n"
        "A request that fails validation returns `400` and saves nothing. Get valid `model_ids` "
        "from `GET /api/models/`."
    ),
    request={"application/json": ComparisonRequestSerializer},
    responses={
        200: OpenApiResponse(
            response=ComparisonResponseSerializer,
            description="The comparison was run and saved, even if some models failed.",
        ),
        400: OpenApiResponse(
            description=(
                "The request is invalid. Field problems are keyed by field name; "
                "other problems use an `error` message."
            ),
        ),
    },
    examples=[
        OpenApiExample(
            "Request",
            value={
                "prompt": "Explain REST APIs in simple terms.",
                "model_ids": ["gemini-3.8-flash", "gemini-3.6-flash"],
            },
            request_only=True,
        ),
        OpenApiExample(
            "Both models answered and were judged",
            value=SUCCESS_EXAMPLE,
            response_only=True,
            status_codes=["200"],
        ),
        OpenApiExample(
            "One model failed",
            value=PARTIAL_FAILURE_EXAMPLE,
            response_only=True,
            status_codes=["200"],
        ),
        OpenApiExample(
            "Invalid field",
            value={"model_ids": ["Model 'unknown' is not available."]},
            response_only=True,
            status_codes=["400"],
        ),
        OpenApiExample(
            "Invalid request",
            value={"error": "Duplicate model IDs are not allowed."},
            response_only=True,
            status_codes=["400"],
        ),
    ],
)
@api_view(["POST"])
def create_comparison(request):
    serializer = ComparisonRequestSerializer(data=request.data)

    if not serializer.is_valid():
        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )

    prompt = serializer.validated_data["prompt"]
    model_ids = serializer.validated_data["model_ids"]

    try:
        service = ComparisonService()
        # Anonymous users are saved without an owner.
        user = request.user if request.user.is_authenticated else None
        result = service.compare(prompt, model_ids, user=user)

        return Response(result, status=status.HTTP_200_OK)

    except ValueError as error:
        return Response(
            {"error": str(error)},
            status=status.HTTP_400_BAD_REQUEST
        )