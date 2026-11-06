"""The read side of the API: a user's saved experiments."""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from apps.ai_models.serializers import AIModelSerializer
from apps.comparisons.models import ModelResponse, Run
from apps.comparisons.serializers import ResultErrorSerializer, ResultMetadataSerializer
from apps.evaluations.models import Evaluation

from .models import Experiment

ERROR_CODE = 'provider_error'


class RunSummarySerializer(serializers.ModelSerializer):
    winner_model_id = serializers.CharField(
        source='winner.ai_model.api_model_identifier', allow_null=True, default=None,
        help_text='The model the judge picked. null when there is no winner.',
    )

    class Meta:
        model = Run
        fields = ['id', 'status', 'evaluation_status', 'winner_model_id', 'started_at']


class ExperimentListSerializer(serializers.ModelSerializer):
    models = AIModelSerializer(source='ai_models', many=True)
    run_count = serializers.IntegerField(help_text='How many times this experiment has been run.')
    latest_run = serializers.SerializerMethodField(help_text='The most recent run, with its winner.')

    class Meta:
        model = Experiment
        fields = ['id', 'prompt', 'created_at', 'models', 'run_count', 'latest_run']

    @extend_schema_field(RunSummarySerializer(allow_null=True))
    def get_latest_run(self, experiment):
        # The runs are prefetched newest first, so this costs no extra query.
        runs = list(experiment.runs.all())
        return RunSummarySerializer(runs[0]).data if runs else None


class ScoreSerializer(serializers.ModelSerializer):
    criterion = serializers.CharField(source='criterion.name')

    class Meta:
        model = Evaluation
        fields = ['criterion', 'score', 'feedback']


class RunResultSerializer(serializers.ModelSerializer):
    """One model's saved outcome in one run. Same shape as a comparison result, plus its scores."""

    model_id = serializers.CharField(source='experiment_model.ai_model.api_model_identifier')
    answer = serializers.CharField(
        source='response_text', allow_null=True, help_text='null when the model failed.',
    )
    metadata = serializers.SerializerMethodField()
    error = serializers.SerializerMethodField()
    scores = ScoreSerializer(
        source='evaluations', many=True,
        help_text="The judge's score per criterion. Empty when not evaluated.",
    )

    class Meta:
        model = ModelResponse
        fields = ['model_id', 'answer', 'metadata', 'status', 'error', 'scores']

    @extend_schema_field(ResultMetadataSerializer(allow_null=True))
    def get_metadata(self, response):
        if response.status != ModelResponse.Status.SUCCESS:
            return None
        tokens = (response.input_tokens, response.output_tokens)
        return {
            'latency_ms': response.latency_ms,
            'input_tokens': response.input_tokens,
            'output_tokens': response.output_tokens,
            'total_tokens': None if None in tokens else sum(tokens),
            'cost': None if response.cost is None else float(response.cost),
            'cost_currency': response.experiment_model.ai_model.currency,
        }

    @extend_schema_field(ResultErrorSerializer(allow_null=True))
    def get_error(self, response):
        if response.status == ModelResponse.Status.SUCCESS:
            return None
        return {'code': ERROR_CODE, 'message': response.error_message}


class RunDetailSerializer(RunSummarySerializer):
    completed_at = serializers.DateTimeField(allow_null=True)
    evaluation_error = serializers.CharField(
        help_text='Why the evaluation did not complete. Empty when it did.',
    )
    judge_reasoning = serializers.CharField(help_text="The judge's explanation. Empty without an evaluation.")
    results = RunResultSerializer(source='responses', many=True)

    class Meta(RunSummarySerializer.Meta):
        fields = RunSummarySerializer.Meta.fields + [
            'completed_at', 'evaluation_error', 'judge_reasoning', 'results',
        ]


class ExperimentDetailSerializer(serializers.ModelSerializer):
    models = AIModelSerializer(source='ai_models', many=True)
    runs = RunDetailSerializer(many=True, help_text='Every run of this experiment, newest first.')

    class Meta:
        model = Experiment
        fields = ['id', 'prompt', 'created_at', 'models', 'runs']
