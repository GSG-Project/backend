from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    """Creates users that sign in with their email instead of a username."""

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError('An email address is required.')
        user = self.model(email=self.normalize_email(email).lower(), **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', False)
        extra_fields.setdefault('is_superuser', False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        return self._create_user(email, password, **extra_fields)


class User(AbstractUser):
    """A person with an account. Signs in with email and password."""

    username = None

    # first_name and last_name come from AbstractUser (both up to 150 characters).
    email = models.EmailField(unique=True)
    # When on, signing in also needs a code that is emailed to the user.
    two_factor_enabled = models.BooleanField(default=False)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['first_name']

    objects = UserManager()

    def __str__(self):
        return self.email


class EmailCode(models.Model):
    """A short-lived six digit code sent by email. Only a hash of the code is stored."""

    class Purpose(models.TextChoices):
        LOGIN = 'login', 'Sign-in'
        ENABLE_2FA = 'enable_2fa', 'Turn on two-step verification'

    user = models.ForeignKey('accounts.User', on_delete=models.CASCADE, related_name='email_codes')
    purpose = models.CharField(max_length=20, choices=Purpose.choices)
    code_hash = models.CharField(max_length=64)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()
    # Wrong guesses so far. The code stops working after a few.
    attempts = models.PositiveSmallIntegerField(default=0)
    used_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        indexes = [models.Index(fields=['user', 'purpose', '-created_at'])]

    def __str__(self):
        return f'{self.purpose} code for {self.user_id}'
