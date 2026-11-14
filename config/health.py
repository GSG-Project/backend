from django.db import connection
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema
from rest_framework import serializers, status
from rest_framework.decorators import api_view, authentication_classes, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


class HealthSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=['ok', 'error'])
    database = serializers.ChoiceField(choices=['ok', 'unavailable'])


@extend_schema(
    tags=['Health'],
    auth=[],
    summary='Check that the service is running',
    description=(
        'Returns `200` when the service is up and can reach the database, and `503` when the '
        'database cannot be reached. It needs no token and returns nothing private, so it can be '
        'called by an uptime monitor or a cron job. Calling it every 10 minutes keeps a free '
        'Render service from going to sleep. `HEAD` works too.'
    ),
    responses={
        200: OpenApiResponse(HealthSerializer, description='The service and its database are up.'),
        503: OpenApiResponse(HealthSerializer, description='The service is up but the database is not.'),
    },
    examples=[
        OpenApiExample(
            'Healthy', value={'status': 'ok', 'database': 'ok'},
            response_only=True, status_codes=['200'],
        ),
        OpenApiExample(
            'Database down', value={'status': 'error', 'database': 'unavailable'},
            response_only=True, status_codes=['503'],
        ),
    ],
)
@api_view(['GET', 'HEAD'])
@authentication_classes([])
@permission_classes([AllowAny])
def health(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
    except Exception:
        body = {'status': 'error', 'database': 'unavailable'}
        return Response(body, status=status.HTTP_503_SERVICE_UNAVAILABLE)
    return Response({'status': 'ok', 'database': 'ok'})
