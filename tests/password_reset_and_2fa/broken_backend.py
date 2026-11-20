from django.core.mail.backends.base import BaseEmailBackend


class BrokenBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        raise RuntimeError('provider down')
