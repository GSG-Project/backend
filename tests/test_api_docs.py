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


PUBLIC_ENDPOINTS = [
    ('/api/health/', 'get'),
    ('/api/models/', 'get'),
    ('/api/comparisons/', 'post'),
    ('/api/auth/register/', 'post'),
    ('/api/auth/login/', 'post'),
    ('/api/auth/refresh/', 'post'),
    ('/api/auth/login/verify/', 'post'),
    ('/api/auth/login/resend/', 'post'),
    ('/api/auth/password-reset/', 'post'),
    ('/api/auth/password-reset/confirm/', 'post'),
]
SIGNED_IN_ENDPOINTS = [
    ('/api/auth/me/', 'get'),
    ('/api/auth/me/', 'patch'),
    ('/api/auth/change-password/', 'post'),
    ('/api/auth/two-factor/enable/', 'post'),
    ('/api/auth/two-factor/confirm/', 'post'),
    ('/api/auth/two-factor/disable/', 'post'),
    ('/api/experiments/', 'get'),
    ('/api/experiments/{id}/', 'get'),
    ('/api/experiments/{id}/', 'delete'),
    ('/api/experiments/{id}/rerun/', 'post'),
]
ALL_ENDPOINTS = PUBLIC_ENDPOINTS + SIGNED_IN_ENDPOINTS


@pytest.mark.parametrize('path, method', ALL_ENDPOINTS)
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


@pytest.mark.parametrize('path, method', PUBLIC_ENDPOINTS)
def test_endpoints_are_documented_as_public(schema, path, method):
    assert not operation(schema, path, method).get('security')


@pytest.mark.parametrize('path, method', SIGNED_IN_ENDPOINTS)
def test_signed_in_endpoints_document_the_bearer_token(schema, path, method):
    security = operation(schema, path, method).get('security')

    assert security and any('jwtAuth' in option for option in security)
    assert 'jwtAuth' in schema['components']['securitySchemes']


def test_the_experiment_list_documents_its_pagination(schema):
    op = operation(schema, '/api/experiments/', 'get')

    assert {'page', 'page_size'} <= {parameter['name'] for parameter in op['parameters']}
    assert 'results' in schema['components']['schemas']['PaginatedExperimentListList']['properties']


def test_the_experiment_detail_documents_not_found(schema):
    assert '404' in operation(schema, '/api/experiments/{id}/', 'get')['responses']


def test_delete_and_rerun_document_their_responses(schema):
    delete = operation(schema, '/api/experiments/{id}/', 'delete')['responses']
    rerun = operation(schema, '/api/experiments/{id}/rerun/', 'post')

    assert {'204', '401', '404'} <= set(delete)
    assert {'201', '400', '401', '404'} <= set(rerun['responses'])
    assert rerun['responses']['201']['content']['application/json']['schema']
    assert 'requestBody' not in rerun


def test_registration_documents_its_request_and_tokens(schema):
    op = operation(schema, '/api/auth/register/', 'post')

    assert 'application/json' in op['requestBody']['content']
    assert 'password' in schema['components']['schemas']['Register']['properties']
    response_schema = schema['components']['schemas']['RegisterResponse']
    assert {'access', 'refresh', 'user'} <= set(response_schema['properties'])


def test_changing_the_profile_and_password_document_their_requests(schema):
    patch = operation(schema, '/api/auth/me/', 'patch')
    password = operation(schema, '/api/auth/change-password/', 'post')

    assert 'application/json' in patch['requestBody']['content']
    assert 'first_name' in schema['components']['schemas']['PatchedUser']['properties']
    password_schema = schema['components']['schemas']['ChangePassword']
    assert {'old_password', 'new_password'} <= set(password_schema['properties'])
    assert '204' in password['responses'] and '400' in password['responses']
    assert 'put' not in schema['paths']['/api/auth/me/']


def test_a_saved_runs_evaluation_is_documented_like_the_comparison_response(schema):
    run = schema['components']['schemas']['RunDetail']['properties']
    evaluation = schema['components']['schemas']['JudgeEvaluation']['properties']
    live = schema['components']['schemas']['EvaluationResult']['properties']
    judged = schema['components']['schemas']['JudgedAnswer']['properties']

    assert 'evaluation' in run
    assert set(evaluation) == set(live)
    assert {'label', 'overall_score', 'strengths', 'weaknesses'} <= set(judged)


def test_health_documents_both_outcomes(schema):
    responses = operation(schema, '/api/health/', 'get')['responses']

    assert '200' in responses and '503' in responses
