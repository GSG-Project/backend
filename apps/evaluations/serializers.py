from rest_framework import serializers  # noqa: F401


class JudgeScoreSerializer(serializers.Serializer):
    label = serializers.CharField()
    accuracy = serializers.IntegerField(min_value=1, max_value=10)
    relevance = serializers.IntegerField(min_value=1, max_value=10)
    clarity = serializers.IntegerField(min_value=1, max_value=10)
    completeness = serializers.IntegerField(min_value=1, max_value=10)
    overall_score = serializers.FloatField(min_value=1, max_value=10)
    strengths = serializers.CharField()
    weaknesses = serializers.CharField()


class JudgeResponseSerializer(serializers.Serializer):
    winner = serializers.CharField()
    evaluations = JudgeScoreSerializer(many=True)
    reasoning = serializers.CharField()

    def validate(self, data):
        evaluations = data["evaluations"]
        labels = [item["label"] for item in evaluations]

        if len(labels) != len(set(labels)):
            raise serializers.ValidationError(
                "Each answer must have exactly one evaluation."
            )

        expected_labels = self.context.get("expected_labels")

        if expected_labels is not None and set(labels) != set(expected_labels):
            raise serializers.ValidationError(
                "The Judge must evaluate every answer exactly once."
            )

        if data["winner"] not in labels:
            raise serializers.ValidationError(
                "The winner must be one of the evaluated answers."
            )

        return data


class EvaluationScoreSerializer(serializers.Serializer):
    """The judge's evaluation of one model's answer, as returned by the API."""

    model_id = serializers.CharField(help_text="The model that produced the evaluated answer.")
    label = serializers.CharField(
        help_text="The anonymous label (A, B, ...) the judge saw instead of the model name.",
    )
    accuracy = serializers.IntegerField(min_value=1, max_value=10)
    relevance = serializers.IntegerField(min_value=1, max_value=10)
    clarity = serializers.IntegerField(min_value=1, max_value=10)
    completeness = serializers.IntegerField(min_value=1, max_value=10)
    overall_score = serializers.FloatField(min_value=1, max_value=10)
    strengths = serializers.CharField()
    weaknesses = serializers.CharField()


class EvaluationResultSerializer(serializers.Serializer):
    """The judge's evaluation of a comparison, as returned by the API."""

    winner = serializers.CharField(help_text="The label of the best answer.")
    winner_model_id = serializers.CharField(help_text="The model that produced the best answer.")
    reasoning = serializers.CharField(help_text="Why the judge picked the winner.")
    evaluations = EvaluationScoreSerializer(many=True)
    judge_model = serializers.CharField(help_text="The model that acted as the judge.")
    latency_ms = serializers.FloatField(allow_null=True)
    input_tokens = serializers.IntegerField(allow_null=True)
    output_tokens = serializers.IntegerField(allow_null=True)
    total_tokens = serializers.IntegerField(allow_null=True)
