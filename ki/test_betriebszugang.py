from concurrent.futures import ThreadPoolExecutor
from threading import Event

import pytest
from django.db import OperationalError, close_old_connections, connections

from ki.anbieter import AnbieterFehler, Antwort, AttrappenAnbieter, Einbettung, SteckplatzStumm
from ki.betriebszugang import _sperrkonflikt
from ki.models import KILauf, SteckplatzZugang, Zweck, einbettung_ausfuehren, lauf_ausfuehren
from ki.test_kontext_auftrag import a  # noqa: F401
from ki.warteschlange import HOECHSTVERSUCHE, auftrag_ausfuehren, einreihen
from parameter.models import Parameter
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def _konto(settings):
    settings.DDOE_KI_ANBIETER = "attrappe"
    return mitglied_anlegen("zugang-gegenprobe")


def _aufrufen(art, konto):
    if art == "text":
        return lauf_ausfuehren(Zweck.EINSCHAETZUNG, "synthetischer Auftrag", "synthetische Eingabe", konto)
    return einbettung_ausfuehren(["synthetische Eingabe"], konto)


@pytest.mark.parametrize("aussen,innen", [("text", "text"), ("text", "vektor"), ("vektor", "text"), ("vektor", "vektor")])
def test_text_und_einbettung_teilen_den_zugang_und_das_gerade_verbrauchte_budget(settings, monkeypatch, aussen, innen):
    m = _konto(settings)
    Parameter.objects.update_or_create(schluessel="ki-monatstokens", defaults={"wert": "5", "beschreibung": "Test", "quelle": "Test"})
    gestartet = []
    def antwort(art):
        gestartet.append(art)
        if len(gestartet) == 1:
            with pytest.raises(SteckplatzStumm, match="belegt"):
                _aufrufen(innen, m)
            # Das abgewiesene innere Fenster darf den äußeren Zugang nicht freigeben.
            assert SteckplatzZugang.objects.get(name="anbieter").belegt
        return Antwort("Test", "kein-echter-anbieter", 3, 2) if art == "text" else Einbettung([[1.0]], "kein-echter-anbieter", 5)
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: antwort("text"))
    monkeypatch.setattr(AttrappenAnbieter, "einbetten", lambda *args, **kwargs: antwort("vektor"))
    _aufrufen(aussen, m)
    assert gestartet == [aussen] and KILauf.monatsverbrauch() == 5
    assert not SteckplatzZugang.objects.get(name="anbieter").belegt
    with pytest.raises(SteckplatzStumm, match="Monats-Tokenbudget"):
        _aufrufen(innen, m)
    assert gestartet == [aussen] and KILauf.objects.count() == 1


def test_anbieterfehler_bleibt_archiviert_und_gibt_den_zugang_wieder_frei(settings, monkeypatch):
    m = _konto(settings)
    original = AttrappenAnbieter.frage
    def kaputt(*args):
        raise AnbieterFehler("synthetischer Ausfall")
    monkeypatch.setattr(AttrappenAnbieter, "frage", kaputt)
    with pytest.raises(SteckplatzStumm, match="nicht geantwortet"):
        _aufrufen("text", m)
    assert KILauf.objects.count() == 1 and not KILauf.objects.get().erfolgreich
    assert not SteckplatzZugang.objects.get(name="anbieter").belegt
    monkeypatch.setattr(AttrappenAnbieter, "frage", original)
    _aufrufen("text", m)
    assert KILauf.objects.filter(erfolgreich=True).count() == 1


@pytest.mark.parametrize("fehler", [RuntimeError("Testabbruch"), OperationalError("synthetischer Datenbankausfall")])
def test_unerwartete_fehler_werden_nicht_als_budgetstille_versteckt(settings, monkeypatch, fehler):
    m = _konto(settings)
    def kaputt(*args):
        raise fehler
    monkeypatch.setattr(AttrappenAnbieter, "frage", kaputt)
    with pytest.raises(type(fehler), match=str(fehler)):
        _aufrufen("text", m)
    assert not SteckplatzZugang.objects.get(name="anbieter").belegt
    assert not KILauf.objects.exists()


@pytest.mark.parametrize("code,pg,erwartet", [(5, None, True), (6, None, True), (262, None, True), (1, None, False),
    (None, "55P03", True), (None, "08006", False), (None, None, False)])
def test_nur_tatsaechliche_sperrkonflikte_erhalten_einen_stumm_rueckfall(code, pg, erwartet):
    class Ursache(Exception):
        sqlite_errorcode = code
        sqlstate = pg
    e = OperationalError("Test")
    e.__cause__ = Ursache()
    assert _sperrkonflikt(e) is erwartet


@pytest.mark.django_db(transaction=True)
def test_zwei_echte_verbindungen_starten_keine_parallelen_anbieter(settings, monkeypatch):
    m = _konto(settings)
    SteckplatzZugang.objects.get_or_create(name="anbieter")
    begonnen, freigabe = Event(), Event()
    gestartet = []
    def frage(*args):
        gestartet.append("text")
        begonnen.set()
        assert freigabe.wait(8), "Test muss die Attrappe wieder freigeben"
        return Antwort("Test", "kein-echter-anbieter", 3, 2)
    monkeypatch.setattr(AttrappenAnbieter, "frage", frage)
    monkeypatch.setattr(AttrappenAnbieter, "einbetten", lambda *args, **kw: pytest.fail("Besetzter Zugang rief zweiten Anbieter auf"))
    def erster():
        close_old_connections()
        try:
            return _aufrufen("text", m).pk
        finally:
            connections.close_all()
    with ThreadPoolExecutor(max_workers=1) as pool:
        lauf = pool.submit(erster)
        try:
            assert begonnen.wait(8), "Erste Attrappe wurde nicht gestartet"
            with pytest.raises(SteckplatzStumm, match="belegt"):
                _aufrufen("vektor", m)
        finally:
            freigabe.set()
        assert lauf.result(timeout=8)
    assert gestartet == ["text"] and KILauf.objects.count() == 1
    assert not SteckplatzZugang.objects.get(name="anbieter").belegt


def test_belegter_zugang_verbraucht_auch_bei_wiederholung_keine_versuche(a, monkeypatch):  # noqa: F811
    j = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    SteckplatzZugang.objects.update_or_create(name="anbieter", defaults={"belegt": True})
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *a: pytest.fail("Kein Anbieter bei belegtem Zugang"))
    for _ in range(HOECHSTVERSUCHE + 1):
        assert auftrag_ausfuehren(j.pk) == "verschoben"
        j.refresh_from_db()
        assert j.versuche == 0 and j.status == "geplant" and j.naechster_versuch is None
        assert j.lauf_id is None
    assert not KILauf.objects.exists()


def test_zwischenzeitlich_erschoepftes_budget_laesst_auftrag_ohne_fehlversuch_warten(a, monkeypatch):  # noqa: F811
    j = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    Parameter.objects.update_or_create(schluessel="ki-monatstokens", defaults={"wert": "0", "beschreibung": "Test", "quelle": "Test"})
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *a: pytest.fail("Kein Anbieter bei Budget0"))
    assert auftrag_ausfuehren(j.pk) == "verschoben"
    j.refresh_from_db()
    assert j.versuche == 0 and j.status == "geplant"
    assert not KILauf.objects.exists()
