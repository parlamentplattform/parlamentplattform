"""Die Konto-Erweiterung bewahrt bestehende IDs, Parteidaten und Verfahrenshistorie."""

import pytest
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.utils import timezone


@pytest.mark.django_db(transaction=True)
def test_bestandskonten_bleiben_ohne_historienumbau_parteikonten():
    from verfahren.models import AuditEintrag

    AuditEintrag.anhaengen({"typ": "migrationsprobe_gemeinde"})
    audit = list(AuditEintrag.objects.order_by("pk").values())
    executor = MigrationExecutor(connection)
    ziel = [("mitglieder", "0023_wohnsitzangabe")]
    latest = executor.loader.graph.leaf_nodes()
    executor.migrate(ziel)
    try:
        apps = executor.loader.project_state(ziel).apps
        Mitglied = apps.get_model("mitglieder", "Mitglied")
        Token = apps.get_model("mitglieder", "EinmalToken")
        m = Mitglied.objects.create(
            username="bestand", email="bestand@example.org", mitgliedsnummer=123,
            beitritt=timezone.localdate(), identitaetsstufe="geprueft", beitragsreferenz_stamm="ABC123",
            ausweis_code="0123456789", post_einwilligung=True,
        )
        token = Token.objects.create(
            mitglied=m, zweck="login", token_hash="a" * 64, gueltig_bis=timezone.now() + timezone.timedelta(days=1)
        )
        vorher = Mitglied.objects.filter(pk=m.pk).values().get()
        executor = MigrationExecutor(connection)
        executor.migrate(latest)
        apps = executor.loader.project_state(latest).apps
        Neu = apps.get_model("mitglieder", "Mitglied")
        nachher = Neu.objects.filter(pk=m.pk).values().get()
        assert nachher.pop("parteikonto") is True
        assert nachher == vorher
        assert apps.get_model("mitglieder", "Gemeindezugang").objects.count() == 0
        assert apps.get_model("mitglieder", "EinmalToken").objects.get(pk=token.pk).mitglied_id == m.pk
        assert list(AuditEintrag.objects.order_by("pk").values()) == audit
    finally:
        MigrationExecutor(connection).migrate(latest)
