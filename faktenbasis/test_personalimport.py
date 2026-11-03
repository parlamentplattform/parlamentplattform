import copy
from email.message import Message
from io import BytesIO, StringIO

import pytest
from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.db import transaction
from django.urls import reverse

from faktenbasis import personalimport
from faktenbasis.models import PersonalAbruf, PersonalAggregat
from faktenbasis.personalbeleg import ORIGINAL_SHA256, QUELLE
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from parameter.models import Parameter
from verfahren.models import AuditEintrag

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]

DATEN = {"datenjahr": 2025, "einheit": "VBÄ", "beamte": 60312, "vertragliches_personal": 77788, "gesamt": 138100,
    "quelle": QUELLE, "original_sha256": ORIGINAL_SHA256, "parser_fassung": 1, "seite": 75, "tabelle": 20,
    "publikation": "Das Personal des Bundes 2026 – Daten und Fakten", "bereich": "Bundespersonal nach Art des Dienstverhältnisses"}


@pytest.fixture
def gelesen(monkeypatch):
    monkeypatch.setattr(personalimport, "lesen", lambda raw: copy.deepcopy(DATEN))
    return DATEN


def test_einmaliger_inhalt_jeder_versuch_und_keine_original_pdf_kopie(gelesen):
    a = personalimport.datei_importieren(b"Testdatei")
    zeit = a.aggregat.erfasst_am
    b = personalimport.datei_importieren(b"Testdatei")
    assert a.neu and not b.neu and a.aggregat_id == b.aggregat_id
    assert PersonalAggregat.objects.count() == 1 and PersonalAbruf.objects.count() == 2
    b.aggregat.refresh_from_db()
    assert b.aggregat.erfasst_am == zeit
    assert not {"pdf", "dateiname", "mitglied", "email"} & {f.name for f in PersonalAggregat._meta.fields}
    assert AuditEintrag.objects.filter(ereignis__typ="personal_import").count() == 2


def test_fehler_nach_erfolg_veraendert_keinen_bestand(gelesen, monkeypatch, client):
    a = personalimport.datei_importieren(b"Testdatei")
    def kaputt(raw):
        raise ValueError("personal_unbekannter_beleg")
    monkeypatch.setattr(personalimport, "lesen", kaputt)
    with pytest.raises(ValueError, match="personal_unbekannter_beleg"):
        personalimport.datei_importieren(b"fremd")
    assert PersonalAggregat.objects.count() == 1 and PersonalAbruf.objects.count() == 2
    assert PersonalAbruf.objects.first().aggregat_id is None
    html = client.get(reverse("faktenbasis:personal")).content.decode()
    assert "Frühere Angaben bleiben erhalten" in html and "2025" in html
    assert client.get(reverse("faktenbasis:personal_detail", args=[a.aggregat_id])).status_code == 200


@pytest.mark.parametrize("modell", [PersonalAggregat, PersonalAbruf])
@pytest.mark.parametrize("weg", ["save", "neue_instanz", "update", "bulk_update", "upsert", "delete", "queryset_delete"])
def test_alle_schnappschuesse_unveraenderlich(gelesen, modell, weg):
    lauf = personalimport.datei_importieren(b"Testdatei")
    a = lauf.aggregat if modell is PersonalAggregat else lauf
    vorher = modell.objects.filter(pk=a.pk).values().get()
    feld = "bereich" if modell is PersonalAggregat else "weg"
    setattr(a, feld, "Ersetzt")
    with transaction.atomic():
        with pytest.raises(ValidationError):
            if weg == "save":
                a.save()
            elif weg == "neue_instanz":
                modell(**{f.attname: getattr(a, f.attname) for f in modell._meta.concrete_fields}).save()
            elif weg == "update":
                modell.objects.filter(pk=a.pk).update(**{feld: "Ersetzt"})
            elif weg == "bulk_update":
                modell.objects.bulk_update([a], [feld])
            elif weg == "upsert":
                modell.objects.bulk_create([a], update_conflicts=True, unique_fields=["pk"], update_fields=[feld])
            elif weg == "delete":
                a.delete()
            else:
                modell.objects.filter(pk=a.pk).delete()
        assert modell.objects.filter(pk=a.pk).values().get() == vorher


