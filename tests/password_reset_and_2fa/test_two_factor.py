# ruff: noqa: E501
import re
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.core import mail
from django.utils import timezone
from rest_framework.test import APIClient

from apps.accounts.models import EmailCode

User = get_user_model()
PASSWORD = 'a-long-passphrase-42'


@pytest.fixture
def sara(db):
    return User.objects.create_user(email='sara@example.com', first_name='Sara', password=PASSWORD)


@pytest.fixture
def sara_2fa(sara):
    sara.two_factor_enabled = True
    sara.save()
    return sara


def last_code():
    return re.search(r'code is (\d{6})', mail.outbox[-1].body).group(1)


def login(client, user):
    return client.post('/api/auth/login/', {'email': user.email, 'password': PASSWORD}, format='json')


def test_login_without_2fa_returns_tokens(sara):
    response = login(APIClient(), sara)

    assert response.status_code == 200
    assert {'access', 'refresh'} <= set(response.json())
    assert mail.outbox == []


def test_wrong_password_is_still_401(sara_2fa):
    response = APIClient().post(
        '/api/auth/login/', {'email': sara_2fa.email, 'password': 'wrong'}, format='json',
    )

    assert response.status_code == 401
    assert mail.outbox == []


def test_login_with_2fa_sends_a_code_instead_of_tokens(sara_2fa):
    response = login(APIClient(), sara_2fa)

    assert response.status_code == 202
    body = response.json()
    assert body['requires_2fa'] is True and body['challenge']
    assert 'access' not in body
    assert body['email'] == 'sa**@example.com'
    assert len(mail.outbox) == 1


def test_the_code_completes_the_login(sara_2fa):
    client = APIClient()
    challenge = login(client, sara_2fa).json()['challenge']

    response = client.post(
        '/api/auth/login/verify/', {'challenge': challenge, 'code': last_code()}, format='json',
    )

    assert response.status_code == 200
    assert {'access', 'refresh'} <= set(response.json())


def test_a_code_works_only_once(sara_2fa):
    client = APIClient()
    challenge = login(client, sara_2fa).json()['challenge']
    code = last_code()
    client.post('/api/auth/login/verify/', {'challenge': challenge, 'code': code}, format='json')

    again = client.post('/api/auth/login/verify/', {'challenge': challenge, 'code': code}, format='json')

    assert again.status_code == 400 and again.json()['error'] == 'no_code'


def test_a_wrong_code_is_rejected(sara_2fa):
    client = APIClient()
    challenge = login(client, sara_2fa).json()['challenge']

    response = client.post(
        '/api/auth/login/verify/', {'challenge': challenge, 'code': '000000'}, format='json',
    )

    assert response.status_code == 400 and response.json()['error'] == 'invalid'


def test_five_wrong_codes_lock_the_code_even_for_the_right_one(sara_2fa):
    client = APIClient()
    challenge = login(client, sara_2fa).json()['challenge']
    right = last_code()
    wrong = '000000' if right != '000000' else '111111'
    for _ in range(5):
        client.post('/api/auth/login/verify/', {'challenge': challenge, 'code': wrong}, format='json')

    response = client.post('/api/auth/login/verify/', {'challenge': challenge, 'code': right}, format='json')

    assert response.status_code == 400 and response.json()['error'] == 'too_many_attempts'


def test_an_expired_code_is_rejected(sara_2fa):
    client = APIClient()
    challenge = login(client, sara_2fa).json()['challenge']
    EmailCode.objects.update(expires_at=timezone.now() - timedelta(seconds=1))

    response = client.post(
        '/api/auth/login/verify/', {'challenge': challenge, 'code': last_code()}, format='json',
    )

    assert response.status_code == 400 and response.json()['error'] == 'expired'


def test_a_forged_challenge_is_401(db):
    response = APIClient().post(
        '/api/auth/login/verify/', {'challenge': 'forged', 'code': '123456'}, format='json',
    )

    assert response.status_code == 401


def test_the_code_is_stored_hashed(sara_2fa):
    login(APIClient(), sara_2fa)

    assert last_code() not in EmailCode.objects.get().code_hash


def test_resend_is_limited_then_replaces_the_code(sara_2fa):
    client = APIClient()
    challenge = login(client, sara_2fa).json()['challenge']

    too_soon = client.post('/api/auth/login/resend/', {'challenge': challenge}, format='json')
    assert too_soon.status_code == 429 and 'Retry-After' in too_soon

    old = last_code()
    EmailCode.objects.update(created_at=timezone.now() - timedelta(minutes=1))
    resend = client.post('/api/auth/login/resend/', {'challenge': challenge}, format='json')
    assert resend.status_code == 204 and len(mail.outbox) == 2

    new = last_code()
    if new != old:
        stale = client.post('/api/auth/login/verify/', {'challenge': challenge, 'code': old}, format='json')
        assert stale.status_code == 400
    ok = client.post('/api/auth/login/verify/', {'challenge': challenge, 'code': new}, format='json')
    assert ok.status_code == 200


def test_login_reports_503_when_the_code_email_fails(sara_2fa, settings):
    settings.EMAIL_BACKEND = 'tests.password_reset_and_2fa.broken_backend.BrokenBackend'

    response = login(APIClient(), sara_2fa)

    assert response.status_code == 503
    assert not EmailCode.objects.exists()


def test_turning_2fa_on_needs_the_password_then_the_code(sara):
    client = APIClient()
    client.force_authenticate(sara)

    wrong = client.post('/api/auth/two-factor/enable/', {'password': 'nope'}, format='json')
    assert wrong.status_code == 400 and mail.outbox == []

    assert client.post('/api/auth/two-factor/enable/', {'password': PASSWORD}, format='json').status_code == 204
    bad = client.post('/api/auth/two-factor/confirm/', {'code': '000000'}, format='json')
    if last_code() != '000000':
        assert bad.status_code == 400
    sara.refresh_from_db()
    assert sara.two_factor_enabled is False

    ok = client.post('/api/auth/two-factor/confirm/', {'code': last_code()}, format='json')
    assert ok.status_code == 200 and ok.json()['two_factor_enabled'] is True
    sara.refresh_from_db()
    assert sara.two_factor_enabled is True


def test_a_login_code_cannot_turn_2fa_on(sara):
    client = APIClient()
    client.force_authenticate(sara)
    EmailCode.objects.create(
        user=sara, purpose=EmailCode.Purpose.LOGIN, code_hash='x', expires_at=timezone.now() + timedelta(minutes=5),
    )

    response = client.post('/api/auth/two-factor/confirm/', {'code': '123456'}, format='json')

    assert response.status_code == 400 and response.json()['error'] == 'no_code'


def test_turning_2fa_off_needs_the_password(sara_2fa):
    client = APIClient()
    client.force_authenticate(sara_2fa)

    assert client.post('/api/auth/two-factor/disable/', {'password': 'nope'}, format='json').status_code == 400
    response = client.post('/api/auth/two-factor/disable/', {'password': PASSWORD}, format='json')

    assert response.status_code == 200 and response.json()['two_factor_enabled'] is False


def test_the_user_endpoint_shows_the_setting_read_only(sara):
    client = APIClient()
    client.force_authenticate(sara)

    response = client.patch('/api/auth/me/', {'two_factor_enabled': True}, format='json')

    assert response.json()['two_factor_enabled'] is False
