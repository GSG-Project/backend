import pytest
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient

User = get_user_model()
URL = '/api/auth/me/'


@pytest.fixture
def sara(db):
    return User.objects.create_user(
        email='sara@example.com', first_name='Sara', last_name='Ali', password='a-long-passphrase-42',
    )


def client_for(user=None):
    client = APIClient()
    if user is not None:
        client.force_authenticate(user)
    return client


def test_me_returns_both_names(sara):
    body = client_for(sara).get(URL).json()

    assert body == {'id': sara.pk, 'email': 'sara@example.com', 'first_name': 'Sara', 'last_name': 'Ali',
                    'two_factor_enabled': False}


def test_patch_changes_the_names_and_saves_them(sara):
    response = client_for(sara).patch(URL, {'first_name': 'Layla', 'last_name': 'Hassan'}, format='json')

    assert response.status_code == 200
    assert response.json()['first_name'] == 'Layla' and response.json()['last_name'] == 'Hassan'
    sara.refresh_from_db()
    assert (sara.first_name, sara.last_name) == ('Layla', 'Hassan')
    # The change is what the next read returns.
    assert client_for(sara).get(URL).json()['first_name'] == 'Layla'


def test_patch_with_one_field_leaves_the_other_alone(sara):
    client_for(sara).patch(URL, {'last_name': 'Hassan'}, format='json')

    sara.refresh_from_db()
    assert (sara.first_name, sara.last_name) == ('Sara', 'Hassan')


def test_the_last_name_can_be_cleared(sara):
    response = client_for(sara).patch(URL, {'last_name': ''}, format='json')

    assert response.status_code == 200
    sara.refresh_from_db()
    assert sara.last_name == ''


def test_the_first_name_cannot_be_blank(sara):
    response = client_for(sara).patch(URL, {'first_name': ''}, format='json')

    assert response.status_code == 400 and 'first_name' in response.json()
    sara.refresh_from_db()
    assert sara.first_name == 'Sara'


@pytest.mark.parametrize('field, value', [('email', 'new@example.com'), ('id', 999), ('is_staff', True)])
def test_other_fields_cannot_be_changed(sara, field, value):
    client_for(sara).patch(URL, {field: value}, format='json')

    sara.refresh_from_db()
    assert sara.email == 'sara@example.com' and sara.pk != 999 and not sara.is_staff


def test_only_the_signed_in_user_is_changed(sara):
    other = User.objects.create_user(
        email='omar@example.com', first_name='Omar', password='a-long-passphrase-42',
    )

    client_for(sara).patch(URL, {'first_name': 'Layla'}, format='json')

    other.refresh_from_db()
    assert other.first_name == 'Omar'


def test_patch_requires_a_token(db):
    assert client_for().patch(URL, {'first_name': 'X'}, format='json').status_code == 401


def test_put_is_not_allowed(sara):
    assert client_for(sara).put(URL, {'first_name': 'X'}, format='json').status_code == 405
