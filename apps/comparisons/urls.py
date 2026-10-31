from django.urls import path  # noqa: F401

from apps.comparisons.views import create_comparison
app_name = 'comparisons'

urlpatterns = []


urlpatterns = [
    path("", create_comparison, name="create-comparison"),
]