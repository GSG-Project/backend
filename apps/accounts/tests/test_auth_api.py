import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()

PASSWORD = 'a-long-passphrase-42'
REGISTER = {'email': 'Sara@Example.com', 'first_name': 'Sara', 'last_name': 'Ali', 'password': PASSWORD}


@pytest.fixture
def client():
    return APIClient()


@pytest.fixture
def user(db):
    return User.objects.create_user(email='sara@example.com', first_name='Sara', password=PASSWORD)


@pytest.mark.django_db
def test_register_creates_the_account_and_returns_tokens(client):
    response = client.post('/api/auth/register/', REGISTER, format='json')

    assert response.status_code == 201
    body = response.json()
    assert body['user']['email'] == 'sara@example.com'  # stored in lower case
    assert body['user']['first_name'] == 'Sara' and body['user']['last_name'] == 'Ali'
    assert body['access'] and body['refresh']
    assert 'password' not in body['user']
    created = User.objects.get(email='sara@example.com')
    assert created.password != PASSWORD and created.check_password(PASSWORD)
    assert not created.is_staff


@pytest.mark.django_db
def test_register_tokens_work_straight_away(client):
    access = client.post('/api/auth/register/', REGISTER, format='json').json()['access']

    response = client.get('/api/auth/me/', HTTP_AUTHORIZATION=f'Bearer {access}')

    assert response.status_code == 200
    assert response.json()['email'] == 'sara@example.com'


@pytest.mark.django_db
def test_register_rejects_a_duplicate_email_ignoring_case(client, user):
    response = client.post('/api/auth/register/', {**REGISTER, 'email': 'SARA@example.com'}, format='json')

    assert response.status_code == 400
    assert 'email' in response.json()
    assert User.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize('field', ['email', 'first_name', 'password'])
def test_register_requires_every_field(client, field):
    data = {k: v for k, v in REGISTER.items() if k != field}

    response = client.post('/api/auth/register/', data, format='json')

    assert response.status_code == 400
    assert field in response.json()
    assert User.objects.count() == 0


@pytest.mark.django_db
@pytest.mark.parametrize('password', ['short1', 'password123', '1234567890'])
def test_register_rejects_weak_passwords(client, password):
    response = client.post('/api/auth/register/', {**REGISTER, 'password': password}, format='json')

    assert response.status_code == 400
    assert 'non_field_errors' in response.json() or 'password' in response.json()
    assert User.objects.count() == 0


@pytest.mark.django_db
def test_register_ignores_attempts_to_become_staff(client):
    client.post('/api/auth/register/', {**REGISTER, 'is_staff': True, 'is_superuser': True}, format='json')

    created = User.objects.get(email='sara@example.com')
    assert not created.is_staff and not created.is_superuser


def test_login_returns_tokens(client, user):
    credentials = {'email': 'sara@example.com', 'password': PASSWORD}
    response = client.post('/api/auth/login/', credentials, format='json')

    assert response.status_code == 200
    assert set(response.json()) == {'access', 'refresh'}


@pytest.mark.parametrize('email, password', [
    ('sara@example.com', 'wrong-password-99'),
    ('nobody@example.com', PASSWORD),
])
def test_login_rejects_bad_credentials(client, user, email, password):
    response = client.post('/api/auth/login/', {'email': email, 'password': password}, format='json')

    assert response.status_code == 401


def test_refresh_returns_a_new_access_token(client, user):
    tokens = client.post(
        '/api/auth/login/', {'email': 'sara@example.com', 'password': PASSWORD}, format='json'
    ).json()

    response = client.post('/api/auth/refresh/', {'refresh': tokens['refresh']}, format='json')

    assert response.status_code == 200
    assert response.json()['access']


def test_refresh_rejects_an_access_token(client, user):
    tokens = client.post(
        '/api/auth/login/', {'email': 'sara@example.com', 'password': PASSWORD}, format='json'
    ).json()

    response = client.post('/api/auth/refresh/', {'refresh': tokens['access']}, format='json')

    assert response.status_code == 401


def test_me_requires_a_token(client, db):
    assert client.get('/api/auth/me/').status_code == 401
    assert client.get('/api/auth/me/', HTTP_AUTHORIZATION='Bearer not-a-token').status_code == 401


def test_inactive_users_cannot_sign_in(client, user):
    user.is_active = False
    user.save()

    credentials = {'email': 'sara@example.com', 'password': PASSWORD}
    response = client.post('/api/auth/login/', credentials, format='json')

    assert response.status_code == 401


def test_public_endpoints_still_work_without_a_token(client, db):
    assert client.get('/api/models/').status_code == 200


def test_public_endpoints_accept_a_valid_token(client, user):
    access = client.post(
        '/api/auth/login/', {'email': 'sara@example.com', 'password': PASSWORD}, format='json'
    ).json()['access']

    response = client.get('/api/models/', HTTP_AUTHORIZATION=f'Bearer {access}')

    assert response.status_code == 200
