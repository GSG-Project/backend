from django.shortcuts import render

# Create your views here.
from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.ai_models.services.registry import get_available_models


@api_view(["GET"])
def model_list(request):
    models = get_available_models()

    return Response({
        "models": models
    })