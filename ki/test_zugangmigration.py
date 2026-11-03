import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db(transaction=True)


def test_zugangmigration_erhaelt_original_laufdaten_und_legte_nur_betriebszeile_an():
    m = mitglied_anlegen("zugang-migration")
    vorher = [("ki", "0006_korrekturlauf")]
    ziel = [("ki", "0007_betrieblicher_zugang")]
    executor = MigrationExecutor(connection)
    try:
        executor.migrate(vorher)
        apps = executor.loader.project_state(vorher).apps
        alt = apps.get_model("ki", "KILauf").objects.create(angefordert_von_id=m.pk,
            zweck="rechtsbezug", eingabe="Alter öffentlicher Wortlaut", antwort="Alte Originalantwort",
            anbieter="synthetisch", modell="alt", auftrag_version="rechtsbezug-v1",
            kontext={"alt": True}, tokens_ein=7, tokens_aus=3)
        daten = apps.get_model("ki", "KILauf").objects.filter(pk=alt.pk).values().get()
        executor = MigrationExecutor(connection)
        executor.migrate(ziel)
        apps = executor.loader.project_state(ziel).apps
        assert apps.get_model("ki", "KILauf").objects.filter(pk=alt.pk).values().get() == daten
        zugang = apps.get_model("ki", "SteckplatzZugang").objects.get()
        assert zugang.name == "anbieter" and not zugang.belegt
    finally:
        MigrationExecutor(connection).migrate(ziel)
