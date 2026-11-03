import copy

import pytest
from django.urls import reverse

from faktenbasis import ressortimport
from faktenbasis.test_ressortimport import DATEN
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from verfahren.models import AuditEintrag

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]


@pytest.fixture
def tabelle(monkeypatch):
    monkeypatch.setattr(ressortimport, "lesen", lambda raw: copy.deepcopy(DATEN))
    return ressortimport.datei_importieren(b"synthetisch").inhalt


def test_lesende_nachlese_und_export_enthalten_die_gleichen_originalwerte(tabelle, client, monkeypatch):
    monkeypatch.setattr(ressortimport, "_herunterladen", lambda: pytest.fail("Kein Netz beim GET"))
    vorher = AuditEintrag.objects.count()
    urls = [reverse("faktenbasis:personal_ressorts"), reverse("faktenbasis:personal_ressorts_detail", args=[tabelle.pk]),
        reverse("faktenbasis:personal_ressorts_nachweis", args=[tabelle.pk])]
    for url in urls:
        assert client.get(url).status_code == 200 and client.post(url).status_code == 405
    html = client.get(urls[1]).content.decode()
    assert "nicht angegeben" in html
    assert "Keine Kopfzahlen, freien Kapazitäten oder Personalprognosen" in html
    assert "Methodikseite" in html and "175" in html
    assert html.index("Sonstige oberste Organe") < html.index("Bundeskanzleramt") < html.index("Inneres")
    r = client.get(urls[2])
    d = r.json()
    assert d["ressorts"] == DATEN["ressorts"] and d["gesamt"] == DATEN["gesamt"]
    assert d["ressorts"][0]["nachgeordnet"] is None and d["stichtag"] == "2025-12-31"
    assert d["original_sha256"] == DATEN["original_sha256"] and d["parser_fassung"] == 1
    assert r["Content-Disposition"].startswith("attachment;") and r["X-Content-Type-Options"] == "nosniff"
    assert not {"pdf", "dateiname", "mitglied", "email", "kapazitaet"} & set(d)
    assert AuditEintrag.objects.count() == vorher


def test_ressortuebersicht_hat_ehrlichen_leerzustand_und_fehlender_beleg_ist_404(client):
    html = client.get(reverse("faktenbasis:personal_ressorts")).content.decode()
    assert "Noch keine amtliche Personal-Ressorttabelle übernommen" in html
    assert client.get(reverse("faktenbasis:personal_ressorts_detail", args=[999])).status_code == 404


def test_fehler_nach_beleg_loescht_keine_nachlese(tabelle, client, monkeypatch):
    def kaputt(raw):
        raise ValueError("ressort_methodik")
    monkeypatch.setattr(ressortimport, "lesen", kaputt)
    with pytest.raises(ValueError):
        ressortimport.datei_importieren(b"fremd")
    html = client.get(reverse("faktenbasis:personal_ressorts")).content.decode()
    assert "Frühere Angaben bleiben erhalten" in html and "31.12.2025" in html
    assert client.get(reverse("faktenbasis:personal_ressorts_detail", args=[tabelle.pk])).status_code == 200
