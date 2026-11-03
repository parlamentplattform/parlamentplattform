"""Kleine synthetische LrKons-Antworten; CI fragt niemals das RIS ab."""

import copy
import io
import json
from datetime import date
from email.message import Message
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.urls import reverse

from faktenbasis import landesrecht
from faktenbasis.auswahl import erfassen
from faktenbasis.importieren import importieren
from faktenbasis.kontext import QuellenkontextFehler, festhalten
from faktenbasis.models import Norm, RisImport
from faktenbasis.ris import RisFehler
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from ki.kontext import festhalten as text_festhalten
from parameter.models import Parameter
from verfahren.models import AuditEintrag, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]
NUMMER = "10000288"
STAND = date(2026, 11, 3)


def beispiel(bundesland="Oberoesterreich"):
    # Absichtlich künstliche Kennung und Titel, keine normative Aussage.
    return {"OgdSearchResult": {"OgdDocumentResults": {
        "Hits": {"#text": "147", "@pageNumber": "1", "@pageSize": "10"},
        "OgdDocumentReference": {"Data": {"Metadaten": {
            "Technisch": {"ID": "LOO00000001", "Applikation": "LrKons"},
            "Allgemein": {"DokumentUrl": "https://ogd.ris.bka.gv.at/Dokumente/Landesnormen/LOO00000001/LOO00000001.html"},
            "Landesrecht": {"Kurztitel": "Synthetisches Beispiel", "Titel": "Nur Testdaten<br/>Keine Rechtsquelle",
                "Bundesland": landesrecht.BUNDESLAENDER[bundesland],
                "LrKons": {"Gesetzesnummer": NUMMER, "Typ": "LG", "ArtikelParagraphAnlage": "§ 1"}},
        }}}}}}


@pytest.fixture
def antwort(monkeypatch):
    d = beispiel()
    monkeypatch.setattr(landesrecht, "abrufen", lambda nummer, stand, land: landesrecht.antwort_parsen(d, nummer, land))
    return d


@pytest.mark.parametrize("bundesland", list(landesrecht.BUNDESLAENDER))
def test_nur_das_ausdruecklich_gewaehlte_land_ist_zulaessig(bundesland):
    a = landesrecht.antwort_parsen(beispiel(bundesland), NUMMER, bundesland)
    n, = a.normen
    assert n.ebene == "Land" and n.bundesland == landesrecht.BUNDESLAENDER[bundesland]
    assert n.ris_id == "LOO00000001" and a.treffer == 147 and len(a.normen) == 1
    assert "<br" not in n.titel and len(n.inhalt_hash) == 64


@pytest.mark.parametrize("fehler", ["land", "app", "kennung", "fremde_nummer", "fremder_host", "anderes_dokument",
    "seite", "seitengroesse", "treffer", "doppelt", "null_mit_daten", "keine_meta", "listen_typ", "elf_dokumente"])
def test_falsche_herkunft_und_antwortform_werden_nicht_geraten(fehler):
    d = beispiel()
    e = d["OgdSearchResult"]["OgdDocumentResults"]
    m = e["OgdDocumentReference"]["Data"]["Metadaten"]
    if fehler == "land":
        m["Landesrecht"]["Bundesland"] = "Wien"
    elif fehler == "app":
        m["Technisch"]["Applikation"] = "BrKons"
    elif fehler == "kennung":
        m["Technisch"]["ID"] = "NOR00000001"
    elif fehler == "fremde_nummer":
        m["Landesrecht"]["LrKons"]["Gesetzesnummer"] = "99999999"
    elif fehler == "fremder_host":
        m["Allgemein"]["DokumentUrl"] = "https://example.org/LOO00000001"
    elif fehler == "anderes_dokument":
        m["Allgemein"]["DokumentUrl"] = "https://ris.bka.gv.at/LOO00000002"
    elif fehler == "seite":
        e["Hits"]["@pageNumber"] = "2"
    elif fehler == "seitengroesse":
        e["Hits"]["@pageSize"] = "100"
    elif fehler == "treffer":
        e["Hits"]["#text"] = "-1"
    elif fehler == "doppelt":
        e["OgdDocumentReference"] = [e["OgdDocumentReference"], copy.deepcopy(e["OgdDocumentReference"])]
    elif fehler == "null_mit_daten":
        e["Hits"]["#text"] = "0"
    elif fehler == "keine_meta":
        e["OgdDocumentReference"] = {"Data": []}
    elif fehler == "listen_typ":
        e["OgdDocumentReference"] = "keine Liste"
    else:
        e["OgdDocumentReference"] = [copy.deepcopy(e["OgdDocumentReference"]) for _ in range(11)]
    with pytest.raises(RisFehler):
        landesrecht.antwort_parsen(d, NUMMER, "Oberoesterreich")


