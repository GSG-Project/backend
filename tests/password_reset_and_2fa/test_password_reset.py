import re

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from rest_framework.test import APIClient

User = get_user_model()
REQUEST = '/api/auth/password-reset/'
CONFIRM = '/api/auth/password-reset/confirm/'
OLD = 'a-long-passphrase-42'
NEW = 'a-newer-passphrase-77'


@pytest.fixture
def sara(db):
    return User.objects.create_user(email='sara@example.com', first_name='Sara', password=OLD)


def link_params():
    body = mail.outbox[-1].body
    match = re.search(r'/reset-password\?uid=([^&\s]+)&token=([^\s]+)', body)
    return match.group(1), match.group(2)


def test_a_reset_email_with_a_link_is_sent(sara):
    response = APIClient().post(REQUEST, {'email': 'Sara@Example.com'}, format='json')

    assert response.status_code == 204
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ['sara@example.com']
    assert 'https://app.example.com/reset-password?uid=' in mail.outbox[0].body


def test_an_unknown_email_gets_the_same_answer_and_no_email(db):
    response = APIClient().post(REQUEST, {'email': 'nobody@example.com'}, format='json')

    assert response.status_code == 204
    assert mail.outbox == []


def test_a_second_request_within_a_minute_sends_nothing(sara):
    client = APIClient()
    client.post(REQUEST, {'email': sara.email}, format='json')
    response = client.post(REQUEST, {'email': sara.email}, format='json')

    assert response.status_code == 204
    assert len(mail.outbox) == 1


def test_a_failing_email_provider_is_not_revealed(sara, settings):
    settings.EMAIL_BACKEND = 'tests.password_reset_and_2fa.broken_backend.BrokenBackend'

    response = APIClient().post(REQUEST, {'email': sara.email}, format='json')

    assert response.status_code == 204


def test_the_link_sets_a_new_password(sara):
    client = APIClient()
    client.post(REQUEST, {'email': sara.email}, format='json')
    uid, token = link_params()

    response = client.post(CONFIRM, {'uid': uid, 'token': token, 'new_password': NEW}, format='json')

    assert response.status_code == 204
    sara.refresh_from_db()
    assert sara.check_password(NEW)


def test_a_link_works_only_once(sara):
    client = APIClient()
    client.post(REQUEST, {'email': sara.email}, format='json')
    uid, token = link_params()
    client.post(CONFIRM, {'uid': uid, 'token': token, 'new_password': NEW}, format='json')

    response = client.post(
        CONFIRM, {'uid': uid, 'token': token, 'new_password': 'yet-another-pass-99'}, format='json',
    )

    assert response.status_code == 400
    sara.refresh_from_db()
    assert sara.check_password(NEW)


def test_a_bad_token_is_rejected(sara):
    client = APIClient()
    client.post(REQUEST, {'email': sara.email}, format='json')
    uid, _ = link_params()

    response = client.post(CONFIRM, {'uid': uid, 'token': 'nope', 'new_password': NEW}, format='json')

    assert response.status_code == 400
    assert 'invalid or has expired' in response.json()['detail'][0]


def test_a_weak_password_is_rejected_and_the_link_survives(sara):
    client = APIClient()
    client.post(REQUEST, {'email': sara.email}, format='json')
    uid, token = link_params()

    weak = client.post(CONFIRM, {'uid': uid, 'token': token, 'new_password': '123'}, format='json')
    retry = client.post(CONFIRM, {'uid': uid, 'token': token, 'new_password': NEW}, format='json')

    assert weak.status_code == 400 and 'new_password' in weak.json()
    assert retry.status_code == 204


def test_an_expired_link_is_rejected(sara, settings):
    client = APIClient()
    client.post(REQUEST, {'email': sara.email}, format='json')
    uid, token = link_params()
    settings.PASSWORD_RESET_TIMEOUT = -1

    response = client.post(CONFIRM, {'uid': uid, 'token': token, 'new_password': NEW}, format='json')

    assert response.status_code == 400
