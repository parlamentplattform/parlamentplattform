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


def _verlorene_vertrauensfrage(mandat, angefochten: bool):
    """Verloren vor 40 Tagen — die Rückgabefrist ist um; auf Wunsch am dritten Tag rechtzeitig angefochten."""
    from mandatare import models as mm
    from plattform_core import Phase
    from verfahren.models import Antrag, Antragsart

    ende = timezone.now() - timedelta(days=40)
    antrag = Antrag.objects.create(titel="Vertrauensfrage", art=Antragsart.VERTRAUENSFRAGE, eingebracht_von=mandat.mitglied,
                                   eingebracht_am=ende - timedelta(days=20), phase=Phase.ANGENOMMEN.value, phase_beginn=ende,
                                   policy_snapshot={})
    vf = mm.Vertrauensfrage.objects.create(antrag=antrag, mandat=mandat)
    mm.vertrauensfrage_wirkungen(vf, jetzt=ende)
    if angefochten:
        mm.vertrauensfrage_anfechtung_vermerken(vf, "PSG 1/26", jetzt=ende + timedelta(days=3))
        vf.refresh_from_db()
        assert vf.anfechtung_rechtzeitig
    return vf


def _ortsseite(mandat):
    return Client().get(reverse("gemeinde:ort", args=[mandat.gemeinde.kennziffer])).content.decode()


def test_bei_offener_anfechtung_blendet_das_vertretungsende_termine_nur_aus_und_beendet_die_sitzung(mandat):
    """Regelvorgriff GP-116: Solange eine rechtzeitige Anfechtung offen ist, sagt das Ende der Vertretung
    die Sprechstunden nicht ab — sie sind wie im Stand 0.114.0 nur ausgeblendet. Eine laufende Sitzung endet."""
    from mandatare import models as mm
    from mandatare.models import Sitzung

    Mandat.objects.filter(pk=mandat.pk).update(ebene="gemeinde")
    termin = _termin(mandat, tage=5)
    sitzung = _laufende_sitzung(mandat)
    _verlorene_vertrauensfrage(mandat, angefochten=True)
    mm.vertrauensfragen_fortschreiben()
    mandat.refresh_from_db()
    termin.refresh_from_db()
    assert mandat.vertretung_beendet_am is not None
    assert termin.abgesagt_am is None and not _absagen_audit()
    assert "Öffentlicher Raum A" not in _ortsseite(mandat)  # ausgeblendet wie live
    assert not Sitzung.objects.get(pk=sitzung.pk).laeuft()
    assert AuditEintrag.objects.filter(ereignis__typ="sitzung_beendet", ereignis__anlass="vertretung_beendet").count() == 1
    mm.vertrauensfragen_fortschreiben()  # ein weiterer Lauf sagt auch nichts ab
    termin.refresh_from_db()
    assert termin.abgesagt_am is None


def test_bestaetigt_das_schiedsgericht_werden_die_kommenden_termine_dann_abgesagt(mandat):
    from mandatare import models as mm

    Mandat.objects.filter(pk=mandat.pk).update(ebene="gemeinde")
    termin = _termin(mandat, tage=5)
    vf = _verlorene_vertrauensfrage(mandat, angefochten=True)
    mm.vertrauensfragen_fortschreiben()
    termin.refresh_from_db()
    assert termin.abgesagt_am is None
    mm.vertrauensfrage_entscheidung_vermerken(mm.Vertrauensfrage.objects.get(pk=vf.pk), "bestaetigt")
    termin.refresh_from_db()
    assert termin.abgesagt_am is not None
    assert [e["anlass"] for e in _absagen_audit()] == ["vertretung_beendet"]
    seite = _ortsseite(mandat)
    assert "Öffentlicher Raum A" in seite and "Abgesagt" in seite


def test_hebt_das_schiedsgericht_auf_stehen_die_termine_wieder_da(mandat):
    from mandatare import models as mm

    Mandat.objects.filter(pk=mandat.pk).update(ebene="gemeinde")
    termin = _termin(mandat, tage=5)
    vf = _verlorene_vertrauensfrage(mandat, angefochten=True)
    mm.vertrauensfragen_fortschreiben()
    assert "Öffentlicher Raum A" not in _ortsseite(mandat)
    mm.vertrauensfrage_entscheidung_vermerken(mm.Vertrauensfrage.objects.get(pk=vf.pk), "aufgehoben")
    mandat.refresh_from_db()
    termin.refresh_from_db()
    assert mandat.vertretung_beendet_am is None
    assert termin.abgesagt_am is None and not _absagen_audit()
    seite = _ortsseite(mandat)
    assert "Öffentlicher Raum A" in seite and "Abgesagt" not in seite


