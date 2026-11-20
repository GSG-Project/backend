"""Sends Django emails through Brevo's HTTPS API (free Render services block SMTP ports)."""
import logging
from email.utils import parseaddr

import httpx
from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_SEND_URL = 'https://api.brevo.com/v3/smtp/email'


class EmailDeliveryError(Exception):
    """The email provider did not accept a message."""


class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            if self._send(message):
                sent += 1
        return sent

    def _send(self, message) -> bool:
        if not settings.BREVO_API_KEY:
            return self._fail('BREVO_API_KEY is not configured.')

        name, address = parseaddr(message.from_email or settings.DEFAULT_FROM_EMAIL)
        sender = {'email': address}
        if name:
            sender['name'] = name

        payload = {
            'sender': sender,
            'to': [{'email': recipient} for recipient in message.to],
            'subject': message.subject,
            'textContent': message.body,
        }
        for content, mimetype in getattr(message, 'alternatives', []):
            if mimetype == 'text/html':
                payload['htmlContent'] = content

        try:
            response = httpx.post(
                BREVO_SEND_URL,
                headers={'api-key': settings.BREVO_API_KEY, 'accept': 'application/json'},
                json=payload,
                timeout=10,
            )
        except httpx.HTTPError as error:
            return self._fail(f'Brevo is unreachable: {type(error).__name__}')

        if response.is_success:
            return True
        # The response body is logged, never the request: it holds the recipient and the content.
        return self._fail(f'Brevo rejected the email ({response.status_code}): {response.text[:200]}')

    def _fail(self, reason: str) -> bool:
        logger.error('Email not sent: %s', reason)
        if self.fail_silently:
            return False
        raise EmailDeliveryError(reason)
