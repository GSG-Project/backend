from django.urls import path

from apps.comparisons.views import create_comparison

app_name = 'comparisons'

urlpatterns = [
    path("", create_comparison, name="create-comparison"),
]
