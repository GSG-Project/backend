"""Six digit email codes, used to turn on two-step verification and to sign in with it."""
import secrets
from datetime import timedelta

from django.core import signing
from django.db.models import F
from django.utils import timezone
from django.utils.crypto import constant_time_compare, salted_hmac

from .emails import send_code_email
from .models import EmailCode

CODE_LIFETIME = timedelta(minutes=10)
MAX_ATTEMPTS = 5
RESEND_COOLDOWN = timedelta(seconds=30)
CHALLENGE_SALT = 'accounts.login-challenge'
CHALLENGE_MAX_AGE = int(CODE_LIFETIME.total_seconds())

REASONS = {
    EmailCode.Purpose.LOGIN: 'sign in',
    EmailCode.Purpose.ENABLE_2FA: 'turn on two-step verification',
}


class CodeError(Exception):
    """A code could not be accepted. `code` tells the client why."""

    def __init__(self, message, code):
        super().__init__(message)
        self.message = message
        self.code = code


class CooldownError(Exception):
    def __init__(self, wait):
        super().__init__('Please wait before asking for another code.')
        self.wait = wait


def _hash(code: str) -> str:
    return salted_hmac('accounts.email-code', code).hexdigest()


def seconds_until_resend(user, purpose) -> int:
    last = EmailCode.objects.filter(user=user, purpose=purpose).order_by('-created_at').first()
    if last is None:
        return 0
    remaining = last.created_at + RESEND_COOLDOWN - timezone.now()
    return max(0, int(remaining.total_seconds()) + 1) if remaining.total_seconds() > 0 else 0


def issue_code(user, purpose) -> None:
    """Replace any open code of this purpose with a new one and email it."""
    wait = seconds_until_resend(user, purpose)
    if wait:
        raise CooldownError(wait)

    code = f'{secrets.randbelow(10 ** 6):06d}'
    now = timezone.now()
    # Only the newest code is valid, so older ones are closed.
    EmailCode.objects.filter(user=user, purpose=purpose, used_at__isnull=True).update(used_at=now)
    created = EmailCode.objects.create(
        user=user, purpose=purpose, code_hash=_hash(code), expires_at=now + CODE_LIFETIME,
    )
    try:
        send_code_email(user, code, int(CODE_LIFETIME.total_seconds() // 60), REASONS[purpose])
    except Exception:
        # Nothing was delivered, so do not keep a code (and a cooldown) the user never saw.
        created.delete()
        raise


def check_code(user, purpose, submitted: str) -> None:
    """Accept the newest open code, once. Raises CodeError otherwise."""
    entry = (
        EmailCode.objects.filter(user=user, purpose=purpose, used_at__isnull=True)
        .order_by('-created_at').first()
    )
    if entry is None:
        raise CodeError('No code is waiting. Ask for a new one.', 'no_code')
    if entry.expires_at <= timezone.now():
        raise CodeError('This code has expired. Ask for a new one.', 'expired')
    if entry.attempts >= MAX_ATTEMPTS:
        raise CodeError('Too many wrong attempts. Ask for a new code.', 'too_many_attempts')

    # Count the attempt first, so a failed guess is never free.
    EmailCode.objects.filter(pk=entry.pk).update(attempts=F('attempts') + 1)
    if not constant_time_compare(entry.code_hash, _hash((submitted or '').strip())):
        raise CodeError('That code is not correct.', 'invalid')

    updated = EmailCode.objects.filter(pk=entry.pk, used_at__isnull=True).update(used_at=timezone.now())
    if not updated:  # used by a parallel request
        raise CodeError('No code is waiting. Ask for a new one.', 'no_code')


def make_challenge(user) -> str:
    return signing.dumps({'user': user.pk}, salt=CHALLENGE_SALT)


def user_from_challenge(challenge: str):
    """The user a sign-in challenge was issued for, or None if it is invalid or too old."""
    from .models import User

    try:
        data = signing.loads(challenge, salt=CHALLENGE_SALT, max_age=CHALLENGE_MAX_AGE)
    except signing.BadSignature:
        return None
    return User.objects.filter(pk=data.get('user'), is_active=True).first()


def mask_email(email: str) -> str:
    name, _, domain = email.partition('@')
    visible = name[:1] if len(name) <= 2 else name[:2]
    return f'{visible}{"*" * max(1, len(name) - len(visible))}@{domain}'
