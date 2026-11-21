"""Sperrreihenfolge zwischen Mandatsende und laufender Livemeldung (Nebenläufigkeits-Fund, GP-116).

Eine Livemeldung sperrt zuerst die Sitzung und hängt dann an die Audit-Kette an. Das Mandatsende und das
Ende der Vertretung beenden die Sitzung erst nach ihrem ersten Audit-Eintrag; sperrten sie die Sitzung
erst dann, warteten beide aufeinander (PostgreSQL bricht eine Seite mit „deadlock detected“ ab). Darum
sperren sie die offenen Sitzungen vor dem ersten Eintrag, und die Livemeldung sperrt nur die Sitzung,
nicht zusätzlich das Mandat. Die Reihenfolge prüft der erste Test überall, das Warten selbst nur
PostgreSQL (Job `pruefen_postgres`)."""

import threading
import time

import pytest
from django.db import connection, connections
from django.test import Client
from django.urls import reverse

# Das Einmal-Token-Modell liegt in `mitglieder.auth_flows`, nicht in `models.py`; ohne diesen
# Import kennt der Flush der transaktionalen Tests die Tabelle nicht und scheitert am Fremdschlüssel.
import mitglieder.auth_flows  # noqa: F401
from mandatare import sitzung as sitzung_modul
from mandatare.models import Livemeldung, Mandat, Sitzung
from mandatare.sitzung import SitzungFehler, meldung_abgeben, sitzung_beginnen
from mandatare.test_mandatare import admin_anlegen, mandat_anlegen
from mandatare.test_sitzung_modelle import sitzungstag
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen

POSTGRES = pytest.mark.skipif(connection.vendor != "postgresql", reason="Zeilensperren wirken nur auf PostgreSQL")


def _laufend():
    mandat = mandat_anlegen(mitglied_anlegen("live"))
    return mandat, sitzung_beginnen(mandat, sitzungstag(mandat), punkte=["Budget"])


@pytest.mark.django_db
def test_das_mandatsende_sperrt_die_sitzung_vor_seinem_ersten_audit_eintrag(client, monkeypatch):
    mandat, sitzung = _laufend()
    folge = []
    echt_sperren, echt_anhaengen = sitzung_modul.sitzungen_sperren, AuditEintrag.anhaengen

    def sperren(m):
        folge.append("sperren")
        return echt_sperren(m)

    def anhaengen(ereignis, *args, **kwargs):
        folge.append(ereignis.get("typ"))
        return echt_anhaengen(ereignis, *args, **kwargs)

    monkeypatch.setattr(sitzung_modul, "sitzungen_sperren", sperren)
    monkeypatch.setattr(AuditEintrag, "anhaengen", anhaengen)
    client.force_login(admin_anlegen("sperrfolge"))
    client.post(reverse("mandatare:verwaltung_aktion"), {"aktion": "beenden", "mandat": mandat.pk})
    assert folge[0] == "sperren" and "mandat_beendet" in folge and "sitzung_beendet" in folge
    assert not Sitzung.objects.get(pk=sitzung.pk).laeuft()


@pytest.mark.django_db
def test_das_ende_der_vertretung_sperrt_die_sitzung_vor_seinem_ersten_audit_eintrag(monkeypatch):
    from datetime import timedelta

    from django.utils import timezone

    from mandatare import models as mm
    from plattform_core import Phase
    from verfahren.models import Antrag, Antragsart

    mandat, sitzung = _laufend()
    ende = timezone.now() - timedelta(days=40)
    antrag = Antrag.objects.create(titel="Vertrauensfrage", art=Antragsart.VERTRAUENSFRAGE, eingebracht_von=mandat.mitglied,
                                   eingebracht_am=ende - timedelta(days=20), phase=Phase.ANGENOMMEN.value, phase_beginn=ende,
                                   policy_snapshot={})
    vf = mm.Vertrauensfrage.objects.create(antrag=antrag, mandat=mandat)
    mm.vertrauensfrage_wirkungen(vf, jetzt=ende)
    folge = []
    echt_sperren, echt_anhaengen = sitzung_modul.sitzungen_sperren, AuditEintrag.anhaengen
    monkeypatch.setattr(sitzung_modul, "sitzungen_sperren", lambda m: folge.append("sperren") or echt_sperren(m))
    monkeypatch.setattr(
        AuditEintrag, "anhaengen", lambda e, *a, **k: folge.append(e.get("typ")) or echt_anhaengen(e, *a, **k)
    )
    mm.vertrauensfragen_fortschreiben()
    assert folge[0] == "sperren" and "vertretung_beendet" in folge
    assert not Sitzung.objects.get(pk=sitzung.pk).laeuft()


