from rest_framework import serializers

from apps.ai_models.services.catalog import get_selectable_model
from apps.comparisons.models import ModelResponse
from apps.evaluations.serializers import EvaluationResultSerializer


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


class ResultMetadataSerializer(serializers.Serializer):
    latency_ms = serializers.FloatField(help_text="Response time measured by the backend, in milliseconds.")
    input_tokens = serializers.IntegerField(
        allow_null=True, help_text="Reported by the provider. null when unavailable, never 0.",
    )
    output_tokens = serializers.IntegerField(
        allow_null=True, help_text="Reported by the provider. null when unavailable, never 0.",
    )
    total_tokens = serializers.IntegerField(allow_null=True)
    cost = serializers.FloatField(
        allow_null=True,
        help_text="Estimated cost, calculated from the token counts and the model's price. "
                  "null when the tokens or the price are unknown, never 0.",
    )
    cost_currency = serializers.CharField(help_text="Currency of `cost`, for example USD.")


class ResultErrorSerializer(serializers.Serializer):
    code = serializers.CharField(help_text="For now always `provider_error`.")
    message = serializers.CharField()


class ModelResultSerializer(serializers.Serializer):
    model_id = serializers.CharField()
    answer = serializers.CharField(allow_null=True, help_text="null when the model failed.")
    metadata = ResultMetadataSerializer(allow_null=True, help_text="null when the model failed.")
    status = serializers.ChoiceField(choices=ModelResponse.Status.choices)
    error = ResultErrorSerializer(allow_null=True, help_text="null when the model succeeded.")


class ComparisonResponseSerializer(serializers.Serializer):
    experiment_id = serializers.IntegerField(help_text="The saved experiment.")
    run_id = serializers.IntegerField(help_text="The saved run of that experiment.")
    prompt = serializers.CharField()
    results = ModelResultSerializer(
        many=True, help_text="One entry per selected model, in the order they were selected.",
    )
    evaluation = EvaluationResultSerializer(
        allow_null=True,
        help_text="The judge's evaluation. null when it could not run; see `evaluation_error`.",
    )
    evaluation_error = serializers.CharField(
        allow_null=True, help_text="Why `evaluation` is null. null when the evaluation succeeded.",
    )
