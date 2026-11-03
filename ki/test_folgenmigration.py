"""Neues Kontextfeld ergänzt keine vermeintlichen Quellen in Altaufträgen."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor

from verfahren.models import Antrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db(transaction=True)


def test_folgenfeld_erhaelt_alte_auftraege_laeufe_und_quellen():
    m = mitglied_anlegen("folgenmigration")
    a = Antrag.objects.create(titel="Historische Quelle", eingebracht_von=m, policy_snapshot={})
    vorher = [("ki", "0009_vergleichszweck")]
    ziel = [("ki", "0010_rechtsfolgenauftrag")]
    executor = MigrationExecutor(connection)
    try:
        executor.migrate(vorher)
        apps = executor.loader.project_state(vorher).apps
        lauf = apps.get_model("ki", "KILauf").objects.create(
            angefordert_von_id=m.pk, antrag_id=a.pk, zweck="rechtsbezug", eingabe="Alter Wortlaut",
            antwort="Alte unveränderte Antwort", auftrag_version="rechtsbezug-v1", anbieter="synthetisch",
            modell="alt", kontext={"historisch": True}, tokens_ein=3, tokens_aus=7,
        )
        job = apps.get_model("ki", "KIAuftrag").objects.create(
            angefordert_von_id=m.pk, antrag_id=a.pk, zweck="rechtsbezug", kontext={"alt": True},
            quellenkontext={"damalig": "unverändert"}, lauf_id=lauf.pk,
        )
        job_alt = apps.get_model("ki", "KIAuftrag").objects.values().get(pk=job.pk)
        lauf_alt = apps.get_model("ki", "KILauf").objects.values().get(pk=lauf.pk)
        executor = MigrationExecutor(connection)
        executor.migrate(ziel)
        apps = executor.loader.project_state(ziel).apps
        assert apps.get_model("ki", "KIAuftrag").objects.values().get(pk=job.pk) == {**job_alt, "folgenkontext": {}}
        assert apps.get_model("ki", "KILauf").objects.values().get(pk=lauf.pk) == lauf_alt
    finally:
        executor = MigrationExecutor(connection)
        executor.migrate(executor.loader.graph.leaf_nodes())
