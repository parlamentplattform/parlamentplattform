"""Die neue private Anforderungstabelle ändert keine bisherigen Laufdaten."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db(transaction=True)


def test_private_tabelle_erhaelt_alte_laufdaten_und_betriebszugang():
    m = mitglied_anlegen("vergleichsmigration")
    vorher, ziel = [("ki", "0007_betrieblicher_zugang")], [("ki", "0008_private_vergleichsanfrage")]
    executor = MigrationExecutor(connection)
    try:
        executor.migrate(vorher)
        apps = executor.loader.project_state(vorher).apps
        alt = apps.get_model("ki", "KILauf").objects.create(
            angefordert_von_id=m.pk, zweck="rechtsbezug", eingabe="Alter Text", antwort="Alte Antwort",
            anbieter="synthetisch", modell="alt", kontext={"historisch": True}, tokens_ein=11, tokens_aus=13,
        )
        daten = apps.get_model("ki", "KILauf").objects.filter(pk=alt.pk).values().get()
        apps.get_model("ki", "SteckplatzZugang").objects.get_or_create(name="anbieter")
        zugang = apps.get_model("ki", "SteckplatzZugang").objects.values().get()
        executor = MigrationExecutor(connection)
        executor.migrate(ziel)
        apps = executor.loader.project_state(ziel).apps
        assert apps.get_model("ki", "KILauf").objects.filter(pk=alt.pk).values().get() == daten
        assert apps.get_model("ki", "SteckplatzZugang").objects.values().get() == zugang
        assert apps.get_model("ki", "Vergleichsanfrage").objects.count() == 0
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
