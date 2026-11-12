import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()
URL = '/api/auth/change-password/'
OLD = 'a-long-passphrase-42'
NEW = 'a-newer-passphrase-77'


@pytest.fixture
def sara(db):
    return User.objects.create_user(email='sara@example.com', first_name='Sara', password=OLD)


def client_for(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def test_the_password_is_changed(sara):
    response = client_for(sara).post(URL, {'old_password': OLD, 'new_password': NEW}, format='json')

    assert response.status_code == 204
    sara.refresh_from_db()
    assert sara.check_password(NEW) and not sara.check_password(OLD)


def test_the_new_password_works_for_login_and_the_old_one_does_not(sara):
    client_for(sara).post(URL, {'old_password': OLD, 'new_password': NEW}, format='json')
    def login(password):
        credentials = {'email': 'sara@example.com', 'password': password}
        return client_for().post('/api/auth/login/', credentials, format='json')

    assert login(NEW).status_code == 200
    assert login(OLD).status_code == 401


def test_a_wrong_current_password_changes_nothing(sara):
    data = {'old_password': 'not-my-password-1', 'new_password': NEW}
    response = client_for(sara).post(URL, data, format='json')

    assert response.status_code == 400 and 'old_password' in response.json()
    sara.refresh_from_db()
    assert sara.check_password(OLD)


@pytest.mark.parametrize('new_password', ['short1', 'password123', '1234567890', 'sara@example.com'])
def test_a_weak_new_password_is_rejected(sara, new_password):
    response = client_for(sara).post(URL, {'old_password': OLD, 'new_password': new_password}, format='json')

    assert response.status_code == 400 and 'new_password' in response.json()
    sara.refresh_from_db()
    assert sara.check_password(OLD)


def test_the_new_password_must_differ_from_the_old_one(sara):
    response = client_for(sara).post(URL, {'old_password': OLD, 'new_password': OLD}, format='json')

    assert response.status_code == 400 and 'new_password' in response.json()


@pytest.mark.parametrize('missing', ['old_password', 'new_password'])
def test_both_fields_are_required(sara, missing):
    data = {'old_password': OLD, 'new_password': NEW}
    del data[missing]

    response = client_for(sara).post(URL, data, format='json')

    assert response.status_code == 400 and missing in response.json()


def test_a_token_is_required(db):
    response = client_for().post(URL, {'old_password': OLD, 'new_password': NEW}, format='json')

    assert response.status_code == 401
