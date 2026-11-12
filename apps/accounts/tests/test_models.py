import pytest
from django.contrib.auth import get_user_model
from django.db import IntegrityError

User = get_user_model()


@pytest.mark.django_db
def test_create_user_normalizes_the_email_and_hashes_the_password():
    user = User.objects.create_user(
        email='Sara@EXAMPLE.com', first_name='Sara', password='a-long-passphrase-42',
    )

    assert user.email == 'sara@example.com'
    assert user.password != 'a-long-passphrase-42'
    assert not user.is_staff and not user.is_superuser


@pytest.mark.django_db
def test_create_user_requires_an_email():
    with pytest.raises(ValueError):
        User.objects.create_user(email='', first_name='Sara', password='a-long-passphrase-42')


@pytest.mark.django_db
def test_create_superuser_is_staff():
    admin = User.objects.create_superuser(
        email='admin@example.com', first_name='Admin', password='a-long-passphrase-42'
    )

    assert admin.is_staff and admin.is_superuser


@pytest.mark.django_db
def test_email_is_unique():
    User.objects.create_user(email='sara@example.com', first_name='Sara', password='a-long-passphrase-42')

    with pytest.raises(IntegrityError):
        User.objects.create_user(
            email='sara@example.com', first_name='Other', password='a-long-passphrase-42',
        )
