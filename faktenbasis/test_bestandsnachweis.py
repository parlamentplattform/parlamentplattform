import copy
import hashlib
import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import translation

from faktenbasis.bestandsnachweis import REGISTER, bestandsnachweis
from faktenbasis.models import NormText, PersonalAbruf, PersonalAggregat, PersonalRessorttabelle
from faktenbasis.test_personalimport import DATEN as PERSONAL
from faktenbasis.test_ressortimport import DATEN as RESSORTS
from faktenbasis.test_volltext import norm  # noqa: F401
from faktenbasis.test_xmltext import xml_beispiel
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from parameter.models import Parameter
from plattform_core.faktenbestand import BestandsFehler
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]


@pytest.fixture
def bestand(norm):  # noqa: F811
    raw = xml_beispiel()
    text = NormText.objects.create(norm=norm, quelle=norm.quelle, xml=raw, text="Synthetisch",
                                   xml_hash=hashlib.sha256(raw).hexdigest(), parser_fassung=2)
    personal = PersonalAggregat.objects.create(**copy.deepcopy(PERSONAL))
    ressorts = PersonalRessorttabelle.objects.create(**copy.deepcopy(RESSORTS))
    return norm, text, personal, ressorts


def grenze(wert):
    Parameter.objects.update_or_create(schluessel=REGISTER, defaults={"wert": str(wert)})


