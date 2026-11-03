import copy
from io import StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import transaction

from faktenbasis import ressortimport
from faktenbasis.models import PersonalAggregat, PersonalRessortAbruf, PersonalRessorttabelle
from faktenbasis.personalbeleg import ORIGINAL_SHA256, QUELLE
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from parameter.models import Parameter
from plattform_core.personalressorts import aus_text
from plattform_core.test_personalressorts import METHODIK, TABELLE
from verfahren.models import AuditEintrag

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]

DATEN = {**aus_text(TABELLE, METHODIK), "quelle": QUELLE, "original_sha256": ORIGINAL_SHA256,
    "parser_fassung": 1, "seite": 30, "methodik_seite": 175, "tabelle": 7,
    "publikation": "Das Personal des Bundes 2026 – Daten und Fakten"}


@pytest.fixture
def gelesen(monkeypatch):
    monkeypatch.setattr(ressortimport, "lesen", lambda roh: copy.deepcopy(DATEN))
    return DATEN


def test_gesamte_tabelle_idempotent_leere_felder_und_abrufe_erhalten(gelesen):
    a = ressortimport.datei_importieren(b"synthetisch")
    zeit = a.inhalt.erfasst_am
    b = ressortimport.datei_importieren(b"synthetisch")
    assert a.neu and not b.neu and a.inhalt_id == b.inhalt_id
    assert PersonalRessorttabelle.objects.count() == 1 and PersonalRessortAbruf.objects.count() == 2
    b.inhalt.refresh_from_db()
    assert b.inhalt.erfasst_am == zeit and b.inhalt.ressorts == DATEN["ressorts"]
    assert b.inhalt.ressorts[0]["zentralstelle"] is None
    assert b.inhalt.gesamt == DATEN["gesamt"]
    assert not PersonalAggregat.objects.exists()  # Kein erfundener Beamten-/Vertrags-Split.
    assert AuditEintrag.objects.filter(ereignis__typ="personal_ressorts_import").count() == 2


def test_fehler_nach_erfolg_laesst_alle_originalwerte_unveraendert(gelesen, monkeypatch):
    a = ressortimport.datei_importieren(b"synthetisch")
    vorher = PersonalRessorttabelle.objects.values().get()
    def falsch(roh):
        raise ValueError("ressort_methodik")
    monkeypatch.setattr(ressortimport, "lesen", falsch)
    with pytest.raises(ValueError, match="ressort_methodik"):
        ressortimport.datei_importieren(b"fremd")
    assert PersonalRessorttabelle.objects.values().get() == vorher
    assert PersonalRessortAbruf.objects.first().inhalt_id is None
    assert a.inhalt_id and PersonalRessortAbruf.objects.count() == 2


@pytest.mark.parametrize("modell", [PersonalRessorttabelle, PersonalRessortAbruf])
@pytest.mark.parametrize("weg", ["save", "neues_objekt", "update", "bulk_update", "upsert", "delete", "queryset_delete"])
def test_gespeicherte_tabellen_und_abrufe_werden_nicht_ersetzt(gelesen, modell, weg):
    lauf = ressortimport.datei_importieren(b"synthetisch")
    a = lauf.inhalt if modell is PersonalRessorttabelle else lauf
    vorher = modell.objects.filter(pk=a.pk).values().get()
    feld, wert = ("ressorts", []) if modell is PersonalRessorttabelle else ("fehlercode", "Ersetzt")
    setattr(a, feld, wert)
    with transaction.atomic():
        with pytest.raises(ValidationError):
            if weg == "save":
                a.save()
            elif weg == "neues_objekt":
                modell(**{f.attname: getattr(a, f.attname) for f in modell._meta.concrete_fields}).save()
            elif weg == "update":
                modell.objects.filter(pk=a.pk).update(**{feld: wert})
            elif weg == "bulk_update":
                modell.objects.bulk_update([a], [feld])
            elif weg == "upsert":
                modell.objects.bulk_create([a], update_conflicts=True, unique_fields=["pk"], update_fields=[feld])
            elif weg == "delete":
                a.delete()
            else:
                modell.objects.filter(pk=a.pk).delete()
        assert modell.objects.filter(pk=a.pk).values().get() == vorher


def test_lokales_kommando_benutzt_keinen_netzzugriff(gelesen, monkeypatch, tmp_path):
    p = tmp_path / "bekannt.pdf"
    p.write_bytes(b"synthetisch")
    monkeypatch.setattr(ressortimport, "_herunterladen", lambda: pytest.fail("Kein Netz beim Dateibefehl"))
    ausgabe = StringIO()
    call_command("personal_ressorts_import", "--datei", str(p), stdout=ausgabe)
    assert "Ressorttabelle übernommen" in ausgabe.getvalue()
    assert PersonalRessortAbruf.objects.get().weg == "datei"


def test_gemeinsame_stundensperre_verhindert_bezug_vor_dem_netz(gelesen, monkeypatch):
    Parameter.objects.create(schluessel="faktenbasis-manuelle-abrufe-je-stunde", wert="0", beschreibung="Test", quelle="Test")
    monkeypatch.setattr(ressortimport, "_herunterladen", lambda: pytest.fail("Kein Abruf bei Sperre"))
    with pytest.raises(ValueError):
        ressortimport.amtlich_importieren()
    assert not PersonalRessortAbruf.objects.exists()
