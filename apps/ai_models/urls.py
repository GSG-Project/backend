from django.urls import path

from apps.ai_models.views import model_list

app_name = 'ai_models'

urlpatterns = [
    path("", model_list, name="model-list"),
]
