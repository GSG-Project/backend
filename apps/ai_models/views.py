from rest_framework.decorators import api_view
from rest_framework.response import Response

from apps.ai_models.serializers import AIModelSerializer
from apps.ai_models.services.catalog import get_selectable_models


@api_view(["GET"])
def model_list(request):
    models = get_selectable_models()

    return Response({
        "models": AIModelSerializer(models, many=True).data
    })
