from rest_framework import serializers  # noqa: F401

from apps.ai_models.services.catalog import get_selectable_model


class ComparisonRequestSerializer(serializers.Serializer):
    prompt = serializers.CharField(
        required=True,
        allow_blank=False,
        trim_whitespace=True
    )

    model_ids = serializers.ListField(
        child=serializers.CharField(),
        required=True,
        min_length=2
    )

    def validate_model_ids(self, model_ids):
        # Make sure the same model isn't selected twice.
        if len(model_ids) != len(set(model_ids)):
            raise serializers.ValidationError(
                "You cannot select the same model more than once."
            )

        # Make sure every selected model exists and is active.
        for model_id in model_ids:
            if get_selectable_model(model_id) is None:
                raise serializers.ValidationError(
                    f"Model '{model_id}' is not available."
                )

        return model_ids