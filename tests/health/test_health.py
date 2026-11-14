import pytest
from django.db.utils import OperationalError
from rest_framework.test import APIClient

URL = '/api/health/'


@pytest.mark.django_db
def test_health_reports_ok_without_a_token():
    response = APIClient().get(URL)

    assert response.status_code == 200
    assert response.json() == {'status': 'ok', 'database': 'ok'}


@pytest.mark.django_db
def test_health_ignores_an_invalid_token():
    response = APIClient().get(URL, HTTP_AUTHORIZATION='Bearer not-a-token')

    assert response.status_code == 200


@pytest.mark.django_db
def test_health_works_with_head_for_uptime_monitors():
    assert APIClient().head(URL).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize('method', ['post', 'put', 'patch', 'delete'])
def test_health_only_allows_reading(method):
    assert getattr(APIClient(), method)(URL).status_code == 405


@pytest.mark.django_db
def test_health_reports_503_when_the_database_is_down(monkeypatch):
    def broken_cursor(*args, **kwargs):
        raise OperationalError('database is down')

    monkeypatch.setattr('config.health.connection.cursor', broken_cursor)

    response = APIClient().get(URL)

    assert response.status_code == 503
    assert response.json() == {'status': 'error', 'database': 'unavailable'}
    assert 'down' not in response.content.decode()  # no internal details are leaked
