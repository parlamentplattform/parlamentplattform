"""Gezielte Folgeseiten ohne echte Quellenabrufe oder automatische Folgeschritte."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

import copy
import json
from io import StringIO
from unittest.mock import Mock
from urllib.parse import parse_qs, urlsplit

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.urls import reverse

from faktenbasis import importieren, landesrecht, ris
from faktenbasis.models import AbrufSperre, Norm, RisImport
from faktenbasis.test_landesrecht import NUMMER as LANDNUMMER
from faktenbasis.test_landesrecht import beispiel as landbeispiel
from faktenbasis.test_ris import NUMMER, STAND, Scheinantwort, beispiel
from faktenbasis.test_verwaltung import admin
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from ki.test_kontext import antrag  # noqa: F401
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import ordnung  # noqa: F401


def daten(art, seite=2, treffer=11):
    d = landbeispiel() if art == "Land" else beispiel()
    e = d["OgdSearchResult"]["OgdDocumentResults"]
    e["Hits"].update({"@pageNumber": str(seite), "#text": str(treffer)})
    return d


def parsen(art, d, seite=2):
    if art == "Land":
        return landesrecht.antwort_parsen(d, LANDNUMMER, "Oberoesterreich", seite=seite)
    return ris.antwort_parsen(d, NUMMER, seite=seite)


@pytest.mark.parametrize("art", ["Bund", "Land"])
def test_ausdrueckliche_letzte_folgeseite_bleibt_mit_rohantwort_gebunden(art):
    d = daten(art)
    a = parsen(art, d)
    assert a.seite == 2 and a.treffer == 11 and len(a.normen) == 1
    assert a.rohdaten == d and a.antwort_hash == ris._hash(d)
    assert a.normen[0].ebene == art


@pytest.mark.parametrize("art", ["Bund", "Land"])
@pytest.mark.parametrize("seite", [0, -1, True, False, 1.0, "2", None, 2147483648])
def test_ungueltige_seite_wird_vor_dem_netz_abgewiesen(monkeypatch, art, seite):
    netz = Mock(side_effect=AssertionError("Kein Netz bei ungültiger Seitennummer"))
    monkeypatch.setattr(ris.urllib.request, "build_opener", netz)
    with pytest.raises(ris.RisFehler, match="^seite$"):
        if art == "Land":
            landesrecht.abrufen(LANDNUMMER, STAND, "Oberoesterreich", seite=seite)
        else:
            ris.abrufen(NUMMER, STAND, seite=seite)
    netz.assert_not_called()


@pytest.mark.parametrize("art", ["Bund", "Land"])
@pytest.mark.parametrize("feld,wert", [("@pageNumber", "1"), ("@pageNumber", "3"),
                                      ("@pageNumber", True), ("@pageSize", "20"),
                                      ("#text", True), ("#text", 11.5), ("#text", "elf")])
def test_server_darf_nicht_andere_seite_oder_groesse_unterschieben(art, feld, wert):
    d = daten(art)
    d["OgdSearchResult"]["OgdDocumentResults"]["Hits"][feld] = wert
    with pytest.raises(ris.RisFehler, match="antwortformat"):
        parsen(art, d)


@pytest.mark.parametrize("art", ["Bund", "Land"])
@pytest.mark.parametrize("treffer", [0, 1, 10])
def test_seite_hinter_trefferende_ist_keine_erfolgreiche_leere_quelle(art, treffer):
    d = daten(art, treffer=treffer)
    d["OgdSearchResult"]["OgdDocumentResults"]["OgdDocumentReference"] = []
    with pytest.raises(ris.RisFehler, match="seite_ausserhalb"):
        parsen(art, d)


@pytest.mark.parametrize("art", ["Bund", "Land"])
def test_letzte_seite_darf_nicht_mehr_als_die_resttreffer_enthalten(art):
    d = daten(art)
    e = d["OgdSearchResult"]["OgdDocumentResults"]
    e["OgdDocumentReference"] = [e["OgdDocumentReference"]] * 2
    with pytest.raises(ris.RisFehler, match="antwortformat"):
        parsen(art, d)


@pytest.mark.parametrize("art", ["Bund", "Land"])
def test_eine_gewaehlte_seite_bedeutet_genau_eine_begrenzte_anfrage(monkeypatch, art):
    opener = Mock()
    def holen(*args, **kwargs):
        a = Scheinantwort(json.dumps(daten(art)).encode())
        a.status = 200
        return a
    opener.open.side_effect = holen
    monkeypatch.setattr(ris.urllib.request, "build_opener", Mock(return_value=opener))
    if art == "Land":
        a = landesrecht.abrufen(LANDNUMMER, STAND, "Oberoesterreich", seite=2)
    else:
        a = ris.abrufen(NUMMER, STAND, seite=2)
    request = opener.open.call_args.args[0]
    query = parse_qs(urlsplit(request.full_url).query)
    assert query["Seitennummer"] == ["2"] and query["DokumenteProSeite"] == ["Ten"]
    assert query["Fassung.FassungVom"] == [STAND.isoformat()]
    assert a.api_url == request.full_url and a.seite == 2
    assert opener.open.call_count == 1 and opener.open.call_args.kwargs == {"timeout": 15}


@pytest.mark.django_db
@pytest.mark.usefixtures("abrufuhr")
@pytest.mark.parametrize("art", ["Bund", "Land"])
def test_einzelimport_haelt_seite_audit_und_wiederholten_altinhalt_fest(monkeypatch, art, client):
    nummer = LANDNUMMER if art == "Land" else NUMMER
    auswahl = {"bundesland": "Oberoesterreich"} if art == "Land" else {}
    modul = landesrecht if art == "Land" else importieren
    raw = daten(art)
    calls = []
    def holen(*args, **kwargs):
        calls.append((args, kwargs))
        return parsen(art, raw, kwargs.get("seite", 1))
    monkeypatch.setattr(modul, "abrufen", holen)
    erster = importieren.importieren(nummer, STAND, seite=2, **auswahl)
    vorher = list(Norm.objects.values())
    zweiter = importieren.importieren(nummer, STAND, seite=2, **auswahl)
    assert erster.seite == zweiter.seite == 2 and erster.neu == 1 and zweiter.neu == 0
    assert list(Norm.objects.values()) == vorher and len(calls) == 2
    assert all(k == {"seite": 2} for _, k in calls)
    assert AuditEintrag.objects.last().ereignis["seite"] == 2
    assert RisImport.objects.get(pk=erster.pk).antwort_hash == ris._hash(raw)
    page = client.get(reverse("faktenbasis:norm", args=[vorher[0]["id"]])).content.decode()
    assert "RIS-Seite: 2" in page


@pytest.mark.django_db
@pytest.mark.usefixtures("abrufuhr")
@pytest.mark.parametrize("art", ["Bund", "Land"])
def test_zehn_dokumente_dann_das_elfte_ergaenzen_ohne_alte_staende_anzufassen(monkeypatch, art):
    nummer = LANDNUMMER if art == "Land" else NUMMER
    auswahl = {"bundesland": "Oberoesterreich"} if art == "Land" else {}
    modul = landesrecht if art == "Land" else importieren
    seiten = {}
    for seite, bereich in ((1, range(1, 11)), (2, range(11, 12))):
        raw = daten(art, seite=seite)
        ergebnis = raw["OgdSearchResult"]["OgdDocumentResults"]
        vorbild = ergebnis["OgdDocumentReference"]
        referenzen = []
        for i in bereich:
            referenz = copy.deepcopy(vorbild)
            meta = referenz["Data"]["Metadaten"]
            alt = meta["Technisch"]["ID"]
            neu = ("LOO" if art == "Land" else "NOR") + f"{i:08d}"
            meta["Technisch"]["ID"] = neu
            meta["Allgemein"]["DokumentUrl"] = meta["Allgemein"]["DokumentUrl"].replace(alt, neu)
            referenzen.append(referenz)
        ergebnis["OgdDocumentReference"] = referenzen
        seiten[seite] = raw
    calls = []
    def holen(*args, **kwargs):
        seite = kwargs.get("seite", 1)
        calls.append(seite)
        return parsen(art, seiten[seite], seite)
    monkeypatch.setattr(modul, "abrufen", holen)
    erster = importieren.importieren(nummer, STAND, **auswahl)
    normen_vorher = list(Norm.objects.order_by("pk").values())
    import_vorher = RisImport.objects.filter(pk=erster.pk).values().get()
    audit_vorher = list(AuditEintrag.objects.order_by("pk").values())
    assert erster.gelesen == erster.neu == 10 and calls == [1]
    zweiter = importieren.importieren(nummer, STAND, seite=2, **auswahl)
    assert calls == [1, 2] and zweiter.gelesen == zweiter.neu == 1
    assert Norm.objects.count() == 11 and RisImport.objects.count() == 2
    assert list(Norm.objects.order_by("pk").values())[:10] == normen_vorher
    assert RisImport.objects.filter(pk=erster.pk).values().get() == import_vorher
    assert list(AuditEintrag.objects.order_by("pk").values())[:-1] == audit_vorher
    assert zweiter.antwort == seiten[2] and zweiter.antwort_hash == ris._hash(seiten[2])


@pytest.mark.django_db
@pytest.mark.usefixtures("abrufuhr")
def test_falsche_antwortseite_bleibt_als_fehler_ohne_uebernommene_norm(monkeypatch):
    monkeypatch.setattr(importieren, "abrufen", lambda *a, **k: ris.antwort_parsen(beispiel(), NUMMER))
    with pytest.raises(ris.RisFehler, match="antwortformat"):
        importieren.importieren(NUMMER, STAND, seite=2)
    lauf = RisImport.objects.get()
    assert lauf.seite == 2 and not lauf.erfolgreich and lauf.fehlercode == "antwortformat"
    assert not Norm.objects.exists() and AuditEintrag.objects.get().ereignis["seite"] == 2


@pytest.mark.django_db
@pytest.mark.parametrize("seite", [0, -1, True, "2", 2147483648])
def test_ungueltiger_importparameter_verbraucht_keinen_abrufplatz(seite):
    with pytest.raises(ris.RisFehler, match="^seite$"):
        importieren.importieren(NUMMER, STAND, seite=seite)
    assert not AbrufSperre.objects.exists() and not RisImport.objects.exists() and not AuditEintrag.objects.exists()


@pytest.mark.django_db
@pytest.mark.usefixtures("abrufuhr")
@pytest.mark.parametrize("art", ["Bund", "Land"])
def test_beide_cli_wege_uebernehmen_nur_die_angegebene_folgeseite(monkeypatch, art):
    modul = landesrecht if art == "Land" else importieren
    monkeypatch.setattr(modul, "abrufen", lambda *a, **k: parsen(art, daten(art), k["seite"]))
    args = {"bundesland": "Oberoesterreich"} if art == "Land" else {}
    ausgabe = StringIO()
    call_command("landesrecht_import" if art == "Land" else "ris_import",
                 gesetzesnummer=LANDNUMMER if art == "Land" else NUMMER,
                 stand=STAND.isoformat(), seite=2, stdout=ausgabe, **args)
    assert RisImport.objects.get().seite == 2 and "RIS-Seite 2" in ausgabe.getvalue()
    with pytest.raises(CommandError, match="seite"):
        call_command("landesrecht_import" if art == "Land" else "ris_import",
                     gesetzesnummer=LANDNUMMER if art == "Land" else NUMMER,
                     stand=STAND.isoformat(), seite=0, stdout=ausgabe, **args)
    assert RisImport.objects.count() == 1


@pytest.mark.django_db
@pytest.mark.usefixtures("abrufuhr")
def test_web_seitenwahl_ist_explizit_get_und_formfehler_bleiben_lesend(monkeypatch, client):
    admin(client)
    calls = []
    def holen(*args, **kwargs):
        calls.append(kwargs)
        return ris.antwort_parsen(daten("Bund"), NUMMER, seite=kwargs["seite"])
    monkeypatch.setattr(importieren, "abrufen", holen)
    url = reverse("faktenbasis:verwaltung")
    assert client.get(url, {"seite": 2}).status_code == 200 and not calls
    for seite in (0, -1, "abc", 2147483648):
        r = client.post(url, {"gesetzesnummer": NUMMER, "stand": STAND.isoformat(), "seite": seite})
        assert r.status_code == 200 and r.context["formular"].errors and not calls
    assert not AuditEintrag.objects.exists() and not AbrufSperre.objects.exists()
    r = client.post(url, {"gesetzesnummer": NUMMER, "stand": STAND.isoformat(), "seite": 2})
    assert r.status_code == 302 and calls == [{"seite": 2}]
    assert RisImport.objects.get().seite == 2 and AuditEintrag.objects.last().ereignis["seite"] == 2


@pytest.mark.django_db
@pytest.mark.usefixtures("abrufuhr")
def test_folgeseite_aendert_keine_festgehaltene_modelleingabe_oder_policy(antrag, monkeypatch):
    from ki.folgenauftraege import einreihen

    job = einreihen(antrag, antrag.eingebracht_von, hoechstzeichen=50000)
    vorher = copy.deepcopy((job.kontext, job.quellenkontext, job.folgenkontext, antrag.policy_snapshot))
    assert not job.quellenkontext["quellen"]
    monkeypatch.setattr(importieren, "abrufen", lambda *a, **k: parsen("Bund", daten("Bund"), k["seite"]))
    importieren.importieren(NUMMER, STAND, seite=2)
    assert Norm.objects.exists()
    job.refresh_from_db()
    antrag.refresh_from_db()
    assert (job.kontext, job.quellenkontext, job.folgenkontext, antrag.policy_snapshot) == vorher


@pytest.mark.django_db(transaction=True)
def test_migration_haelt_alte_importe_bis_auf_additive_seite_eins_bytegleich():
    executor = MigrationExecutor(connection)
    aktuell = executor.loader.graph.leaf_nodes()
    alt = ("faktenbasis", "0006_personalressorts")
    try:
        executor.migrate([alt])
        apps = executor.loader.project_state([alt]).apps
        modell = apps.get_model("faktenbasis", "RisImport")
        obj = modell.objects.create(gesetzesnummer=NUMMER, stand=STAND, erfolgreich=False,
                                   fehlercode="alter_testfehler", antwort={"alt": "äöü"})
        vorher = copy.deepcopy(modell.objects.get(pk=obj.pk).__dict__)
        vorher.pop("_state")
        executor = MigrationExecutor(connection)
        executor.migrate(aktuell)
        neu = executor.loader.project_state(aktuell).apps.get_model("faktenbasis", "RisImport")
        nachher = neu.objects.get(pk=obj.pk).__dict__
        nachher.pop("_state")
        assert nachher.pop("seite") == 1 and nachher == vorher
    finally:
        MigrationExecutor(connection).migrate(aktuell)