@pytest.mark.parametrize("leer", [None, [], {"@xsi:nil": "true"}])
def test_leere_treffer_bleiben_leer(leer):
    d = beispiel()
    e = d["OgdSearchResult"]["OgdDocumentResults"]
    e.update(Hits={"#text": "0", "@pageNumber": "1", "@pageSize": "10"}, OgdDocumentReference=leer)
    assert landesrecht.antwort_parsen(d, NUMMER, "Oberoesterreich").normen == ()


@pytest.mark.parametrize("bundesland", list(landesrecht.BUNDESLAENDER))
def test_feste_adresse_erste_seite_genau_ein_bundesland(monkeypatch, bundesland):
    class Antwort(io.BytesIO):
        status = 200
        headers = Message()
    antwort = Antwort(json.dumps(beispiel(bundesland)).encode())
    antwort.headers["Content-Type"] = "application/json"

    class Opener:
        def open(self, request, timeout):
            url = urlsplit(request.full_url)
            q = parse_qs(url.query)
            assert url.scheme == "https" and url.netloc == "data.bka.gv.at" and url.path.endswith("/Landesrecht")
            assert [k for k in q if k.startswith("Bundesland.")] == [f"Bundesland.SucheIn{bundesland}"]
            assert q[f"Bundesland.SucheIn{bundesland}"] == ["true"]
            assert q["Gesetzesnummer"] == [NUMMER] and q["Fassung.FassungVom"] == [STAND.isoformat()]
            assert q["Applikation"] == ["LrKons"] and q["Seitennummer"] == ["1"] and q["DokumenteProSeite"] == ["Ten"]
            assert timeout == 15
            return antwort

    monkeypatch.setattr(landesrecht.urllib.request, "build_opener", lambda *a: Opener())
    a = landesrecht.abrufen(NUMMER, STAND, bundesland)
    assert a.api_url and a.normen[0].bundesland == landesrecht.BUNDESLAENDER[bundesland]


@pytest.mark.parametrize("nummer,stand,land", [("1", STAND, "Wien"), (NUMMER, "2026-11-03", "Wien"),
    (NUMMER, STAND, ""), (NUMMER, STAND, "Austria"), (NUMMER, STAND, None)])
def test_unzulaessige_auswahl_verbraucht_keinen_abruf(monkeypatch, nummer, stand, land):
    monkeypatch.setattr(landesrecht.urllib.request, "build_opener", lambda *a: pytest.fail("Kein Netz für falsche Auswahl"))
    with pytest.raises(RisFehler):
        landesrecht.abrufen(nummer, stand, land)


def test_wiederholung_haelt_herkunft_und_erstes_original_fest(antwort):
    eins = importieren(NUMMER, STAND, bundesland="Oberoesterreich")
    norm = Norm.objects.get()
    original = copy.deepcopy(norm.rohdaten)
    zwei = importieren(NUMMER, STAND, bundesland="Oberoesterreich")
    norm.refresh_from_db()
    assert eins.neu == 1 and zwei.neu == 0 and Norm.objects.count() == 1
    assert norm.importlauf_id == eins.pk and norm.rohdaten == original
    assert norm.ebene == eins.ebene == zwei.ebene == "Land"
    assert norm.bundesland == eins.bundesland == zwei.bundesland == "Oberösterreich"


def test_fehler_haelt_das_angeforderte_land_fest_ohne_alte_daten_zu_aendern(antwort):
    eins = importieren(NUMMER, STAND, bundesland="Oberoesterreich")
    antwort["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"]["Data"]["Metadaten"]["Landesrecht"]["Bundesland"] = "Wien"
    with pytest.raises(RisFehler, match="kennung"):
        importieren(NUMMER, STAND, bundesland="Oberoesterreich")
    fehler = RisImport.objects.first()
    assert not fehler.erfolgreich and fehler.ebene == "Land" and fehler.bundesland == "Oberösterreich"
    assert Norm.objects.get().importlauf_id == eins.pk


def test_gemeinsames_kontingent_sperrt_auch_landesabrufe(monkeypatch):
    Parameter.objects.create(schluessel="faktenbasis-manuelle-abrufe-je-stunde", wert="0", beschreibung="Test", quelle="Test")
    monkeypatch.setattr(landesrecht, "abrufen", lambda *a: pytest.fail("Gemeinsame Sperre darf nicht umgangen werden"))
    with pytest.raises(RisFehler, match="abruf_kontingent"):
        importieren(NUMMER, STAND, bundesland="Oberoesterreich")
    assert not RisImport.objects.exists()


