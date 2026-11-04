"""Keine Anbieterwirkung bei Angeboten und keine zweite Reservierung je Anforderung."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

import copy
import uuid

import pytest
from django.core.exceptions import ValidationError
from django.db import transaction

from ki.models import KILauf, Vergleichsanfrage
from ki.test_vergleichskontext import lage, snapshot  # noqa: F401
from ki.vergleichsanfragen import anbieten, anlegen, kennung_lesen, reservieren
from verfahren.einbringwahl import pruefstand_fuer
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def anfrage(lage):
    daten, konto, _, pruefstand = lage
    token = anbieten(daten, konto, pruefstand)
    kennung = kennung_lesen(token, daten, konto, pruefstand)
    return anlegen(kennung, snapshot(lage), konto)[0]


def test_angebot_allein_speichert_keinen_entwurf_und_startet_keinen_lauf(lage):
    d, m, _, stand = lage
    token = anbieten(d, m, stand)
    assert kennung_lesen(token, d, m, stand).version == 4
    assert not Vergleichsanfrage.objects.exists() and not KILauf.objects.exists()


@pytest.mark.parametrize("art", ["konto", "daten", "angebot", "signatur"])
def test_anforderungskennung_ist_an_konto_formular_und_genaues_angebot_gebunden(lage, art):
    d, m, _, stand = lage
    token = anbieten(d, m, stand)
    if art == "konto":
        m = mitglied_anlegen("fremde_anfrage")
    elif art == "daten":
        d = {**d, "begruendung": "Anderer Grund"}
    elif art == "angebot":
        from verfahren.aehnlichkeit import Ergebnis
        from verfahren.einbringwahl import pruefstand_lesen
        stand = pruefstand_fuer(d, m, Ergebnis(treffer=[]))
        assert pruefstand_lesen(stand, d, m) is not None
    else:
        token += "x"
    with pytest.raises(ValueError):
        kennung_lesen(token, d, m, stand)
    assert not Vergleichsanfrage.objects.exists()


def test_doppelpost_legt_nur_eine_unveraenderliche_anfrage_an(lage):
    d, m, _, stand = lage
    token = anbieten(d, m, stand)
    kennung = kennung_lesen(token, d, m, stand)
    erste, neu = anlegen(kennung, snapshot(lage), m)
    zweite, erneut = anlegen(kennung, snapshot(lage), m)
    assert neu and not erneut and erste.pk == zweite.pk
    assert erste.kontext == zweite.kontext
    assert Vergleichsanfrage.objects.count() == 1


def test_reservierung_bleibt_fuer_frische_objektinstanz_verbraucht(lage):
    a = anfrage(lage)
    alt = Vergleichsanfrage.objects.get(pk=a.pk)
    assert reservieren(a, lage[1])
    assert not reservieren(alt, lage[1])
    # Auch ein betrieblich zurückgesetztes Statusfeld gibt die begonnene Kennung nicht frei.
    Vergleichsanfrage.objects.filter(pk=a.pk).update(status="bereit")
    assert not reservieren(alt, lage[1])
    assert not KILauf.objects.exists()


def test_fremdes_konto_kann_anfrage_nicht_reservieren_oder_ersetzen(lage):
    a = anfrage(lage)
    m = mitglied_anlegen("nicht_besitzer")
    assert not reservieren(a, m)
    with pytest.raises(ValueError):
        anlegen(a.pk, a.kontext, m)
    assert Vergleichsanfrage.objects.get(pk=a.pk).status == "bereit"


def test_geaenderter_aber_neu_gehashter_text_ersetzt_keine_bestehende_kennung(lage):
    from ki.kontext import _hash

    a = anfrage(lage)
    k = copy.deepcopy(a.kontext)
    k.pop("sha256")
    k["entwurf"]["wortlaut"] += " Anderer Entwurf"
    k["sha256"] = _hash(k)
    with pytest.raises(ValueError):
        anlegen(a.pk, k, lage[1])
    assert Vergleichsanfrage.objects.get(pk=a.pk).eingabe == a.eingabe


@pytest.mark.parametrize("weg", ["save", "update", "bulk_update", "upsert", "neues_objekt"])
def test_private_eingaben_koennen_nicht_ueberschrieben_werden(lage, weg):
    a = anfrage(lage)
    vorher = a.eingabe
    a.eingabe = "Ersetzter privater Text"
    with transaction.atomic():
        with pytest.raises(ValidationError):
            if weg == "save":
                a.save(update_fields=["eingabe"])
            elif weg == "update":
                Vergleichsanfrage.objects.filter(pk=a.pk).update(eingabe=a.eingabe)
            elif weg == "bulk_update":
                Vergleichsanfrage.objects.bulk_update([a], ["eingabe"])
            elif weg == "upsert":
                Vergleichsanfrage.objects.bulk_create([a], update_conflicts=True, update_fields=["eingabe"], unique_fields=["kennung"])
            else:
                kopie = Vergleichsanfrage(**{f.attname: getattr(a, f.attname) for f in a._meta.concrete_fields})
                kopie.save()
    assert Vergleichsanfrage.objects.get(pk=a.pk).eingabe == vorher


@pytest.mark.parametrize("weg", ["objekt", "queryset"])
def test_anfragen_werden_nicht_geloescht(lage, weg):
    a = anfrage(lage)
    with pytest.raises(ValidationError):
        a.delete() if weg == "objekt" else Vergleichsanfrage.objects.filter(pk=a.pk).delete()
    assert Vergleichsanfrage.objects.filter(pk=a.pk).exists()


def test_neuer_ausdruecklicher_auftrag_erhaelt_eigene_kennung(lage):
    d, m, _, stand = lage
    eins = kennung_lesen(anbieten(d, m, stand), d, m, stand)
    zwei = kennung_lesen(anbieten(d, m, stand), d, m, stand)
    assert eins != zwei
    with pytest.raises(ValueError):
        anlegen(uuid.uuid1(), snapshot(lage), m)


def test_nur_eigene_private_anfragen_im_persoenlichen_export(lage, client):
    from django.urls import reverse

    a = anfrage(lage)
    client.force_login(lage[1])
    export = client.get(reverse("mitglieder:profil_export"))
    assert export.status_code == 200
    d = export.json()["private_textvergleiche"]
    assert len(d) == 1 and d[0]["kennung"] == str(a.pk)
    assert d[0]["eingabe"] == a.eingabe and d[0]["kontext"] == a.kontext
    client.force_login(mitglied_anlegen("fremder_export"))
    assert client.get(reverse("mitglieder:profil_export")).json()["private_textvergleiche"] == []


def test_privater_entwurf_erscheint_in_keinem_oeffentlichen_antragsarchiv(lage, client):
    from django.urls import reverse

    a = anfrage(lage)
    client.logout()
    for art in ("json", "md"):
        antwort = client.get(reverse("verfahren:archiv_export", args=[lage[2].pk, art]))
        assert antwort.status_code == 200
        assert a.kontext["entwurf"]["wortlaut"] not in antwort.content.decode()
        assert str(a.pk) not in antwort.content.decode()