def test_ohne_anfechtung_bleibt_die_absage_beim_vertretungsende(mandat):
    from mandatare import models as mm

    termin = _termin(mandat, tage=5)
    _verlorene_vertrauensfrage(mandat, angefochten=False)
    mm.vertrauensfragen_fortschreiben()
    termin.refresh_from_db()
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


# ── GP-116 (Folgewelle): die Folgen für ein schon beendetes Mandat, mit neutralem Anlass ──────


def _laufende_sitzung(mandat):
    from mandatare.sitzung import sitzung_beginnen
    from mandatare.test_sitzung_modelle import sitzungstag

    return sitzung_beginnen(mandat, sitzungstag(mandat), punkte=["Budget"])


def test_folgen_fuer_ein_schon_beendetes_mandat_sagen_ab_beenden_die_sitzung_und_wiederholen_sich_nicht(mandat):
    """Der Austritt setzt erst `Mandat.beendet` und ruft dann die Folgen: Das Mandat ist schon beendet, das
    Konto nicht mehr aktiv. Auch Altbestand — ein vor dieser Fassung beendetes Mandat mit verwaistem Termin —
    wird so abgesagt. Ein zweiter Aufruf schreibt nichts mehr."""
    from mandatare.models import Sitzung
    from mandatare.sitzung import ANLASS_MANDATSENDE, mandatsende_folgen
    from mitglieder.models import Mitgliedsstatus

    termin = _termin(mandat)
    sitzung = _laufende_sitzung(mandat)
    Mandat.objects.filter(pk=mandat.pk).update(beendet=timezone.localdate() - timedelta(days=5))
    type(mandat.mitglied).objects.filter(pk=mandat.mitglied_id).update(status=Mitgliedsstatus.AUSGETRETEN, is_active=False)
    mandat = Mandat.objects.get(pk=mandat.pk)
    assert mandat.beendet is not None and ANLASS_MANDATSENDE == "mandat_beendet"
    mandatsende_folgen(mandat, ANLASS_MANDATSENDE)
    termin.refresh_from_db()
    assert termin.abgesagt_am is not None
    assert not Sitzung.objects.get(pk=sitzung.pk).laeuft()
    assert [e["anlass"] for e in _absagen_audit()] == ["mandat_beendet"]
    assert AuditEintrag.objects.filter(ereignis__typ="sitzung_beendet", ereignis__anlass="mandat_beendet").count() == 1
    seite = Client().get(reverse("gemeinde:ort", args=[mandat.gemeinde.kennziffer])).content.decode()
    assert "Öffentlicher Raum A" in seite and "Abgesagt" in seite
    zahl = AuditEintrag.objects.count()
    mandatsende_folgen(mandat, ANLASS_MANDATSENDE)
    assert AuditEintrag.objects.count() == zahl  # idempotent


@pytest.mark.parametrize("wort", ["austritt", "kontosperre", "ausschluss", ""])
def test_das_oeffentliche_protokoll_nennt_nie_warum_das_mandat_endete(mandat, wort):
    """Die Einträge „sprechstunde_abgesagt“ und „sitzung_beendet“ stehen im öffentlichen Protokoll. Ein
    Anlass, der Austritt, Sperre oder Ausschluss verriete, wird zum neutralen Wort für das Mandatsende."""
    from mandatare.sitzung import OEFFENTLICHE_ANLAESSE, mandatsende_folgen

    _termin(mandat)
    _laufende_sitzung(mandat)
    Mandat.objects.filter(pk=mandat.pk).update(beendet=timezone.localdate())
    mandatsende_folgen(Mandat.objects.get(pk=mandat.pk), wort)
    eintraege = [e.ereignis for e in AuditEintrag.objects.filter(ereignis__typ__in=["sprechstunde_abgesagt", "sitzung_beendet"])]
    assert len(eintraege) == 2
    assert {e["anlass"] for e in eintraege} == {"mandat_beendet"}
    assert OEFFENTLICHE_ANLAESSE == {"mandat_beendet", "vertretung_beendet", "gemeinde_zuordnung"}
    for e in AuditEintrag.objects.all():
        assert wort == "" or wort not in str(e.ereignis)


