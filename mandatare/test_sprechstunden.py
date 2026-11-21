"""Ort, Rechte, Zeitzone und nachvollziehbare Absage von veröffentlichten Terminen."""

from datetime import timedelta

import pytest
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Mandat, Sprechstunde
from mitglieder.models import Gemeinde
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


@pytest.fixture
def mandat():
    ort = Gemeinde.objects.create(kennziffer="40510", name="Gleichort", bezirk="Eferding", bundesland="oberoesterreich")
    return Mandat.objects.create(mitglied=mitglied_anlegen("ratsmitglied"), bezeichnung="Gemeinderat", gemeinde=ort)


def _formular():
    beginn = timezone.localtime() + timedelta(days=2)
    return {"beginn": beginn.strftime("%Y-%m-%dT%H:%M"), "ende": (beginn + timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M"),
            "treffpunkt": "Öffentlicher Raum A"}


def test_mandatar_veroeffentlicht_nur_am_zugeordneten_ort_und_sagt_nachvollziehbar_ab(client, mandat):
    gleichort = Gemeinde.objects.create(kennziffer="41419", name=mandat.gemeinde.name, bezirk="Schärding", bundesland="oberoesterreich")
    client.force_login(mandat.mitglied)
    url = reverse("mandatare:sprechstunden", args=[mandat.pk])
    antwort = client.post(url, _formular())
    assert antwort.status_code == 302
    termin = Sprechstunde.objects.get()
    oeffentlich = reverse("gemeinde:ort", args=[mandat.gemeinde.kennziffer])
    gast = Client()
    assert "Öffentlicher Raum A" in gast.get(oeffentlich).content.decode()
    assert "Öffentlicher Raum A" not in gast.get(reverse("gemeinde:ort", args=[gleichort.kennziffer])).content.decode()
    assert "private" in client.get(url).headers["Cache-Control"]

    absage = reverse("mandatare:sprechstunde_absagen", args=[mandat.pk, termin.pk])
    assert client.get(absage).status_code == 405
    for _ in range(2):
        assert client.post(absage).status_code == 302
    termin.refresh_from_db()
    assert termin.abgesagt_am is not None
    assert "Abgesagt" in gast.get(oeffentlich).content.decode()
    audit = AuditEintrag.objects.filter(ereignis__typ__startswith="sprechstunde_")
    assert sorted(e.ereignis["typ"] for e in audit) == ["sprechstunde_abgesagt", "sprechstunde_veroeffentlicht"]


def test_fremde_paused_und_mandatsende_sperren_veroeffentlichung(client, mandat):
    url = reverse("mandatare:sprechstunden", args=[mandat.pk])
    client.force_login(mitglied_anlegen("fremd"))
    assert client.post(url, _formular()).status_code == 404
    client.force_login(mandat.mitglied)
    mandat.mitglied.status = "pausiert"
    mandat.mitglied.save(update_fields=["status"])
    assert client.post(url, _formular()).status_code == 403
    mandat.mitglied.status = "aktiv"
    mandat.mitglied.save(update_fields=["status"])
    mandat.vertretung_beendet_am = timezone.localdate()
    mandat.save(update_fields=["vertretung_beendet_am"])
    assert client.post(url, _formular()).status_code == 404
    assert not Sprechstunde.objects.exists()


def test_falsche_datumsfolgen_doppelung_und_csrf(client, mandat):
    url = reverse("mandatare:sprechstunden", args=[mandat.pk])
    client.force_login(mandat.mitglied)
    daten = _formular()
    assert client.post(url, {**daten, "ende": daten["beginn"]}).status_code == 200
    assert client.post(url, {**daten, "beginn": daten["beginn"] + "+05:00"}).status_code == 200
    assert client.post(url, {**daten, "beginn": "a"}).status_code == 200
    assert not Sprechstunde.objects.exists()
    assert client.post(url, daten).status_code == 302
    assert client.post(url, daten).status_code == 200
    assert Sprechstunde.objects.count() == 1
    abgesichert = Client(enforce_csrf_checks=True)
    abgesichert.force_login(mandat.mitglied)
    assert abgesichert.post(url, daten).status_code == 403


# ── GP-116: Mandatsende, Vertretungsende und neue Zuordnung sagen kommende Termine ab ──────────


def _termin(mandat, tage=2, treffpunkt="Öffentlicher Raum A"):
    beginn = timezone.now() + timedelta(days=tage)
    return Sprechstunde.objects.create(mandat=mandat, gemeinde=mandat.gemeinde, beginn=beginn,
                                       ende=beginn + timedelta(hours=1), treffpunkt=treffpunkt)


def _absagen_audit():
    return [e.ereignis for e in AuditEintrag.objects.filter(ereignis__typ="sprechstunde_abgesagt")]


def test_mandatsende_sagt_kommende_sprechstunden_ab_und_beendet_die_laufende_sitzung(client, mandat):
    from mandatare.models import Sitzung
    from mandatare.sitzung import sitzung_beginnen
    from mandatare.test_mandatare import admin_anlegen
    from mandatare.test_sitzung_modelle import sitzungstag

    vorbei = Sprechstunde.objects.create(mandat=mandat, gemeinde=mandat.gemeinde, beginn=timezone.now() - timedelta(days=3),
                                         ende=timezone.now() - timedelta(days=3, hours=-1), treffpunkt="Früher")
    termin = _termin(mandat)
    sitzung = sitzung_beginnen(mandat, sitzungstag(mandat), punkte=["Budget"])
    client.force_login(admin_anlegen("gp116admin"))
    assert client.post(reverse("mandatare:verwaltung_aktion"), {"aktion": "beenden", "mandat": mandat.pk}).status_code == 302
    termin.refresh_from_db()
    vorbei.refresh_from_db()
    assert termin.abgesagt_am is not None and vorbei.abgesagt_am is None
    (eintrag,) = _absagen_audit()
    assert eintrag["termin"] == termin.pk and eintrag["anlass"] == "mandat_beendet"
    seite = Client().get(reverse("gemeinde:ort", args=[mandat.gemeinde.kennziffer])).content.decode()
    assert "Öffentlicher Raum A" in seite and "Abgesagt" in seite
    assert not Sitzung.objects.get(pk=sitzung.pk).laeuft()
    assert AuditEintrag.objects.filter(ereignis__typ="sitzung_beendet", ereignis__anlass="mandat_beendet").count() == 1


def test_neue_zuordnung_sagt_die_termine_am_alten_ort_ab(client, mandat):
    from mandatare.test_mandatare import admin_anlegen

    alt = mandat.gemeinde
    termin = _termin(mandat)
    neu = Gemeinde.objects.create(kennziffer="40511", name="Neuort", bezirk="Eferding", bundesland="oberoesterreich")
    Mandat.objects.filter(pk=mandat.pk).update(ebene="gemeinde")
    client.force_login(admin_anlegen("gp116admin2"))
    client.post(reverse("mandatare:verwaltung_aktion"),
                {"aktion": "gemeinde_zuordnen", "mandat": mandat.pk, "gemeindekennziffer": neu.kennziffer})
    mandat.refresh_from_db()
    assert mandat.gemeinde_id == neu.pk
    termin.refresh_from_db()
    assert termin.abgesagt_am is not None
    assert [e["anlass"] for e in _absagen_audit()] == ["gemeinde_zuordnung"]
    seite = Client().get(reverse("gemeinde:ort", args=[alt.kennziffer])).content.decode()
    assert "Öffentlicher Raum A" in seite and "Abgesagt" in seite
    assert "Öffentlicher Raum A" not in Client().get(reverse("gemeinde:ort", args=[neu.kennziffer])).content.decode()


def test_ende_der_vertretung_sagt_kommende_sprechstunden_ab(mandat):
    from mandatare import models as mm
    from plattform_core import Phase
    from verfahren.models import Antrag, Antragsart

    termin = _termin(mandat, tage=5)
    ende = timezone.now() - timedelta(days=40)
    antrag = Antrag.objects.create(titel="Vertrauensfrage", art=Antragsart.VERTRAUENSFRAGE, eingebracht_von=mandat.mitglied,
                                   eingebracht_am=ende - timedelta(days=20), phase=Phase.ANGENOMMEN.value, phase_beginn=ende,
                                   policy_snapshot={})
    vf = mm.Vertrauensfrage.objects.create(antrag=antrag, mandat=mandat)
    mm.vertrauensfrage_wirkungen(vf, jetzt=ende)
    mm.vertrauensfragen_fortschreiben()
    mandat.refresh_from_db()
    termin.refresh_from_db()
    assert mandat.vertretung_beendet_am is not None
    assert termin.abgesagt_am is not None
    assert [e["anlass"] for e in _absagen_audit()] == ["vertretung_beendet"]


def test_altbestand_abgesagter_termin_eines_beendeten_mandats_bleibt_bis_zum_ende_sichtbar(mandat):
    termin = _termin(mandat)
    Sprechstunde.objects.filter(pk=termin.pk).update(abgesagt_am=timezone.now())
    Mandat.objects.filter(pk=mandat.pk).update(beendet=timezone.localdate())
    seite = Client().get(reverse("gemeinde:ort", args=[mandat.gemeinde.kennziffer])).content.decode()
    assert "Öffentlicher Raum A" in seite and "Abgesagt" in seite
    # Ein Testkonto erscheint auch mit abgesagtem Termin nie auf der Ortsseite (Gegenlesen GP-116)
    type(mandat.mitglied).objects.filter(pk=mandat.mitglied_id).update(testkonto=True)
    seite = Client().get(reverse("gemeinde:ort", args=[mandat.gemeinde.kennziffer])).content.decode()
    assert "Öffentlicher Raum A" not in seite
