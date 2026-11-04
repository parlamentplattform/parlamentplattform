"""Gemeinsamer Upgrade ab dem tatsächlich veröffentlichten Stand 0.64.0.

Die drei Ausgangsgrenzen stammen aus Git 2a0a326beb37bd0d4fc0561015037fab66089ba8.
Nur synthetische Daten: Kein Produktionsabzug, Anbieteraufruf oder Quellenabruf.
Einzeltests der Migrationen ersetzen diesen gemeinsamen Altbestandsvergleich nicht.
"""

import hashlib
from datetime import UTC, datetime, timedelta
from uuid import UUID

import pytest
from django.db import IntegrityError, connection, transaction
from django.db.migrations.executor import MigrationExecutor

from plattform_core import GENESIS, ereignis_hash

pytestmark = pytest.mark.django_db(transaction=True)

LIVE_GRENZEN = {
    "ki": "0005_amtlicher_quellenkontext",
    "faktenbasis": "0003_abrufschutz",
    "verfahren": "0028_eigenstaendigkeit",
}
TABELLEN = (
    ("mitglieder", "Mitglied"), ("verfahren", "Verfahrensordnung"),
    ("verfahren", "Antrag"), ("verfahren", "AntragsFassung"),
    ("verfahren", "Unterstuetzung"), ("verfahren", "Stimmabgabe"),
    ("verfahren", "StimmRegister"), ("verfahren", "AuditEintrag"),
    ("gremien", "Entwurf"), ("gremien", "EntwurfsFassung"),
    ("ki", "KILauf"), ("ki", "KIAuftrag"), ("verfahren", "Beanstandung"),
    ("faktenbasis", "RisImport"), ("faktenbasis", "Norm"),
    ("faktenbasis", "NormText"), ("faktenbasis", "NormTextAbruf"),
)


def _stand(apps):
    return {
        kennung: list(apps.get_model(*kennung).objects.order_by("pk").values())
        for kennung in TABELLEN
    }