def test_folgen_des_mandatsendes_stehen_gemeinsam_oder_gar_nicht(mandat):
    """Scheitert der Audit-Eintrag zum Ende der Sitzung, bleibt auch die Absage des Termins nicht stehen."""
    from unittest import mock

    from django.db import IntegrityError

    from mandatare.models import Sitzung
    from mandatare.sitzung import ANLASS_MANDATSENDE, mandatsende_folgen

    termin = _termin(mandat)
    sitzung = _laufende_sitzung(mandat)
    echt = AuditEintrag.anhaengen

    def nur_die_absage(ereignis, *args, **kwargs):
        if ereignis.get("typ") == "sitzung_beendet":
            raise IntegrityError("Audit scheitert")
        return echt(ereignis, *args, **kwargs)

    with mock.patch.object(AuditEintrag, "anhaengen", side_effect=nur_die_absage), pytest.raises(IntegrityError):
        mandatsende_folgen(mandat, ANLASS_MANDATSENDE)
    termin.refresh_from_db()
    assert termin.abgesagt_am is None and not _absagen_audit()
    assert Sitzung.objects.get(pk=sitzung.pk).ende is None


def test_eine_gleichzeitig_beendete_sitzung_bricht_das_mandatsende_nicht_ab(mandat, monkeypatch):
    """GP-116, Wettlauf: Der Mandatar beendet seine Sitzung genau, während das Mandat endet. Die Plattform
    findet sie dann schon beendet — das Ziel ist erreicht, die Absage der Termine bleibt stehen."""
    from mandatare import sitzung as sitzung_modul
    from mandatare.models import Sitzung
    from mandatare.sitzung import ANLASS_MANDATSENDE, mandatsende_folgen

    termin = _termin(mandat)
    sitzung = _laufende_sitzung(mandat)
    echt = sitzung_modul.sitzung_beenden

    def wettlauf(s, jetzt=None, anlass=""):
        echt(Sitzung.objects.get(pk=s.pk), jetzt)  # der Mandatar war einen Augenblick schneller
        return echt(s, jetzt, anlass=anlass)

    monkeypatch.setattr(sitzung_modul, "sitzung_beenden", wettlauf)
    mandatsende_folgen(Mandat.objects.get(pk=mandat.pk), ANLASS_MANDATSENDE)
    termin.refresh_from_db()
    assert termin.abgesagt_am is not None and [e["anlass"] for e in _absagen_audit()] == ["mandat_beendet"]
    assert not Sitzung.objects.get(pk=sitzung.pk).laeuft()
    beendet = [e.ereignis for e in AuditEintrag.objects.filter(ereignis__typ="sitzung_beendet").order_by("lfd")]
    assert len(beendet) == 1 and "anlass" not in beendet[0]  # beendet hat der Mandatar, einmal


def test_ein_anderer_fehler_beim_beenden_bleibt_ein_fehler(mandat, monkeypatch):
    """Nur der Wettlauf wird abgefangen: Läuft die Sitzung nach dem Fehler noch, bricht das Mandatsende ab,
    und auch die Absage der Termine bleibt nicht stehen."""
    from mandatare import sitzung as sitzung_modul
    from mandatare.models import Sitzung
    from mandatare.sitzung import ANLASS_MANDATSENDE, SitzungFehler, mandatsende_folgen

    termin = _termin(mandat)
    sitzung = _laufende_sitzung(mandat)

    def scheitert(*args, **kwargs):
        raise SitzungFehler("anderer Fehler")

    monkeypatch.setattr(sitzung_modul, "sitzung_beenden", scheitert)
    with pytest.raises(SitzungFehler):
        mandatsende_folgen(Mandat.objects.get(pk=mandat.pk), ANLASS_MANDATSENDE)
    termin.refresh_from_db()
    assert termin.abgesagt_am is None and not _absagen_audit()
    assert Sitzung.objects.get(pk=sitzung.pk).laeuft()
