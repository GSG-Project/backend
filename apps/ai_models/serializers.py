from rest_framework import serializers

from apps.ai_models.models import AIModel


class AIModelSerializer(serializers.ModelSerializer):
    # The public id is the provider's model identifier, which clients send back
    # in comparison requests.
    id = serializers.CharField(source='api_model_identifier')

    class Meta:
        model = AIModel
        fields = ['id', 'name', 'provider', 'is_active']


class AIModelListSerializer(serializers.Serializer):
    models = AIModelSerializer(many=True)
