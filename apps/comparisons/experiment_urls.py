from django.urls import path

from . import history_views

app_name = 'experiments'

urlpatterns = [
    path('', history_views.ExperimentListView.as_view(), name='list'),
    path('<int:pk>/', history_views.ExperimentDetailView.as_view(), name='detail'),
    path('<int:pk>/rerun/', history_views.ExperimentRerunView.as_view(), name='rerun'),
]
