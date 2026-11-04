from drf_spectacular.utils import OpenApiExample, extend_schema
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.ai_models.serializers import AIModelListSerializer
from apps.ai_models.services.catalog import get_selectable_models


@extend_schema(
    tags=["Models"],
    auth=[],  # public for now; change when authentication is added
    summary="List the models you can compare",
    description=(
        "Returns the active models available for comparison. Judge models are not included.\n\n"
        "The `id` is what you send in `model_ids` when creating a comparison."
    ),
    responses={200: AIModelListSerializer},
    examples=[
        OpenApiExample(
            "Available models",
            value={
                "models": [
                    {
                        "id": "gemini-3.8-flash",
                        "name": "Gemini 3.8 Flash",
                        "provider": "gemini",
                        "is_active": True,
                    },
                    {
                        "id": "gemini-3.6-flash",
                        "name": "Gemini 3.6 Flash",
                        "provider": "gemini",
                        "is_active": True,
                    },
                ]
            },
            response_only=True,
        )
    ],
)
@api_view(["GET"])
def model_list(request):
    models = get_selectable_models()

    return Response(AIModelListSerializer({"models": models}).data)