def _altbestand(apps):
    """Historische Modelle bewusst ohne heutige Save-/Fortschreibungslogik."""
    zeit = datetime(2026, 11, 2, 11, 12, 13, 123456, tzinfo=UTC)
    m = apps.get_model("mitglieder", "Mitglied").objects.create(
        username="synthetischer-upgrade", email="upgrade@example.invalid", mitgliedsnummer=900001,
    )
    regeln = {"policy_id": "alter-teststand", "version": 17, "beratung_tage": 29,
              "abstimmung_tage": 11, "historische_angabe": [None, 0, "äöü"]}
    apps.get_model("verfahren", "Verfahrensordnung").objects.create(
        policy_id="alter-teststand", version=17, regeln=regeln, beschlossen_am=zeit, aktiv=True,
    )
    a = apps.get_model("verfahren", "Antrag").objects.create(
        titel="Synthetischer archivierter Text", eingebracht_von_id=m.pk,
        eingebracht_am=zeit, phase="abstimmung", phase_beginn=zeit,
        stimmberechtigung_stichtag=zeit.date(), stimmberechtigte_anzahl=7,
        policy_snapshot=regeln, ebene="gemeinde", gebiet="Synthetischer Ort",
    )
    for nummer in range(1, 5):
        apps.get_model("verfahren", "AntragsFassung").objects.create(
            antrag_id=a.pk, nummer=nummer, wortlaut=f"Alter Wortlaut {nummer}: äöü\nZweite Zeile.",
            begruendung="Unverändert, auch wenn neue Auftragstexte hinzukommen.", erstellt_am=zeit,
        )
    entwurf = apps.get_model("gremien", "Entwurf").objects.create(
        antrag_id=a.pk, eingereichte_fassung=1, eingereicht_am=zeit,
        review_frist=zeit + timedelta(days=4), erstellt_am=zeit,
    )
    vorschlag = apps.get_model("gremien", "EntwurfsFassung").objects.create(
        entwurf_id=entwurf.pk, nummer=1, wortlaut="Alter öffentlicher Vorschlag.",
        verfasst_von_id=m.pk, erstellt_am=zeit,
    )
    apps.get_model("verfahren", "Unterstuetzung").objects.create(
        antrag_id=a.pk, mitglied_id=m.pk, erklaert_am=zeit, zurueckgezogen_am=zeit + timedelta(hours=1),
    )
    pseudonym = UUID("00000000-0000-4000-8000-000000000001")
    apps.get_model("verfahren", "Stimmabgabe").objects.create(
        antrag_id=a.pk, pseudonym=pseudonym, stimme="ja", abgegeben_am=zeit,
    )
    apps.get_model("verfahren", "StimmRegister").objects.create(
        antrag_id=a.pk, mitglied_id=m.pk, pseudonym=pseudonym, pruefcode="synthetischer-pruefcode",
    )
    kopf = GENESIS
    for typ in ("synthetischer_anfang", "synthetischer_folgeschritt"):
        ereignis = {"typ": typ, "antrag": a.pk, "zeit": zeit.isoformat()}
        wert = ereignis_hash(kopf, ereignis)
        apps.get_model("verfahren", "AuditEintrag").objects.create(
            zeit=zeit, ereignis=ereignis, vorgaenger=kopf, hash=wert,
        )
        kopf = wert
    for nummer, status in enumerate(("geplant", "laeuft", "erledigt", "gescheitert"), 1):
        lauf = None
        if status in {"erledigt", "gescheitert"}:
            lauf = apps.get_model("ki", "KILauf").objects.create(
                antrag_id=a.pk, angefordert_von_id=m.pk, zweck="rechtsbezug",
                eingabe="Historische Originaleingabe\nmit Umlauten äöü.",
                antwort="Historische Antwort" if status == "erledigt" else "",
                auftrag_version="rechtsbezug-v1", kontext={}, anbieter="synthetisch", modell="alt",
                tokens_ein=17, tokens_aus=5, dauer_ms=27, erstellt_am=zeit,
                erfolgreich=status == "erledigt", fehler="Altfehler" if status == "gescheitert" else "",
            )
        # Auch alte, nicht mehr deutbare Rohfelder dürfen Migrationen nicht still bereinigen.
        apps.get_model("ki", "KIAuftrag").objects.create(
            antrag_id=a.pk, angefordert_von_id=m.pk, zweck="rechtsbezug", fassung_nummer=nummer,
            status=status, lauf_id=lauf.pk if lauf else None,
            kontext={} if nummer == 1 else {"historisch": [nummer, "äöü", None]},
            quellenkontext={} if nummer == 1 else {"damaliger_rahmen": {"nummer": nummer}},
            erstellt_am=zeit, versuche=nummer - 1, zuletzt_versucht_am=zeit if nummer > 1 else None,
            naechster_versuch=zeit + timedelta(minutes=8),
            gesperrt_bis=zeit + timedelta(minutes=4) if status == "laeuft" else None,
            sperrcode="alte-reservierung" if status == "laeuft" else "",
            erledigt_am=zeit if lauf else None,
        )
    apps.get_model("ki", "KIAuftrag").objects.create(
        antrag_id=a.pk, angefordert_von_id=m.pk, zweck="rechtsbezug", quellenart="vorschlag",
        fassung_nummer=1, vorschlagsfassung_id=vorschlag.pk, erstellt_am=zeit,
    )
    apps.get_model("verfahren", "Beanstandung").objects.create(
        antrag_id=a.pk, mitglied_id=m.pk, lauf_id=lauf.pk,
        text="Historische Beanstandung bleibt offen.", erstellt_am=zeit,
    )
    original = {"synthetischer_originalinhalt": ["äöü", 0, None]}
    importlauf = apps.get_model("faktenbasis", "RisImport").objects.create(
        gesetzesnummer="00000001", stand=zeit.date(), erfolgreich=True, treffer=1,
        gelesen=1, neu=1, begonnen_am=zeit, beendet_am=zeit,
        api_url="https://example.invalid/metadaten", antwort=original, antwort_hash="a" * 64,
    )
    norm = apps.get_model("faktenbasis", "Norm").objects.create(
        ris_id="NOR00000001", gesetzesnummer="00000001", kurztitel="Synthetische Norm",
        stand=zeit.date(), quelle="https://example.invalid/norm", rohdaten=original,
        inhalt_hash="b" * 64, importlauf_id=importlauf.pk,
    )
    for fassung in (1, 2):
        xml = f"<synthetisch fassung='{fassung}'>äöü\nOriginal</synthetisch>".encode()
        text = apps.get_model("faktenbasis", "NormText").objects.create(
            norm_id=norm.pk, quelle="https://example.invalid/norm.xml", xml=xml,
            text=f"Historischer Parsertext {fassung}", xml_hash=hashlib.sha256(xml).hexdigest(),
            parser_fassung=fassung, erfasst_am=zeit,
        )
        apps.get_model("faktenbasis", "NormTextAbruf").objects.create(
            norm_id=norm.pk, inhalt_id=text.pk, erfolgreich=True, neu=True,
            begonnen_am=zeit, beendet_am=zeit, quelle=text.quelle,
        )


