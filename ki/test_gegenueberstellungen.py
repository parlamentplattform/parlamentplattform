"""Expliziter Privatvergleich: Inputbindung, Budget, Doppel-POST und Fehler ohne Zwang."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

import json
from types import SimpleNamespace

import pytest
from django.test import Client
from django.urls import reverse

from ki.anbieter import AnbieterFehler, Antwort, AttrappenAnbieter, MistralAnbieter
from ki.gegenueberstellungen import anfordern, auswertung
from ki.models import KILauf, SteckplatzZugang, Vergleichsanfrage, Zweck
from ki.test_vergleichskontext import lage  # noqa: F401
from ki.vergleichsanfragen import anbieten
from mitglieder.models import Identitaetsstufe, Mitgliedsstatus
from parameter.models import Parameter
from verfahren.models import Antrag, Unterstuetzung, antrag_einbringen
from verfahren.test_einbringen_aehnlichkeit import UMFORMULIERT
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def modell(monkeypatch, settings):
    settings.DDOE_KI_ANBIETER = "attrappe"
    aufrufe = []

    def antwort(self, auftrag, text, zeitgrenze=None):
        d = json.loads(text)
        aufrufe.append((auftrag, d, zeitgrenze))
        return Antwort(json.dumps({"vergleiche": [
            {"antrag": p["antrag"], "fassung": p["fassung"], "gemeinsamkeit": "Beide nennen denselben Gegenstand.",
             "unterschied": "Die Wortlaute unterscheiden sich im Umfang."} for p in d["gegenueber"]
        ]}), "testvergleich-1", 10, 8)

    monkeypatch.setattr(AttrappenAnbieter, "frage", antwort)
    return aufrufe


def anfrage(lage):
    d, m, _, stand = lage
    token = anbieten(d, m, stand)
    return d, m, stand, token


def test_ausdrueckliche_anforderung_allein_startet_exakten_privaten_lauf(lage, modell):
    a = anfordern(*anfrage(lage))
    lauf = a.lauf
    assert a.status == "fertig" and len(modell) == 1
    assert lauf.zweck == Zweck.GEGENUEBERSTELLUNG and lauf.antrag_id is None
    assert lauf.auftrag_version == "gegenueberstellung-v1" and lauf.kontext["vergleich"] == a.kontext
    assert json.loads(lauf.eingabe) == modell[0][1] and modell[0][2] == 8
    assert auswertung(a, lage[1])["gueltig"]
    assert auswertung(a, lage[1])["inhaltlich_geprueft"] is False
    assert Antrag.objects.count() == 1 and not Unterstuetzung.objects.exists()


def test_doppelpost_verbraucht_keinen_zweiten_anbieteraufruf(lage, modell):
    args = anfrage(lage)
    a, b = anfordern(*args), anfordern(*args)
    assert a.pk == b.pk and len(modell) == 1 and KILauf.objects.count() == 1


@pytest.mark.parametrize("sperre", ["belegt", "monat", "anbieter", "stunde"])
def test_betriebsgrenzen_starten_keinen_anbieter_und_wiederholen_nicht(lage, modell, settings, sperre):
    if sperre == "belegt":
        SteckplatzZugang.objects.update_or_create(name="anbieter", defaults={"belegt": True})
    elif sperre == "monat":
        Parameter.objects.create(schluessel="ki-monatstokens", wert="0")
    elif sperre == "anbieter":
        settings.DDOE_KI_ANBIETER, settings.DDOE_KI_SCHLUESSEL = "mistral", ""
    else:
        Parameter.objects.create(schluessel="gegenueberstellung-je-stunde", wert="0")
    args = anfrage(lage)
    a = anfordern(*args)
    assert a.status == "ohne_ergebnis" and not auswertung(a, lage[1])["gueltig"]
    assert anfordern(*args).pk == a.pk
    assert not modell and not KILauf.objects.exists()


def test_neue_anfragen_zaehlen_eigenes_stundenlimit_doppelte_nicht(lage, modell, monkeypatch):
    monkeypatch.setattr("mitglieder.botschutz.time", SimpleNamespace(time=lambda: 1800000000))
    Parameter.objects.create(schluessel="gegenueberstellung-je-stunde", wert="1")
    args = anfrage(lage)
    anfordern(*args)
    anfordern(*args)
    a = anfordern(*anfrage(lage))
    assert a.meldung == "stundengrenze" and len(modell) == 1


def test_neue_stunde_oeffnet_kontingent_aber_beginnt_alte_kennung_nicht_neu(lage, modell, monkeypatch):
    stunde = [1800000000]
    monkeypatch.setattr("mitglieder.botschutz.time", SimpleNamespace(time=lambda: stunde[0]))
    Parameter.objects.create(schluessel="gegenueberstellung-je-stunde", wert="1")
    args = anfrage(lage)
    anfordern(*args)
    stunde[0] += 3600
    anfordern(*args)
    assert len(modell) == 1
    anfordern(*anfrage(lage))
    assert len(modell) == 2


def test_zeitgrenze_kommt_aus_dem_register(lage, modell):
    Parameter.objects.create(schluessel="gegenueberstellung-zeitgrenze-sekunden", wert="3")
    anfordern(*anfrage(lage))
    assert modell[0][2] == 3


def test_chat_transport_erhaelt_eigene_zeitgrenze_ohne_alte_aufrufe_umzudeuten(monkeypatch):
    anbieter, aufrufe = MistralAnbieter("synthetisch", "test"), []
    def senden(endpunkt, daten, **kwargs):
        aufrufe.append(kwargs)
        return {"choices": [{"message": {"content": "Antwort"}}], "usage": {}}
    monkeypatch.setattr(anbieter, "_senden", senden)
    anbieter.frage("Testauftrag", "Daten", zeitgrenze=3)
    anbieter.frage("Alter Aufruf", "Daten")
    assert aufrufe == [{"zeitgrenze": 3}, {}]


def test_zu_langer_text_startet_keinen_lauf_und_speichert_keinen_teilentwurf(lage, modell):
    Parameter.objects.create(schluessel="gegenueberstellung-textzeichen", wert="1")
    with pytest.raises(ValueError, match="zu lang"):
        anfordern(*anfrage(lage))
    assert not modell and not Vergleichsanfrage.objects.exists() and not KILauf.objects.exists()


def test_eigener_export_zeigt_tatsaechliche_antwort_und_kennzeichnet_modell(lage, modell, client):
    a = anfordern(*anfrage(lage))
    client.force_login(lage[1])
    d = client.get(reverse("mitglieder:profil_export")).json()["private_textvergleiche"][0]
    assert d["laufnachweis"]["antwort"] == a.lauf.antwort
    assert d["laufnachweis"]["auftrag_version"] == "gegenueberstellung-v1"
    assert d["laufnachweis"]["modell"] == "testvergleich-1"


def test_anbieterfehler_bleibt_archiviert_und_beginnt_beim_doppelpost_nicht_neu(lage, modell, monkeypatch):
    def fehler(*args, **kwargs):
        raise AnbieterFehler("Synthetischer Ausfall")
    monkeypatch.setattr(AttrappenAnbieter, "frage", fehler)
    args = anfrage(lage)
    a = anfordern(*args)
    assert a.status == "ohne_ergebnis" and a.lauf is not None and not a.lauf.erfolgreich
    assert anfordern(*args).lauf_id == a.lauf_id and KILauf.objects.count() == 1
    assert not SteckplatzZugang.objects.get(name="anbieter").belegt


def test_unerwarteter_fehler_veroeffentlicht_keine_texte_oder_ausnahme(lage, modell, monkeypatch, caplog):
    def fehler(*args, **kwargs):
        raise RuntimeError("Private Details dürfen nicht im Fehlertext erscheinen")
    monkeypatch.setattr(AttrappenAnbieter, "frage", fehler)
    args = anfrage(lage)
    a = anfordern(*args)
    assert a.status == "ohne_ergebnis" and a.meldung == "technik"
    assert "Private Details" not in caplog.text
    assert anfordern(*args).pk == a.pk and not KILauf.objects.exists()


def test_falsche_modelldaten_zeigen_keinen_teilvergleich(lage, modell, monkeypatch):
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *a, **k: Antwort(
        '{"vergleiche":[{"antrag":99999,"fassung":1,"gemeinsamkeit":"Falsch.","unterschied":"Falsch."}]}', "falsch", 1, 2))
    a = anfordern(*anfrage(lage))
    d = auswertung(a, lage[1])
    assert not d["gueltig"] and not d["vergleiche"] and d["meldung"] == "antwortform"


def test_fremde_laufbeziehung_wird_nicht_als_eigener_vergleich_verwendet(lage, modell):
    a = anfordern(*anfrage(lage))
    fremd = KILauf.objects.create(zweck=Zweck.GEGENUEBERSTELLUNG, angefordert_von=lage[1],
                                  eingabe="Fremder Text", antwort=a.lauf.antwort, anbieter="test", modell="fremd")
    Vergleichsanfrage.objects.filter(pk=a.pk).update(lauf=fremd)
    a.refresh_from_db()
    assert auswertung(a, lage[1])["meldung"] == "eingabebindung"
    with pytest.raises(ValueError):
        auswertung(a, mitglied_anlegen("fremder_betrachter"))


def test_private_laeufe_und_fehlertexte_nicht_in_oeffentlicher_werkstatt(lage, modell, monkeypatch, client):
    anfordern(*anfrage(lage))
    def fehler(*args, **kwargs):
        raise AnbieterFehler("privater-geheimer-fehlertext")
    monkeypatch.setattr(AttrappenAnbieter, "frage", fehler)
    anfordern(*anfrage(lage))
    client.logout()
    r = client.get(reverse("verfahren:zukunftswerkstatt"))
    assert r.status_code == 200 and r.context["letzte_laeufe"] == []
    text = r.content.decode()
    assert "privater-geheimer-fehlertext" not in text and "testvergleich-1" not in text
    assert lage[0]["wortlaut"] not in text


@pytest.fixture
def web_lage(client, ordnung):
    a = antrag_einbringen(mitglied_anlegen("autorin"), ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)
    m = mitglied_anlegen("einbringender")
    client.force_login(m)
    # Angebot ausschließlich lokal erstellen, auch wenn der Chat-Anbieter angeschlossen ist.
    angebot = client.post(reverse("verfahren:einbringen"), UMFORMULIERT)
    assert angebot.status_code == 200
    return a, m, angebot


def webpost(client, angebot, **extra):
    return client.post(reverse("verfahren:einbringen"), {
        **UMFORMULIERT, "pruefstand": angebot.context["pruefstand"],
        "textvergleich": angebot.context["gegenueberstellung_token"], **extra,
    })


def test_http_kein_chat_bei_get_oder_vorschau_nur_ausdruecklicher_post(client, web_lage, modell):
    _, _, angebot = web_lage
    assert not modell
    client.get(reverse("verfahren:einbringen"))
    client.post(reverse("verfahren:einbringen_vorschau"), UMFORMULIERT)
    assert not modell
    r = webpost(client, angebot)
    assert r.status_code == 200 and len(modell) == 1
    assert r.context["gegenueberstellung"]["gueltig"]
    assert r.context["form"]["wortlaut"].value() == UMFORMULIERT["wortlaut"]
    assert "Mein Antrag ist etwas anderes" in r.content.decode() and "Diesen unterstützen" in r.content.decode()
    webpost(client, angebot)
    assert len(modell) == 1 and Antrag.objects.count() == 1


@pytest.mark.parametrize("wechsel", ["text", "titel", "fremdkonto", "ungeprueft", "pausiert", "gast"])
def test_http_wechsel_oder_rechtesperre_startet_keinen_chat(client, web_lage, modell, wechsel):
    a, m, angebot = web_lage
    extra = {}
    if wechsel == "text":
        extra["wortlaut"] = "Geänderter eigener Wortlaut"
    elif wechsel == "titel":
        a.titel = "Anderer öffentlicher Titel"
        a.save(update_fields=["titel"])
    elif wechsel == "fremdkonto":
        client.force_login(mitglied_anlegen("fremdes_formular"))
    elif wechsel == "gast":
        client.logout()
    else:
        if wechsel == "ungeprueft":
            m.identitaetsstufe = Identitaetsstufe.UNGEPRUEFT
        else:
            m.status = Mitgliedsstatus.PAUSIERT
        m.save()
    r = webpost(client, angebot, **extra)
    assert r.status_code in (200, 302, 403) and not modell and not Vergleichsanfrage.objects.exists()


def test_http_csrf_bleibt_erforderlich(client, web_lage, modell):
    _, m, angebot = web_lage
    c = Client(enforce_csrf_checks=True)
    c.force_login(m)
    assert webpost(c, angebot).status_code == 403 and not modell


def test_sqlite_schreibkonflikt_behaelt_formular_und_wahl_ohne_zweiten_start(client, web_lage, modell, monkeypatch):
    import sqlite3

    from django.db import OperationalError

    ursprung = sqlite3.OperationalError("synthetischer Schreibkonflikt")
    ursprung.sqlite_errorcode = sqlite3.SQLITE_LOCKED
    def belegt(*args, **kwargs):
        raise OperationalError("synthetisch belegt") from ursprung
    monkeypatch.setattr("ki.gegenueberstellungen.anfordern", belegt)
    r = webpost(client, web_lage[2])
    assert r.status_code == 200 and not modell
    assert r.context["form"]["wortlaut"].value() == UMFORMULIERT["wortlaut"]
    text = r.content.decode()
    assert "Ihr Text bleibt erhalten" in text and "Mein Antrag ist etwas anderes" in text and "Diesen unterstützen" in text


def test_modelltext_wird_als_text_escaped_und_nie_als_html_gerendert(client, web_lage, modell, monkeypatch):
    _, _, angebot = web_lage
    original = AttrappenAnbieter.frage
    def html(self, auftrag, eingabe, zeitgrenze=None):
        a = original(self, auftrag, eingabe, zeitgrenze=zeitgrenze)
        d = json.loads(a.text)
        d["vergleiche"][0]["gemeinsamkeit"] = '<script>alert("x")</script>'
        return Antwort(json.dumps(d), a.modell, a.tokens_ein, a.tokens_aus)
    monkeypatch.setattr(AttrappenAnbieter, "frage", html)
    text = webpost(client, angebot).content.decode()
    assert '&lt;script&gt;alert' in text and '<script>alert("x")</script>' not in text
