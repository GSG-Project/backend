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
