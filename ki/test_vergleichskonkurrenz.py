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
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = pytest.mark.django_db(transaction=True)


def test_zwei_verbindungen_starten_keinen_zweiten_anbieter(lage, modell, monkeypatch):
    args = anfrage(lage)
    SteckplatzZugang.objects.get_or_create(name="anbieter")
    start, anderer_beendet = Barrier(2), Event()
    original = AttrappenAnbieter.frage

    def warten(self, auftrag, eingabe, zeitgrenze=None):
        assert anderer_beendet.wait(10), "Die andere Anforderung muss ohne zweiten Anbieter enden."
        return original(self, auftrag, eingabe, zeitgrenze=zeitgrenze)

    monkeypatch.setattr(AttrappenAnbieter, "frage", warten)

    def post():
        connections.close_all()
        try:
            start.wait(timeout=10)
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
            anderer_beendet.set()
            connections.close_all()

    with ThreadPoolExecutor(max_workers=2) as pool:
        arbeiten = [pool.submit(post) for _ in range(2)]
        staende = [a.result(timeout=20) for a in arbeiten]
    assert "fertig" in staende and len(modell) == 1
    assert KILauf.objects.filter(zweck=Zweck.GEGENUEBERSTELLUNG).count() == 1
