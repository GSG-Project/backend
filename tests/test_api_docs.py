"""The Swagger documentation must stay complete and accurate."""

import pytest
import yaml
from django.core.management import call_command

from apps.comparisons import views as comparison_views
from apps.comparisons.serializers import ComparisonResponseSerializer


@pytest.fixture(scope='module')
def schema(tmp_path_factory):
    path = tmp_path_factory.mktemp('schema') / 'schema.yml'
    # --fail-on-warn also fails on schema errors, such as a view with no serializer.
    call_command('spectacular', '--validate', '--fail-on-warn', '--file', str(path))
    return yaml.safe_load(path.read_text())


def operation(schema, path, method):
    return schema['paths'][path][method]


@pytest.mark.parametrize('path, method', [('/api/models/', 'get'), ('/api/comparisons/', 'post')])
def test_every_endpoint_is_described(schema, path, method):
    op = operation(schema, path, method)

    assert op.get('summary')
    assert op.get('description')
    assert op.get('tags')


def test_comparison_request_documents_its_fields_as_json(schema):
    op = operation(schema, '/api/comparisons/', 'post')
    content = op['requestBody']['content']

    assert list(content) == ['application/json']
    request = schema['components']['schemas']['ComparisonRequest']
    assert set(request['properties']) == {'prompt', 'model_ids'}
    assert set(request['required']) == {'prompt', 'model_ids'}


def test_responses_have_schemas_and_errors_are_documented(schema):
    comparison = operation(schema, '/api/comparisons/', 'post')['responses']
    models = operation(schema, '/api/models/', 'get')['responses']

    assert comparison['200']['content']['application/json']['schema']
    assert '400' in comparison
    assert models['200']['content']['application/json']['schema']


def test_response_documents_unavailable_values_as_nullable(schema):
    metadata = schema['components']['schemas']['ResultMetadata']['properties']

    for field in ('input_tokens', 'output_tokens', 'cost'):
        assert metadata[field].get('nullable') is True


@pytest.mark.parametrize('name', ['SUCCESS_EXAMPLE', 'PARTIAL_FAILURE_EXAMPLE'])
def test_documented_examples_match_the_response_schema(name):
    serializer = ComparisonResponseSerializer(data=getattr(comparison_views, name))

    assert serializer.is_valid(), serializer.errors


@pytest.mark.parametrize('path, method', [('/api/models/', 'get'), ('/api/comparisons/', 'post')])
def test_endpoints_are_documented_as_public(schema, path, method):
    # Update this when authentication is added and the endpoints require login.
    assert not operation(schema, path, method).get('security')
