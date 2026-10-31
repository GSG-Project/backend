from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status

from apps.comparisons.serializers import ComparisonRequestSerializer
from apps.comparisons.services.comparison_service import ComparisonService


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
        result = service.compare(prompt, model_ids)

        return Response(result, status=status.HTTP_200_OK)

    except ValueError as error:
        return Response(
            {"error": str(error)},
            status=status.HTTP_400_BAD_REQUEST
        )