def test_nachlese_und_originalexport_bleiben_lesend(antwort, client, monkeypatch):
    lauf = importieren(NUMMER, STAND, bundesland="Oberoesterreich")
    n = Norm.objects.get()
    vorher = AuditEintrag.objects.count()
    monkeypatch.setattr(landesrecht, "abrufen", lambda *a: pytest.fail("Keine Netzabfrage bei der Nachlese"))
    for url in [reverse("faktenbasis:index"), reverse("faktenbasis:norm", args=[n.pk])]:
        html = client.get(url).content.decode()
        assert "Landesrecht" in html and "Oberösterreich" in html
        assert client.post(url).status_code == 405
    html = client.get(reverse("faktenbasis:norm", args=[n.pk])).content.decode()
    assert "1 von 147" in html and "noch nicht in Modellaufträge" in html
    assert "Diesen Dokumenttext einmal abrufen" not in html
    assert client.get(reverse("faktenbasis:importantwort", args=[lauf.pk])).json() == antwort
    assert AuditEintrag.objects.count() == vorher


def test_land_wird_nicht_stillschweigend_zum_bundes_modellkontext(antwort, ordnung):  # noqa: F811
    from faktenbasis.volltext import importieren as volltext

    importieren(NUMMER, STAND, bundesland="Oberoesterreich")
    n = Norm.objects.get()
    a = antrag_einbringen(mitglied_anlegen("landkontext"), **ANTRAG, ordnung=ordnung)
    k = text_festhalten(a)
    assert erfassen(k)["quellen"] == []
    neu = festhalten([n.pk], hoechstzahl=3, textzeichen=100, text_sha256=k["sha256"])
    assert neu["version"] == 2 and neu["quellen"][0]["ebene"] == "Land"
    with pytest.raises(QuellenkontextFehler):
        festhalten([n.pk], hoechstzahl=3, textzeichen=100, text_sha256=k["sha256"], fassung=1)
    with pytest.raises(RisFehler, match="volltextquelle"):
        volltext(n)


def test_cli_erfordert_exakte_auswahl_und_nennt_teilmenge(antwort):
    ausgabe = io.StringIO()
    call_command("landesrecht_import", "--bundesland", "Oberoesterreich", "--gesetzesnummer", NUMMER,
        "--stand", STAND.isoformat(), stdout=ausgabe)
    assert "1 von 147" in ausgabe.getvalue()
    assert Norm.objects.get().ebene == "Land"
    with pytest.raises(CommandError):
        call_command("landesrecht_import", "--bundesland", "Wien", "--gesetzesnummer", "bad",
            "--stand", STAND.isoformat())
    with pytest.raises(CommandError):
        call_command("landesrecht_import", "--bundesland", "Wien", "--gesetzesnummer", NUMMER, "--stand", "2026-1-1")


@pytest.mark.django_db(transaction=True)
def test_additive_migration_laesst_bundes_original_und_zeitpunkte_unveraendert():
    from django.db import connection
    from django.db.migrations.executor import MigrationExecutor
    from django.utils import timezone

    executor = MigrationExecutor(connection)
    vorher = [("faktenbasis", "0004_personalaggregate")]
    nachher = executor.loader.graph.leaf_nodes()
    try:
        executor.migrate(vorher)
        apps = executor.loader.project_state(vorher).apps
        AltImport, AltNorm = apps.get_model("faktenbasis", "RisImport"), apps.get_model("faktenbasis", "Norm")
        zeit = timezone.now()
        lauf = AltImport.objects.create(gesetzesnummer=NUMMER, stand=STAND, erfolgreich=True,
            begonnen_am=zeit, beendet_am=zeit, antwort={"unveraendert": "amtlicher Altstand"}, antwort_hash="a"*64)
        n = AltNorm.objects.create(ris_id="NOR00000001", gesetzesnummer=NUMMER, kurztitel="Alter Bundesstand",
            stand=STAND, quelle="https://ris.bka.gv.at/NOR00000001", rohdaten={"alt": 1},
            inhalt_hash="b"*64, importlauf=lauf)
        alte_norm = AltNorm.objects.filter(pk=n.pk).values().get()
        alter_import = AltImport.objects.filter(pk=lauf.pk).values().get()
        MigrationExecutor(connection).migrate(nachher)
        neue_norm = Norm.objects.filter(pk=n.pk).values().get()
        neuer_import = RisImport.objects.filter(pk=lauf.pk).values().get()
        assert all(neue_norm[k] == v for k, v in alte_norm.items())
        assert all(neuer_import[k] == v for k, v in alter_import.items())
        assert neue_norm["ebene"] == neuer_import["ebene"] == "Bund"
        assert neue_norm["bundesland"] == neuer_import["bundesland"] == ""
    finally:
        MigrationExecutor(connection).migrate(nachher)
