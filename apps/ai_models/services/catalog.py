"""Reads the AI model catalog from the database."""

from django.conf import settings

from apps.ai_models.models import AIModel


def get_selectable_models():
    """Models users can compare: active and not a judge."""
    return AIModel.objects.filter(is_active=True, is_judge=False)


def get_selectable_model(identifier: str) -> AIModel | None:
    return get_selectable_models().filter(api_model_identifier=identifier).first()


def get_judge_model() -> AIModel:
    """The catalog row for the configured judge, created if the seed was not run."""
    judge, _ = AIModel.objects.get_or_create(
        api_model_identifier=settings.JUDGE_MODEL,
        defaults={
            'name': settings.JUDGE_MODEL,
            'provider': AIModel.Provider.GROQ,
            'is_judge': True,
        },
    )
    return judge
