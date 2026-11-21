"""Die Ortsseite veröffentlicht nur zugeordnete öffentliche Mandate und Sitzungsticker."""

from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Aufgabe, Mandat, Sitzung
from mitglieder.models import Gemeinde, Gemeindezugang, Mitglied, Wohnsitzart
from verfahren.models import AuditEintrag, Ebene

pytestmark = pytest.mark.django_db


@pytest.fixture
def orte():
    return (
        Gemeinde.objects.create(kennziffer="40510", name="Gleichort", bezirk="Eferding", bundesland="Oberösterreich"),
        Gemeinde.objects.create(kennziffer="41417", name="Gleichort", bezirk="Schärding", bundesland="Oberösterreich"),
    )


def _ort_url(ort):
    return reverse("gemeinde:ort", args=[ort.kennziffer])


def _mandat(name, **daten):
    m = Mitglied.objects.create_user(name, pseudonym_oeffentlich=name)
    return Mandat.objects.create(mitglied=m, bezeichnung=name, **daten)


def _sitzung(mandat, name, beginn, ende=None):
    aufgabe = Aufgabe.objects.create(mandat=mandat, titel=name, sitzungstag=True, frist=beginn)
    return Sitzung.objects.create(mandat=mandat, aufgabe=aufgabe, beginn=beginn, ende=ende)


def test_suche_unterscheidet_gleichnamige_orte_und_leere_ergebnisse(client, orte):
    url = reverse("gemeinde:start")
    r = client.get(url, {"ort": "Gleichort"})
    assert r.status_code == 200
    assert list(r.context["trefferseite"]) == list(orte)
    assert all(_ort_url(ort) in r.content.decode() for ort in orte)
    assert list(client.get(url, {"ort": orte[1].kennziffer}).context["trefferseite"]) == [orte[1]]
    assert "Keine passende Gemeinde gefunden." in client.get(url, {"ort": "Unbekannt"}).content.decode()
    assert client.get(reverse("gemeinde:ort", args=["00000"])).status_code == 404


def test_ort_verwechselt_weder_wohnsitz_namen_noch_ebenen(client, orte):
    gemeinde, andere = orte
    richtig = _mandat("Erstes Mandat", gemeinde=gemeinde, gebiet=gemeinde.name)
    _mandat("Gleichnamiger Fremdort", gemeinde=andere, gebiet=gemeinde.name)
    _mandat("Alter Freitext ohne Zuordnung", gebiet=gemeinde.name)
    _mandat("Bezirksvertretung", ebene=Ebene.BEZIRK, gebiet=gemeinde.name)
    _mandat("Beendet", gemeinde=gemeinde, beendet=timezone.localdate())
    _mandat("Beginnt erst morgen", gemeinde=gemeinde, angetreten=timezone.localdate() + timedelta(days=1))
    test = _mandat("Testmandat", gemeinde=gemeinde)
    Mitglied.objects.filter(pk=test.mitglied_id).update(testkonto=True)
    r = client.get(_ort_url(gemeinde))
    assert r.status_code == 200
    assert list(r.context["mandate"]) == [richtig]
    assert "keine amtliche Seite" in r.content.decode()
    with pytest.raises(IntegrityError), transaction.atomic():
        Mandat.objects.filter(pk=richtig.pk).update(ebene=Ebene.BEZIRK)


def test_ort_zeigt_wirksame_nachlese_ohne_aenderung_an_der_sitzung(client, orte):
    jetzt = timezone.now()
    m = _mandat("DDÖ Gemeinderat", gemeinde=orte[0])
    fremd = _mandat("Andere Gemeinde", gemeinde=orte[1])
    live = _sitzung(m, "Sitzung läuft", jetzt - timedelta(minutes=5))
    beendet = _sitzung(m, "Beendete Sitzung", jetzt - timedelta(hours=2), jetzt - timedelta(hours=1))
    abgelaufen = _sitzung(m, "Zeitlich beendet", jetzt - timedelta(days=2))
    _sitzung(m, "Zu alt", jetzt - timedelta(days=12), jetzt - timedelta(days=12))
    _sitzung(m, "Zukünftig", jetzt + timedelta(days=1))
    _sitzung(fremd, "Unzuständige Sitzung", jetzt - timedelta(minutes=5))
    audit_vorher = AuditEintrag.objects.count()
    r = client.get(_ort_url(orte[0]))
    assert r.context["laufend"] == [live]
    assert r.context["protokolle"] == [beendet, abgelaufen]
    assert f"?sitzung={beendet.pk}" in r.content.decode()
    assert "Unzuständige Sitzung" not in r.content.decode()
    abgelaufen.refresh_from_db()
    assert abgelaufen.ende is None
    assert AuditEintrag.objects.count() == audit_vorher


def test_ausschliesslich_verwaltung_ordnen_oder_entfernen_mit_audit(client, orte):
    mandat = _mandat("Gemeinderat", gebiet="Historischer Freitext")
    ziel = reverse("mandatare:verwaltung_aktion")
    daten = {"aktion": "gemeinde_zuordnen", "mandat": mandat.pk, "gemeindekennziffer": orte[0].kennziffer}
    client.force_login(mandat.mitglied)
    assert client.post(ziel, daten).status_code == 403
    admin = Mitglied.objects.create_user("Verwaltung", ist_admin=True)
    ohne_csrf = Client(enforce_csrf_checks=True)
    ohne_csrf.force_login(admin)
    assert ohne_csrf.post(ziel, daten).status_code == 403
    client.force_login(admin)
    assert client.get(ziel, daten).status_code == 405
    assert client.post(ziel, daten).status_code == 302
    mandat.refresh_from_db()
    assert mandat.gemeinde == orte[0] and mandat.gebiet == "Historischer Freitext"
    client.post(ziel, daten)
    client.post(ziel, {**daten, "gemeindekennziffer": "00000"})
    client.post(ziel, {k: v for k, v in daten.items() if k != "gemeindekennziffer"})
    mandat.refresh_from_db()
    assert mandat.gemeinde == orte[0]
    assert client.post(ziel, {**daten, "gemeindekennziffer": ""}).status_code == 302
    mandat.refresh_from_db()
    assert mandat.gemeinde is None
    ereignisse = list(AuditEintrag.objects.filter(ereignis__typ="mandat_gemeinde_zugeordnet")
                      .order_by("pk").values_list("ereignis", flat=True))
    assert [(e["vorher_gemeinde"], e["gemeinde"]) for e in ereignisse] == [(None, orte[0].pk), (orte[0].pk, None)]


def test_gemeindekonto_verlinkt_nur_aktuelle_hauptgemeinde(client, orte):
    konto = Mitglied.objects.create_user(
        "einwohner", parteikonto=False, wohnsitz=orte[0], wohnsitz_art=Wohnsitzart.OESTERREICH,
    )
    jetzt = timezone.now()
    Gemeindezugang.objects.create(konto=konto, angemeldet_am=jetzt, alter_erklaert_am=jetzt, bestaetigt_am=jetzt)
    client.force_login(konto)
    assert _ort_url(orte[0]) in client.get(reverse("gemeinde:konto")).content.decode()
    assert client.get(_ort_url(orte[1])).status_code == 200
    assert client.post(reverse("mandatare:verwaltung_aktion"), {"aktion": "gemeinde_zuordnen"}).status_code == 403
    Mitglied.objects.filter(pk=konto.pk).update(wohnsitz=None, wohnsitz_art=Wohnsitzart.AUSLAND)
    assert _ort_url(orte[0]) not in client.get(reverse("gemeinde:konto")).content.decode()
