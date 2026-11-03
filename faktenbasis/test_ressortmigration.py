import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from faktenbasis.test_personalimport import DATEN

pytestmark = pytest.mark.django_db(transaction=True)


def test_additive_ressortmigration_erhaelt_den_bisherigen_personalbeleg_vollstaendig():
    ziel = [("faktenbasis", "0006_personalressorts")]
    vorher = [("faktenbasis", "0005_normherkunft_bund_land")]
    executor = MigrationExecutor(connection)
    try:
        executor.migrate(vorher)
        apps = executor.loader.project_state(vorher).apps
        alt = apps.get_model("faktenbasis", "PersonalAggregat").objects.create(**DATEN)
        ursprung = apps.get_model("faktenbasis", "PersonalAggregat").objects.filter(pk=alt.pk).values().get()
        executor = MigrationExecutor(connection)
        executor.migrate(ziel)
        apps = executor.loader.project_state(ziel).apps
        assert apps.get_model("faktenbasis", "PersonalAggregat").objects.filter(pk=alt.pk).values().get() == ursprung
        assert not apps.get_model("faktenbasis", "PersonalRessorttabelle").objects.exists()
    finally:
        MigrationExecutor(connection).migrate(ziel)
