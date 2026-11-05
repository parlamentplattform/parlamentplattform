"""Der bestehende geschützte Einzelimport für ausdrücklich gewähltes Landesrecht."""

from unittest.mock import Mock

import pytest
from django.test import Client
from django.urls import reverse

from faktenbasis import importieren, landesrecht
from faktenbasis.models import AbrufSperre, Norm, RisImport
from faktenbasis.ris import RisFehler
from faktenbasis.test_landesrecht import NUMMER, STAND, beispiel
from faktenbasis.test_verwaltung import admin
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from mitglieder.models import Identitaetsstufe, Mitgliedsstatus
from parameter.models import Parameter
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]


def anfordern(client, *, follow=False, **daten):
    return client.post(reverse("faktenbasis:verwaltung"), {
        "quelle": "land", "bundesland": "Oberoesterreich", "gesetzesnummer": NUMMER,
        "stand": STAND.isoformat(), "seite": 2, **daten,
    }, follow=follow)


def antwort(land):
    d = beispiel(land)
    d["OgdSearchResult"]["OgdDocumentResults"]["Hits"].update({"@pageNumber": "2", "#text": "11"})
    return d


@pytest.mark.parametrize("land", list(landesrecht.BUNDESLAENDER))
def test_jedes_ausdruecklich_gewaehlte_land_geht_genau_einmal_durch_den_bestehenden_import(client, monkeypatch, land):
    person = admin(client)
    calls = []
    def holen(nummer, stand, bundesland, *, seite):
        calls.append((nummer, stand, bundesland, seite))
        return landesrecht.antwort_parsen(antwort(bundesland), nummer, bundesland, seite=seite)
    monkeypatch.setattr(landesrecht, "abrufen", holen)
    monkeypatch.setattr(importieren, "abrufen", Mock(side_effect=AssertionError("Kein Bundesabruf")))
    r = anfordern(client, bundesland=land, follow=True)
    assert r.status_code == 200 and calls == [(NUMMER, STAND, land, 2)]
    lauf = RisImport.objects.get()
    norm = Norm.objects.get()
    assert lauf.erfolgreich and lauf.ebene == norm.ebene == "Land"
    assert lauf.bundesland == norm.bundesland == landesrecht.BUNDESLAENDER[land]
    assert lauf.seite == 2 and norm.importlauf == lauf
    audit = AuditEintrag.objects.last().ereignis
    assert audit["durch"] == person.pk and audit["ebene"] == "Land"
    assert audit["bundesland"] == landesrecht.BUNDESLAENDER[land] and audit["seite"] == 2
    assert landesrecht.BUNDESLAENDER[land] in r.content.decode()
    assert landesrecht.BUNDESLAENDER[land] in client.get(reverse("faktenbasis:norm", args=[norm.pk])).content.decode()


@pytest.mark.parametrize("daten", [
    {"bundesland": ""}, {"bundesland": "OÖ"}, {"bundesland": "https://example.invalid"},
    {"quelle": "bund"}, {"quelle": "unbekannt"}, {"quelle": "", "bundesland": "Oberoesterreich"},
    {"seite": 0}, {"gesetzesnummer": "keineNummer"}, {"stand": "2026-02-30"},
])
def test_formfehler_und_widerspruechliche_herkunft_verbrauchen_keinen_abruf(client, monkeypatch, daten):
    admin(client)
    abruf = Mock(side_effect=AssertionError("Kein Abruf bei ungültiger Quellenwahl"))
    monkeypatch.setattr(importieren, "importieren", abruf)
    r = anfordern(client, **daten)
    assert r.status_code == 200 and r.context["formular"].errors
    abruf.assert_not_called()
    assert not AbrufSperre.objects.exists() and not RisImport.objects.exists() and not AuditEintrag.objects.exists()


def test_get_uebernimmt_keine_quellenauswahl_als_abruf(client, monkeypatch):
    admin(client)
    abruf = Mock(side_effect=AssertionError("GET löst nichts aus"))
    monkeypatch.setattr(importieren, "importieren", abruf)
    r = client.get(reverse("faktenbasis:verwaltung"), {"quelle": "land", "bundesland": "Wien", "seite": 2})
    assert r.status_code == 200 and "id_quelle" in r.content.decode() and "id_bundesland" in r.content.decode()
    abruf.assert_not_called()
    assert not AbrufSperre.objects.exists() and not AuditEintrag.objects.exists()


@pytest.mark.parametrize("wer", ["gast", "mitglied", "ungeprueft", "pausiert", "testkonto", "inaktiv", "adresswechsel"])
def test_land_ist_keine_umgehung_der_bestehenden_abrufrechte(client, monkeypatch, wer):
    if wer == "mitglied":
        client.force_login(mitglied_anlegen())
    elif wer != "gast":
        admin(client, **{
            "ungeprueft": {"identitaetsstufe": Identitaetsstufe.UNGEPRUEFT},
            "pausiert": {"status": Mitgliedsstatus.PAUSIERT}, "testkonto": {"testkonto": True},
            "inaktiv": {"is_active": False}, "adresswechsel": {},
        }[wer])
        if wer == "adresswechsel":
            from mitglieder.models import Mitglied

            monkeypatch.setattr(Mitglied, "adresswechsel_offen", property(lambda self: True))
    abruf = Mock(side_effect=AssertionError("Keine Quelle ohne Abrufrecht"))
    monkeypatch.setattr(importieren, "importieren", abruf)
    assert anfordern(client).status_code == (302 if wer in {"gast", "inaktiv"} else 403)
    abruf.assert_not_called()
    assert not AbrufSperre.objects.exists() and not AuditEintrag.objects.exists()


def test_csrf_gilt_auch_fuer_landesrecht(client, monkeypatch):
    person = admin(client)
    anderer = Client(enforce_csrf_checks=True)
    anderer.force_login(person)
    abruf = Mock(side_effect=AssertionError("Kein Abruf ohne CSRF"))
    monkeypatch.setattr(importieren, "importieren", abruf)
    assert anfordern(anderer).status_code == 403
    abruf.assert_not_called()


def test_fehler_haelt_land_und_seite_fest_ohne_fremden_servertext(client, monkeypatch):
    admin(client)
    monkeypatch.setattr(importieren, "abrufen", Mock(side_effect=AssertionError("Kein Bundesabruf")))
    monkeypatch.setattr(landesrecht, "abrufen", Mock(side_effect=RisFehler("antwortformat")))
    r = anfordern(client, follow=True)
    assert r.status_code == 200 and "Bereits gespeicherte Angaben bleiben erhalten" in r.content.decode()
    lauf = RisImport.objects.get()
    assert not lauf.erfolgreich and lauf.bundesland == "Oberösterreich" and lauf.seite == 2
    assert not Norm.objects.exists()
    assert AuditEintrag.objects.last().ereignis["bundesland"] == "Oberösterreich"


def test_land_teilt_das_stundenkontingent_mit_bund(client, monkeypatch):
    admin(client)
    Parameter.objects.create(schluessel="faktenbasis-manuelle-abrufe-je-stunde", wert="0")
    abruf = Mock(side_effect=AssertionError("Kein Abruf ohne Kontingent"))
    monkeypatch.setattr(landesrecht, "abrufen", abruf)
    r = anfordern(client, follow=True)
    assert r.status_code == 200 and "Stundenkontingent" in r.content.decode()
    abruf.assert_not_called()
    assert not RisImport.objects.exists()
