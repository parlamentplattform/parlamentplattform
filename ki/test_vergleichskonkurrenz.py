"""Zwei echte Verbindungen verwenden dieselbe ausdrückliche Anforderung nur einmal."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event

import pytest
from django.db import OperationalError, connections

from ki.anbieter import AttrappenAnbieter
from ki.betriebszugang import _sperrkonflikt
from ki.gegenueberstellungen import anfordern
from ki.models import KILauf, SteckplatzZugang, Zweck
from ki.test_gegenueberstellungen import anfrage, modell  # noqa: F401
from ki.test_vergleichskontext import lage  # noqa: F401
from ki.vergleichsanfragen import anlegen, kennung_lesen, reservieren
from ki.vergleichskontext import festhalten
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = pytest.mark.django_db(transaction=True)


def test_zwei_verbindungen_starten_keinen_zweiten_anbieter(lage, modell, monkeypatch):
    args = anfrage(lage)
    SteckplatzZugang.objects.get_or_create(name="anbieter")
    begonnen, anderer_beendet = Event(), Event()
    begonnene_aufrufe = []
    original = AttrappenAnbieter.frage

    def warten(self, auftrag, eingabe, zeitgrenze=None):
        begonnene_aufrufe.append(1)
        begonnen.set()
        assert anderer_beendet.wait(10), "Die andere Anforderung muss ohne zweiten Anbieter enden."
        return original(self, auftrag, eingabe, zeitgrenze=zeitgrenze)

    monkeypatch.setattr(AttrappenAnbieter, "frage", warten)

    def post(meldet_ende):
        connections.close_all()
        try:
            try:
                return anfordern(*args).status
            except OperationalError as e:
                # SQLite kann schon bei der einmaligen Reservierung ablehnen.
                # Die HTTP-Schicht rendert dann das erhaltene Formular. Andere
                # Datenbankfehler nicht als erfolgreichen Zugriffsschutz ausgeben.
                if not _sperrkonflikt(e):
                    raise
                return "datenbank_belegt"
        finally:
            if meldet_ende:
                anderer_beendet.set()
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        erster = pool.submit(post, False)
        assert begonnen.wait(10), "Die erste Anforderung muss tatsächlich den Anbieter erreichen."
        arbeiten = [erster, pool.submit(post, True)]
        staende = [a.result(timeout=20) for a in arbeiten]
    assert "fertig" in staende and len(modell) == 1 and len(begonnene_aufrufe) == 1
    assert KILauf.objects.filter(zweck=Zweck.GEGENUEBERSTELLUNG).count() == 1


def test_zwei_verbindungen_reservieren_dieselbe_anforderung_nur_einmal(lage):
    daten, mitglied, stand, token = anfrage(lage)
    kennung = kennung_lesen(token, daten, mitglied, stand)
    kontext = festhalten(daten, mitglied, stand, hoechstzeichen=20000, hoechstpaare=3)
    a, _ = anlegen(kennung, kontext, mitglied)
    start = Barrier(2)

    def versuchen():
        connections.close_all()
        try:
            start.wait(timeout=10)
            try:
                return reservieren(a, mitglied)
            except OperationalError as e:
                if not _sperrkonflikt(e):
                    raise
                return False
        finally:
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        arbeiten = [pool.submit(versuchen) for _ in range(2)]
        reserviert = [arbeit.result(timeout=20) for arbeit in arbeiten]
    assert reserviert.count(True) == 1
    a.refresh_from_db()
    assert a.status == "laeuft" and a.begonnen_am is not None and a.lauf_id is None
    assert not KILauf.objects.filter(zweck=Zweck.GEGENUEBERSTELLUNG).exists()