def test_kommando_liest_eine_begrenzte_datei_ohne_netz(gelesen, tmp_path, monkeypatch):
    p = tmp_path / "beleg.pdf"
    p.write_bytes(b"lokale Testdatei")
    monkeypatch.setattr(personalimport, "_herunterladen", lambda: pytest.fail("Dateibefehl darf nicht ins Netz"))
    ausgabe = StringIO()
    call_command("personal_import", "--datei", str(p), stdout=ausgabe)
    assert "Personalbeleg übernommen" in ausgabe.getvalue()
    assert PersonalAbruf.objects.get().weg == "datei"


def test_erschoepftes_gemeinsames_kontingent_verhindert_netz(gelesen, monkeypatch):
    Parameter.objects.create(schluessel="faktenbasis-manuelle-abrufe-je-stunde", wert="0", beschreibung="Test", quelle="Test")
    monkeypatch.setattr(personalimport, "_herunterladen", lambda: pytest.fail("Kein Abruf bei Budget0"))
    with pytest.raises(ValueError):
        personalimport.amtlich_importieren()
    assert not PersonalAbruf.objects.exists()


def test_oeffentliche_seiten_und_export_bleiben_lesend(gelesen, client, monkeypatch):
    a = personalimport.datei_importieren(b"Testdatei").aggregat
    vorher = AuditEintrag.objects.count()
    monkeypatch.setattr(personalimport, "_herunterladen", lambda: pytest.fail("Kein Netz beim Lesen"))
    for name, args in (("personal", []), ("personal_detail", [a.pk]), ("personal_nachweis", [a.pk])):
        u = reverse(f"faktenbasis:{name}", args=args)
        assert client.get(u).status_code == 200
        assert client.post(u).status_code == 405
    d = client.get(reverse("faktenbasis:personal_nachweis", args=[a.pk])).json()
    assert d["gesamt"] == 138100 and d["original_sha256"] == ORIGINAL_SHA256
    assert d["datenjahr"] == 2025 and d["einheit"] == "VBÄ" and d["seite"] == 75
    assert AuditEintrag.objects.count() == vorher


def test_fester_amtlicher_abruf_ohne_umleitung_oder_freie_url(gelesen, monkeypatch):
    class Antwort(BytesIO):
        status = 200
        headers = Message()
    antwort = Antwort(b"bekannter Testbeleg")
    antwort.headers["Content-Type"] = "application/pdf"
    class Opener:
        def open(self, request, timeout):
            assert request.full_url == QUELLE and timeout == 15
            return antwort
    monkeypatch.setattr(personalimport.urllib.request, "build_opener", lambda *a: Opener())
    lauf = personalimport.amtlich_importieren()
    assert lauf.erfolgreich and lauf.weg == "amtlich"


@pytest.mark.parametrize("fehler", ["format", "groesse", "zeit", "umleitung"])
def test_antwortgrenzen_und_umleitungsverbot(gelesen, monkeypatch, fehler):
    from urllib.error import HTTPError

    class Antwort(BytesIO):
        status = 200
        headers = Message()
    antwort = Antwort(b"x"*(6*1024*1024+1) if fehler == "groesse" else b"x")
    antwort.headers["Content-Type"] = "text/html" if fehler == "format" else "application/pdf"
    if fehler == "zeit":
        zeiten = iter([0, 0, 16])
        monkeypatch.setattr(personalimport, "monotonic", lambda: next(zeiten))
    class Opener:
        def open(self, request, timeout):
            if fehler == "umleitung":
                raise HTTPError(QUELLE, 302, "Redirect", {}, None)
            return antwort
    def opener(*handler):
        assert len(handler) == 1 and isinstance(handler[0], personalimport._KeineUmleitung)
        assert handler[0].redirect_request(None, None, 302, "", {}, "https://example.org/") is None
        return Opener()
    monkeypatch.setattr(personalimport.urllib.request, "build_opener", opener)
    with pytest.raises(ValueError):
        personalimport.amtlich_importieren()
    assert not PersonalAggregat.objects.exists()
    assert not PersonalAbruf.objects.get().erfolgreich
