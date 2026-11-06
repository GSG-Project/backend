from drf_spectacular.utils import OpenApiResponse, extend_schema
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination
from rest_framework.permissions import IsAuthenticated

from apps.comparisons.history_serializers import ExperimentDetailSerializer, ExperimentListSerializer
from apps.comparisons.services import history

TAG = ['Experiments']
NOT_SIGNED_IN = OpenApiResponse(description='No valid access token was sent.')


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


@extend_schema(
    tags=TAG,
    summary='Get one of your experiments',
    description=(
        'One saved experiment with every run: each model\'s answer, metrics, error, and per-criterion '
        'scores, plus the judge\'s winner and reasoning. Returns `404` when the experiment does not exist '
        'or belongs to someone else. Requires `Authorization: Bearer <access>`.'
    ),
    responses={
        200: ExperimentDetailSerializer,
        401: NOT_SIGNED_IN,
        404: OpenApiResponse(description='The experiment does not exist or is not yours.'),
    },
)
class ExperimentDetailView(RetrieveAPIView):
    serializer_class = ExperimentDetailSerializer
    permission_classes = [IsAuthenticated]

    def get_queryset(self):
        return history.experiment_detail_queryset(self.request.user)