def test_vier_sammlungen_in_einem_select_mit_register_und_limit(bestand):
    grenze(4)
    with CaptureQueriesContext(connection) as anfragen:
        d = bestandsnachweis()
    assert len(anfragen) == 2
    sql = anfragen[-1]["sql"].upper()
    assert sql.count("UNION ALL") == 3 and "LIMIT 5" in sql and "ORDER BY" not in sql
    assert "XML\"" not in sql and "ROHDATEN" not in sql and "RESSORTS\"" not in sql
    assert [s["anzahl"] for s in d["inhalt"]["sammlungen"]] == [1, 1, 1, 1]
    assert [e["pruefsumme"] for e in d["inhalt"]["eintraege"]] == [
        bestand[0].inhalt_hash, bestand[1].xml_hash, bestand[2].original_sha256, bestand[3].original_sha256]
    raw = json.dumps(d["inhalt"], ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    assert hashlib.sha256(raw).hexdigest() == d["sha256"]
    assert d["hoechstzahl"] == 4


def test_abrufversuche_zeit_und_grenze_veraendern_keinen_bestand(bestand):
    vorher = bestandsnachweis()
    PersonalAbruf.objects.create(erfolgreich=False, fehlercode="synthetisch", weg="datei")
    grenze(50)
    nachher = bestandsnachweis()
    assert vorher["inhalt"] == nachher["inhalt"] and vorher["sha256"] == nachher["sha256"]
    assert nachher["erstellt_am"] != vorher["erstellt_am"]
    # Neue Parserfassung ist ein zusätzlicher Datensatz, auch bei identischer Quelldatei.
    t = bestand[1]
    NormText.objects.create(norm=t.norm, quelle=t.quelle, xml=bytes(t.xml), text=t.text,
                            xml_hash=t.xml_hash, parser_fassung=3)
    assert bestandsnachweis()["sha256"] != vorher["sha256"]


@pytest.mark.parametrize("wert", [0, -1, 10001, "kaputt", "1.5", ""])
def test_deaktivierte_oder_ungueltige_grenze_liest_keine_sammlung(wert):
    grenze(wert)
    with CaptureQueriesContext(connection) as anfragen, pytest.raises(BestandsFehler, match="grenze"):
        bestandsnachweis()
    assert len(anfragen) == 1


def test_umfang_und_unlesbarer_hash_geben_keinen_teilnachweis(bestand, client):
    grenze(3)
    with pytest.raises(BestandsFehler, match="umfang"):
        bestandsnachweis()
    for name in ("bestand", "bestand_json"):
        antwort = client.get(reverse("faktenbasis:" + name))
        assert antwort.status_code == 503 and "Teilnachweis" in antwort.content.decode()
        assert bestand[0].inhalt_hash not in antwort.content.decode()
    grenze(100)
    daten = copy.deepcopy(PERSONAL)
    daten["original_sha256"] = "kein gültiger Hash"
    PersonalAggregat.objects.create(**daten)
    with pytest.raises(BestandsFehler, match="daten"):
        bestandsnachweis()
    antwort = client.get(reverse("faktenbasis:bestand_json"))
    assert antwort.status_code == 503 and antwort.json()["fehler"] == "daten"
    assert "inhalt" not in antwort.json() and "sha256" not in antwort.json()


@pytest.mark.parametrize("rolle", ["gast", "mitglied", "admin"])
def test_oeffentliche_nachlese_ist_rein_lesend_und_download_gebunden(bestand, client, monkeypatch, rolle):
    from faktenbasis import importieren, personalimport, ressortimport, volltext
    def verboten(*args, **kwargs):
        pytest.fail("Die Bestandsnachlese darf nichts abrufen")
    for modul, name in [(importieren, "abrufen"), (volltext, "abrufen"),
                         (personalimport, "_herunterladen"), (ressortimport, "_herunterladen")]:
        monkeypatch.setattr(modul, name, verboten)
    if rolle != "gast":
        person = mitglied_anlegen()
        person.ist_admin = rolle == "admin"
        person.save(update_fields=["ist_admin"])
        client.force_login(person)
    audit = AuditEintrag.objects.count()
    digest = bestandsnachweis()["sha256"]
    url = reverse("faktenbasis:bestand_json")
    with CaptureQueriesContext(connection) as anfragen:
        seite = client.get(reverse("faktenbasis:bestand"))
        download = client.get(url, {"sha256": digest})
    assert not any(q["sql"].lstrip().upper().startswith(("INSERT", "UPDATE", "DELETE")) for q in anfragen)
    assert seite.status_code == download.status_code == 200
    html = seite.content.decode()
    assert digest in html and "?sha256=" + digest in html
    assert "keine amtliche Signatur" in html and "Original-PDFs" in html
    assert download.json()["sha256"] == digest
    assert download["Content-Disposition"].startswith("attachment;")
    assert download["X-Content-Type-Options"] == "nosniff"
    assert "no-store" in download["Cache-Control"] and "no-store" in seite["Cache-Control"]
    assert AuditEintrag.objects.count() == audit
    assert not any(f'"{fremd}":' in json.dumps(download.json()) for fremd in ("mitglied", "email", "rohdaten", "text"))
    for name in ("bestand", "bestand_json"):
        assert client.post(reverse("faktenbasis:" + name)).status_code == 405
        assert client.head(reverse("faktenbasis:" + name)).status_code == 200
    assert client.get(url, {"sha256": "a" * 64}).status_code == 409
    assert "inhalt" not in client.get(url, {"sha256": "a" * 64}).json()


@pytest.mark.parametrize("pin", ["", "A" * 64, "a" * 63, "a" * 64 + "\n", "ö" * 64])
def test_ungueltiger_downloadpin_liest_keinen_bestand(pin, client, monkeypatch):
    from faktenbasis import bestandsviews
    monkeypatch.setattr(bestandsviews, "bestandsnachweis", lambda: pytest.fail("Falscher Pin"))
    assert client.get(reverse("faktenbasis:bestand_json"), {"sha256": pin}).status_code == 400


def test_leerzustand_und_englische_nachlese_ohne_vollabfrage_im_index(client, monkeypatch):
    html = client.get(reverse("faktenbasis:bestand")).content.decode()
    assert "Der lokale Bestand ist leer" in html
    assert all(s["anzahl"] == 0 for s in client.get(reverse("faktenbasis:bestand_json")).json()["inhalt"]["sammlungen"])
    with translation.override("en"):
        html = client.get(reverse("faktenbasis:bestand"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
        assert "Evidence of the stored source inventory" in html and "No official signature" in html
    from faktenbasis import bestandsviews
    monkeypatch.setattr(bestandsviews, "bestandsnachweis", lambda: pytest.fail("Index liest keinen Nachweis"))
    assert reverse("faktenbasis:bestand") in client.get(reverse("faktenbasis:index")).content.decode()
