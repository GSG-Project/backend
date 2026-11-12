"""The 0002 migration must keep the names accounts already have, in both directions."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

BEFORE = [('accounts', '0001_initial')]
AFTER = [('accounts', '0002_split_name')]


@pytest.fixture
def migrate(transactional_db):
    def run(target):
        executor = MigrationExecutor(connection)
        executor.migrate(target)
        return MigrationExecutor(connection).loader.project_state(target).apps

    yield run
    # Leave the database at the latest migration for the tests that follow.
    MigrationExecutor(connection).migrate(MigrationExecutor(connection).loader.graph.leaf_nodes())


def make_user(apps, email, name):
    return apps.get_model('accounts', 'User').objects.create(email=email, name=name, password='x')


@pytest.mark.parametrize('name, first, last', [
    ('Sara', 'Sara', ''),
    ('Sara Ali', 'Sara', 'Ali'),
    ('  Sara   Ali Hassan ', 'Sara', 'Ali Hassan'),
    ('', '', ''),
])
def test_existing_names_are_split(migrate, name, first, last):
    old_apps = migrate(BEFORE)
    make_user(old_apps, 'a@example.com', name)

    new_apps = migrate(AFTER)

    user = new_apps.get_model('accounts', 'User').objects.get()
    assert (user.first_name, user.last_name) == (first, last)


def test_the_migration_can_be_reversed(migrate):
    new_apps = migrate(AFTER)
    new_apps.get_model('accounts', 'User').objects.create(
        email='a@example.com', first_name='Sara', last_name='Ali', password='x',
    )

    old_apps = migrate(BEFORE)

    assert old_apps.get_model('accounts', 'User').objects.get().name == 'Sara Ali'
