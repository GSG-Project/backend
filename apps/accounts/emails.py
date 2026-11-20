# ruff: noqa: E501
"""The emails the accounts app sends. Each is plain text with a simple HTML copy."""
from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.html import escape

APP = 'ModelJudge'


def _send(user, subject, text, html):
    message = EmailMultiAlternatives(subject, text, settings.DEFAULT_FROM_EMAIL, [user.email])
    message.attach_alternative(html, 'text/html')
    message.send(fail_silently=False)


def _html(heading, paragraphs, button=None, big=None):
    body = ''.join(f'<p style="margin:0 0 14px">{escape(p)}</p>' for p in paragraphs)
    if big:
        body += (
            '<p style="margin:18px 0;font-size:32px;font-weight:700;letter-spacing:6px;'
            f'color:#6D4AFF">{escape(big)}</p>'
        )
    if button:
        label, url = button
        body += (
            f'<p style="margin:18px 0"><a href="{escape(url)}" style="background:#6D4AFF;color:#fff;'
            f'padding:12px 22px;border-radius:8px;text-decoration:none;font-weight:600">{escape(label)}</a></p>'
            f'<p style="margin:0 0 14px;color:#6B6681;font-size:13px">Or paste this link into your browser:<br>{escape(url)}</p>'
        )
    return (
        '<div style="font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;color:#171426;max-width:480px">'
        f'<h2 style="color:#6D4AFF">{APP}</h2><h3 style="margin:0 0 14px">{escape(heading)}</h3>{body}'
        '<p style="margin:18px 0 0;color:#6B6681;font-size:13px">If you did not ask for this, you can ignore this email.</p>'
        '</div>'
    )


def send_password_reset_email(user, link):
    minutes = settings.PASSWORD_RESET_TIMEOUT // 60
    text = (
        f'Hi {user.first_name},\n\nWe received a request to reset your {APP} password. '
        f'Open this link to choose a new one (it works for {minutes} minutes):\n\n{link}\n\n'
        'If you did not ask for this, you can ignore this email.'
    )
    html = _html(
        'Reset your password',
        [f'Hi {user.first_name},', f'We received a request to reset your {APP} password. '
         f'The link works for {minutes} minutes.'],
        button=('Choose a new password', link),
    )
    _send(user, f'Reset your {APP} password', text, html)


def send_code_email(user, code, minutes, reason):
    """`reason` finishes the sentence "Use this code to ...", for example "sign in"."""
    text = (
        f'Hi {user.first_name},\n\nYour {APP} code is {code}.\n'
        f'Use it to {reason}. It works for {minutes} minutes and only once.\n\n'
        'If you did not ask for this, someone may know your password: change it.'
    )
    html = _html(
        f'Your code: {code}',
        [f'Hi {user.first_name},', f'Use this code to {reason}. It works for {minutes} minutes and only once.'],
        big=code,
    )
    _send(user, f'Your {APP} code: {code}', text, html)
