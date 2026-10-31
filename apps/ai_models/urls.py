from django.urls import path  # noqa: F401

app_name = 'ai_models'

urlpatterns = []

from apps.ai_models.views import model_list

urlpatterns = [
    path("", model_list, name="model-list"),
]