def test_gemeinsamer_upgrade_ab_064_erhaelt_den_gesamten_synthetischen_altbestand():
    executor = MigrationExecutor(connection)
    ziel = executor.loader.graph.leaf_nodes()
    vorher = [n for n in ziel if n[0] not in LIVE_GRENZEN] + list(LIVE_GRENZEN.items())
    try:
        executor.migrate(vorher)
        altapps = executor.loader.project_state(vorher).apps
        _altbestand(altapps)
        alt = _stand(altapps)

        executor = MigrationExecutor(connection)
        plan = executor.migration_plan(ziel)
        assert plan and all(not rueckwaerts for _, rueckwaerts in plan)
        assert {m.app_label for m, _ in plan} == set(LIVE_GRENZEN)
        executor.migrate(ziel)
        neuapps = executor.loader.project_state(ziel).apps
        neu = _stand(neuapps)
        for kennung, zeilen in alt.items():
            assert len(neu[kennung]) == len(zeilen), kennung
            for damals, heute in zip(zeilen, neu[kennung], strict=True):
                assert {k: heute[k] for k in damals} == damals, kennung

        for job in neu[("ki", "KIAuftrag")]:
            assert (job["beanstandung_id"], job["ursprung_id"]) == (None, None)
            assert job["korrekturkontext"] == job["folgenkontext"] == {}
        for kennung in (("faktenbasis", "Norm"), ("faktenbasis", "RisImport")):
            assert all(z["ebene"] == "Bund" and z["bundesland"] == "" for z in neu[kennung])
        for name in ("PersonalAggregat", "PersonalAbruf", "PersonalRessorttabelle", "PersonalRessortAbruf"):
            assert not neuapps.get_model("faktenbasis", name).objects.exists()
        assert not neuapps.get_model("ki", "VergleichsAnfrage").objects.exists()
        assert list(neuapps.get_model("ki", "SteckplatzZugang").objects.values()) == [
            {"name": "anbieter", "belegt": False},
        ]
        # Neue bedingte Eindeutigkeit darf normale alte Aufträge nicht doppelt erlauben.
        alter_job = neuapps.get_model("ki", "KIAuftrag").objects.order_by("pk").first()
        with pytest.raises(IntegrityError), transaction.atomic():
            neuapps.get_model("ki", "KIAuftrag").objects.create(
                antrag_id=alter_job.antrag_id, angefordert_von_id=alter_job.angefordert_von_id,
                zweck=alter_job.zweck, fassung_nummer=alter_job.fassung_nummer,
            )
        # Wiederholtes Deploy-Migrate ist ebenfalls ohne implizite Reparatur/Einreihung.
        MigrationExecutor(connection).migrate(ziel)
        assert _stand(neuapps) == neu
    finally:
        MigrationExecutor(connection).migrate(ziel)
