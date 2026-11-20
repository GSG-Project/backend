import httpx
import pytest
from django.core.mail import EmailMultiAlternatives, send_mail

from apps.accounts.email_backends import EmailDeliveryError


@pytest.fixture
def brevo(settings):
    settings.EMAIL_BACKEND = 'apps.accounts.email_backends.BrevoEmailBackend'
    settings.BREVO_API_KEY = 'test-key'
    settings.DEFAULT_FROM_EMAIL = 'ModelJudge <no-reply@example.com>'


def test_the_email_is_posted_to_brevo(brevo, monkeypatch):
    seen = {}

    def fake_post(url, headers, json, timeout):
        seen.update(url=url, headers=headers, json=json)
        return httpx.Response(201, json={'messageId': 'x'}, request=httpx.Request('POST', url))

    monkeypatch.setattr(httpx, 'post', fake_post)
    message = EmailMultiAlternatives('Hi', 'plain', None, ['sara@example.com'])
    message.attach_alternative('<b>html</b>', 'text/html')

    assert message.send() == 1
    assert seen['headers']['api-key'] == 'test-key'
    assert seen['json']['sender'] == {'email': 'no-reply@example.com', 'name': 'ModelJudge'}
    assert seen['json']['to'] == [{'email': 'sara@example.com'}]
    assert seen['json']['textContent'] == 'plain' and seen['json']['htmlContent'] == '<b>html</b>'


def test_a_rejected_email_raises(brevo, monkeypatch):
    monkeypatch.setattr(
        httpx, 'post',
        lambda url, **kw: httpx.Response(401, text='bad key', request=httpx.Request('POST', url)),
    )

    with pytest.raises(EmailDeliveryError):
        send_mail('Hi', 'x', None, ['sara@example.com'])


def test_an_unreachable_provider_raises(brevo, monkeypatch):
    def boom(url, **kw):
        raise httpx.ConnectError('down')

    monkeypatch.setattr(httpx, 'post', boom)

    with pytest.raises(EmailDeliveryError):
        send_mail('Hi', 'x', None, ['sara@example.com'])
