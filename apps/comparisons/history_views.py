import logging

from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiExample, OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import status
from rest_framework.generics import ListAPIView, RetrieveDestroyAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.comparisons.history_serializers import ExperimentDetailSerializer, ExperimentListSerializer
from apps.comparisons.models import Experiment
from apps.comparisons.serializers import ComparisonResponseSerializer
from apps.comparisons.services import history
from apps.comparisons.services.comparison_service import ComparisonService
from apps.comparisons.views import SUCCESS_EXAMPLE

logger = logging.getLogger(__name__)

TAG = ['Experiments']
NOT_SIGNED_IN = OpenApiResponse(description='No valid access token was sent.')
NOT_FOUND = OpenApiResponse(description='The experiment does not exist or is not yours.')


class HistoryPagination(PageNumberPagination):
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 50


@extend_schema(
    tags=TAG,
    summary='List your experiments',
    description=(
        'The experiments the signed-in user has run, newest first, 20 per page '
        '(`?page=` and `?page_size=`, at most 50). Each one shows its models, how many times it has '
        'been run, and the latest run with its winner. Use the detail endpoint for the full results. '
        'Comparisons made without signing in are not listed. Requires `Authorization: Bearer <access>`.'
    ),
    responses={200: ExperimentListSerializer(many=True), 401: NOT_SIGNED_IN},
)
class ExperimentListView(ListAPIView):
    serializer_class = ExperimentListSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = HistoryPagination

    def get_queryset(self):
        return history.list_experiments(self.request.user)


@extend_schema_view(
    get=extend_schema(
        tags=TAG,
        summary='Get one of your experiments',
        description=(
            'One saved experiment with every run: each model\'s answer, metrics, error, and per-criterion '
            'scores, plus the judge\'s winner and reasoning. Returns `404` when the experiment does not '
            'exist or belongs to someone else. Requires `Authorization: Bearer <access>`.'
        ),
        responses={200: ExperimentDetailSerializer, 401: NOT_SIGNED_IN, 404: NOT_FOUND},
    ),
    delete=extend_schema(
        tags=TAG,
        summary='Delete one of your experiments',
        description=(
            'Permanently deletes the experiment with all its runs, answers, and scores. '
            'Only the owner can delete it: someone else\'s experiment returns `404`, as if it did not '
            'exist. Requires `Authorization: Bearer <access>`.'
        ),
        responses={
            204: OpenApiResponse(description='The experiment was deleted.'),
            401: NOT_SIGNED_IN,
            404: NOT_FOUND,
        },
    ),
)
class ExperimentDetailView(RetrieveDestroyAPIView):
    serializer_class = ExperimentDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        if self.request.method == 'DELETE':
            # Deleting needs no prefetching, only the ownership check.
            return Experiment.objects.filter(user=self.request.user)
        return history.experiment_detail_queryset(self.request.user)


@extend_schema(
    tags=TAG,
    summary='Rerun one of your experiments',
    description=(
        'Sends the experiment\'s prompt to the same models again and saves the outcome as a **new run '
        'of the same experiment**; no new experiment is created and earlier runs are kept. '
        'The response has the same shape as `POST /api/comparisons/`, with the new `run_id`. '
        'Failures are reported the same way: one model failing does not fail the request.\n\n'
        'Returns `400` when one of the models has been deactivated since, and `404` when the experiment '
        'does not exist or belongs to someone else. Requires `Authorization: Bearer <access>`.'
    ),
    request=None,
    responses={
        201: OpenApiResponse(
            response=ComparisonResponseSerializer,
            description='The experiment was run again and the new run was saved.',
        ),
        400: OpenApiResponse(description='A model of this experiment is no longer available.'),
        401: NOT_SIGNED_IN,
        404: NOT_FOUND,
    },
    examples=[
        OpenApiExample(
            'Rerun completed',
            value={**SUCCESS_EXAMPLE, 'run_id': 27},
            response_only=True,
            status_codes=['201'],
        ),
        OpenApiExample(
            'Model no longer available',
            value={'error': "Model 'gemini-3.6-flash' is no longer available."},
            response_only=True,
            status_codes=['400'],
        ),
    ],
)
class ExperimentRerunView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, pk):
        experiment = get_object_or_404(Experiment, pk=pk, user=request.user)

        try:
            result = ComparisonService().rerun(experiment)
        except ValueError as error:
            return Response({'error': str(error)}, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            logger.exception('Rerun of experiment %s failed unexpectedly.', experiment.pk)
            return Response(
                {'error': 'The comparison could not be completed.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        return Response(result, status=status.HTTP_201_CREATED)