@pytest.mark.django_db
def test_gesperrt_wird_erst_das_mandat_dann_die_sitzung():
    """Gegenlesen: `sitzung_beginnen` sperrt das Mandat und danach (über `Sitzung.fortschreiben`) eine
    überfällige offene Sitzung. Sperrte das Mandatsende erst die Sitzungen und schriebe dann das Mandat,
    warteten beide aufeinander. Darum nimmt `sitzungen_sperren` dieselbe Folge: Mandat, dann Sitzungen."""
    from django.test.utils import CaptureQueriesContext

    mandat, _sitzung = _laufend()
    with CaptureQueriesContext(connection) as abfragen:
        sitzung_modul.sitzungen_sperren(mandat)
    sql = [a["sql"] for a in abfragen]
    assert len(sql) == 2
    assert f'FROM "{Mandat._meta.db_table}"' in sql[0] and Sitzung._meta.db_table not in sql[0]
    assert f'FROM "{Sitzung._meta.db_table}"' in sql[1]
    if connection.features.has_select_for_update:
        assert all("FOR UPDATE" in s for s in sql)


def _faden(ziel, fehler):
    def lauf():
        try:
            ziel()
        except Exception as e:  # noqa: BLE001 — der Test berichtet jeden Fehler des Fadens
            fehler.append(e)
        finally:
            connections.close_all()

    return threading.Thread(target=lauf)


def _beenden(admin, mandat):
    c = Client()
    c.force_login(admin)
    antwort = c.post(reverse("mandatare:verwaltung_aktion"), {"aktion": "beenden", "mandat": mandat.pk})
    assert antwort.status_code == 302


@POSTGRES
@pytest.mark.django_db(transaction=True)
def test_mandatsende_zuerst_verklemmt_sich_nicht_mit_einer_livemeldung(monkeypatch):
    """Das Mandatsende hat seinen Eintrag geschrieben und hält inne; die Livemeldung kommt dazwischen."""
    mandat, sitzung = _laufend()
    admin = admin_anlegen("sperrfolge1")
    eingetragen = threading.Event()
    echt = AuditEintrag.anhaengen

    def anhaengen(ereignis, *args, **kwargs):
        eintrag = echt(ereignis, *args, **kwargs)
        if ereignis.get("typ") == "mandat_beendet":
            eingetragen.set()
            time.sleep(0.8)  # die Livemeldung soll jetzt ihre Sperren nehmen
        return eintrag

    monkeypatch.setattr(AuditEintrag, "anhaengen", anhaengen)
    fehler_ende, fehler_live = [], []

    def melden():
        assert eingetragen.wait(10)
        try:
            meldung_abgeben(Sitzung.objects.get(pk=sitzung.pk), "Abstimmung läuft.")
        except SitzungFehler:
            pass  # die Sitzung ist inzwischen beendet — das ist kein Verklemmen

    faeden = [_faden(lambda: _beenden(admin, mandat), fehler_ende), _faden(melden, fehler_live)]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join(30)
    assert fehler_ende == [] and fehler_live == [], (fehler_ende, fehler_live)
    assert Mandat.objects.get(pk=mandat.pk).beendet is not None
    assert not Sitzung.objects.get(pk=sitzung.pk).laeuft()


@POSTGRES
@pytest.mark.django_db(transaction=True)
def test_livemeldung_zuerst_verklemmt_sich_nicht_mit_dem_mandatsende(monkeypatch):
    """Die Livemeldung hält die Sitzung und hält inne; das Mandatsende kommt dazwischen."""
    mandat, sitzung = _laufend()
    admin = admin_anlegen("sperrfolge2")
    gesperrt = threading.Event()
    echt = sitzung_modul._gesperrt

    def langsam(s, jetzt):
        frisch = echt(s, jetzt)
        gesperrt.set()
        time.sleep(0.8)  # das Mandatsende soll jetzt beginnen
        return frisch

    monkeypatch.setattr(sitzung_modul, "_gesperrt", langsam)
    fehler_ende, fehler_live = [], []

    def beenden():
        assert gesperrt.wait(10)
        _beenden(admin, mandat)

    faeden = [_faden(lambda: meldung_abgeben(Sitzung.objects.get(pk=sitzung.pk), "Abstimmung läuft."), fehler_live),
              _faden(beenden, fehler_ende)]
    for f in faeden:
        f.start()
    for f in faeden:
        f.join(30)
    assert fehler_ende == [] and fehler_live == [], (fehler_ende, fehler_live)
    assert Livemeldung.objects.filter(sitzung=sitzung).count() == 1
    assert not Sitzung.objects.get(pk=sitzung.pk).laeuft()
