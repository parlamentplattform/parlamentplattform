"""Wahl ohne Entwurfsverlust, ohne Anbieter beim Tippen und ohne doppelte Unterstützung."""

import pytest
from django.db.models.deletion import ProtectedError
from django.test import Client
from django.urls import reverse

from ki.models import KILauf
from mitglieder.models import Identitaetsstufe, Mitgliedsstatus
from parameter.models import Parameter
from verfahren.archiv import als_markdown, archiv
from verfahren.models import Antrag, AuditEintrag, Eigenstaendigkeit, Unterstuetzung, antrag_einbringen
from verfahren.test_einbringen_aehnlichkeit import UMFORMULIERT
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def lage(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    bestehend = antrag_einbringen(anna, ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)
    bernd = mitglied_anlegen("bernd")
    client.force_login(bernd)
    return bestehend, bernd


def _angebot(client):
    antwort = client.post(reverse("verfahren:einbringen"), UMFORMULIERT)
    assert antwort.status_code == 200
    return antwort.context["pruefstand"]


def _wahl(client, token, **wahl):
    return client.post(reverse("verfahren:einbringen"), {**UMFORMULIERT, "pruefstand": token, **wahl})


def test_vorschau_ruft_auch_mit_angeschlossenem_anbieter_keinen_steckplatz_auf(client, settings, lage):
    settings.DDOE_KI_ANBIETER = "attrappe"
    antwort = client.post(reverse("verfahren:einbringen_vorschau"), UMFORMULIERT)
    assert antwort.status_code == 200 and "Die Vorschau bleibt lokal" in antwort.content.decode()
    assert antwort.context["aehnliche"][0]["antrag"] == lage[0]
    assert not KILauf.objects.exists()
    assert Antrag.objects.count() == 1 and not Eigenstaendigkeit.objects.exists()


def test_vorschau_grenzen_kommen_aus_dem_register(client, lage):
    for key, wert in [
        ("aehnlichkeit-vorschau-mindestzeichen", "99999"),
        ("aehnlichkeit-vorschau-hoechstzeichen", "1"),
    ]:
        Parameter.objects.update_or_create(schluessel=key, defaults={"wert": wert})
        antwort = client.post(reverse("verfahren:einbringen_vorschau"), UMFORMULIERT)
        assert antwort.context["aehnliche"] == []
        Parameter.objects.filter(schluessel=key).delete()


def test_direkte_unterstuetzung_fragt_nach_und_behaelt_den_entwurf(client, lage):
    bestehend, bernd = lage
    token = _angebot(client)
    antwort = _wahl(client, token, unterstuetzen=str(bestehend.pk))
    assert antwort.status_code == 200 and antwort.context["bestaetigung"] == bestehend
    assert "Ihr eigener Text wird nicht eingebracht" in antwort.content.decode()
    assert antwort.context["form"]["wortlaut"].value() == UMFORMULIERT["wortlaut"]
    assert not Unterstuetzung.objects.filter(antrag=bestehend, mitglied=bernd).exists()
    zurueck = _wahl(client, token, vergleich_zurueck="1")
    assert zurueck.context["bestaetigung"] is None
    assert zurueck.context["form"]["titel"].value() == UMFORMULIERT["titel"]


def test_native_und_htmx_zeilenenden_sind_derselbe_pruefstand(client, lage):
    daten = {**UMFORMULIERT, "wortlaut": UMFORMULIERT["wortlaut"] + "\nEin weiterer Absatz."}
    vorschau = client.post(reverse("verfahren:einbringen_vorschau"), daten)
    daten["wortlaut"] = daten["wortlaut"].replace("\n", "\r\n")
    antwort = client.post(reverse("verfahren:einbringen"), {
        **daten, "pruefstand": vorschau.context["pruefstand"], "trotzdem": "1",
    })
    assert antwort.status_code == 302 and Eigenstaendigkeit.objects.count() == 1


def test_keine_falsche_einstufung_bei_geaendertem_text(client, lage):
    token = _angebot(client)
    antwort = client.post(reverse("verfahren:einbringen"), {
        **UMFORMULIERT, "wortlaut": "Ein neuer, anderer Text.", "pruefstand": token, "trotzdem": "1",
    })
    assert antwort.status_code == 200 and Antrag.objects.count() == 1
    assert not Eigenstaendigkeit.objects.exists()


def test_bestaetigte_unterstuetzung_ist_idempotent_und_legt_keinen_parallelantrag_an(client, lage):
    bestehend, bernd = lage
    token = _angebot(client)
    for _ in range(2):
        _wahl(client, token, unterstuetzen_bestaetigt=str(bestehend.pk))
    assert Antrag.objects.count() == 1
    assert Unterstuetzung.gueltige().filter(antrag=bestehend, mitglied=bernd).count() == 1
    assert AuditEintrag.objects.filter(ereignis__typ="unterstuetzung", ereignis__antrag=bestehend.pk).count() == 1


def test_eigene_wahl_bleibt_als_vermerk_samt_fassung_und_export(client, lage):
    bestehend, _ = lage
    token = _angebot(client)
    antwort = _wahl(client, token, trotzdem="1")
    assert antwort.status_code == 302
    neu = Antrag.objects.latest("pk")
    v = Eigenstaendigkeit.objects.get(antrag=neu)
    assert v.gegenueber == bestehend and v.fassung_nummer == 1 and v.titel == bestehend.titel
    bestehend.titel = "Neuer Titel"
    bestehend.save(update_fields=["titel"])
    v.refresh_from_db()
    assert v.titel != bestehend.titel
    assert archiv(neu)["eigenstaendigkeit"][0]["antrag"] == bestehend.pk
    assert "Beim Einbringen als eigenständig eingestuft gegenüber:" in als_markdown(neu)
    seite = client.get(reverse("verfahren:antrag", args=[neu.pk])).content.decode()
    assert v.titel in seite
    with pytest.raises(ProtectedError):
        bestehend.delete()


@pytest.mark.parametrize("art", ["text", "konto", "signatur", "treffer"])
def test_fremde_oder_veraltete_auswahl_schreibt_nichts(client, lage, art):
    bestehend, _ = lage
    token = _angebot(client)
    daten = {**UMFORMULIERT, "pruefstand": token, "unterstuetzen_bestaetigt": str(bestehend.pk)}
    if art == "text":
        daten["begruendung"] = "Geändert seit der Vorschau."
    elif art == "konto":
        client.force_login(mitglied_anlegen("carla"))
    elif art == "signatur":
        daten["pruefstand"] = token + "x"
    else:
        daten["unterstuetzen_bestaetigt"] = "99999"
    antwort = client.post(reverse("verfahren:einbringen"), daten)
    assert antwort.status_code == 200
    assert antwort.context["form"].non_field_errors()
    assert Antrag.objects.count() == 1 and not Eigenstaendigkeit.objects.exists()
    assert not Unterstuetzung.objects.filter(antrag=bestehend).exists()


def test_abgelaufene_phase_behaelt_den_eigenen_text(client, lage):
    bestehend, _ = lage
    token = _angebot(client)
    bestehend.phase = "beratung"
    bestehend.save(update_fields=["phase"])
    antwort = _wahl(client, token, unterstuetzen_bestaetigt=str(bestehend.pk))
    assert antwort.status_code == 200
    assert "Ihr eigener Text bleibt erhalten" in antwort.content.decode()
    assert antwort.context["form"]["wortlaut"].value() == UMFORMULIERT["wortlaut"]
    assert not Unterstuetzung.objects.filter(antrag=bestehend).exists()


@pytest.mark.parametrize("zustand", ["gast", "ungeprueft", "pausiert"])
def test_vorschau_hat_dieselben_rechte_wie_einbringen(client, lage, zustand):
    _, m = lage
    if zustand == "gast":
        client.logout()
    elif zustand == "ungeprueft":
        m.identitaetsstufe = Identitaetsstufe.UNGEPRUEFT
        m.save(update_fields=["identitaetsstufe"])
    else:
        m.status = Mitgliedsstatus.PAUSIERT
        m.save(update_fields=["status"])
    assert client.post(reverse("verfahren:einbringen_vorschau"), UMFORMULIERT).status_code == (
        302 if zustand == "gast" else 403
    )


def test_vorschau_ist_post_mit_csrf(client, lage):
    assert client.get(reverse("verfahren:einbringen_vorschau")).status_code == 405
    gesichert = Client(enforce_csrf_checks=True)
    gesichert.force_login(lage[1])
    assert gesichert.post(reverse("verfahren:einbringen_vorschau"), UMFORMULIERT).status_code == 403
