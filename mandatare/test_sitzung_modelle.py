"""Die Fachoperationen des Sitzungsmodus (FB-L5): Beginn nur am Sitzungstag, append-only Punkte und
Meldungen, Berichtigung als neue Meldung, Ende einmal, Höchstdauer lazy — jede Handlung auditiert."""

from datetime import date, datetime, time, timedelta

import pytest
from django.db import IntegrityError, transaction
from django.db.models import ProtectedError
from django.utils import timezone

from mandatare.models import Aufgabe, Livemeldung, Sitzung, Tagesordnungspunkt
from mandatare.sitzung import (
    SitzungFehler,
    darf_live_melden,
    meldung_abgeben,
    punkt_anhaengen,
    punkt_verknuepfen,
    sitzung_beenden,
    sitzung_beginnen,
    stream_pruefen,
    stream_setzen,
)
from mandatare.test_mandatare import mandat_anlegen
from parameter.models import Parameter, erstbestand_sicherstellen
from verfahren.models import AuditEintrag, antrag_einbringen
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def wiener(tag: date, stunde: int = 18, minute: int = 0):
    return timezone.make_aware(datetime.combine(tag, time(stunde, minute)))


def sitzungstag(mandat, tag: date | None = None, titel="Gemeinderatssitzung") -> Aufgabe:
    tag = tag or timezone.localdate()
    return Aufgabe.objects.create(mandat=mandat, titel=titel, frist=wiener(tag, 23, 59), sitzungstag=True)


def typen(typ: str) -> list[dict]:
    """Die Audit-Ereignisse eines Typs ohne den Zeitstempel, den `anhaengen` setzt."""
    return [{k: v for k, v in e.ereignis.items() if k != "zeit"} for e in AuditEintrag.objects.filter(ereignis__typ=typ)]


@pytest.fixture
def mandat():
    return mandat_anlegen(mitglied_anlegen("anna"))


@pytest.fixture
def sitzung(mandat):
    return sitzung_beginnen(mandat, sitzungstag(mandat), punkte=["Budget 2027", "Radweg"])


# ── Beginn ────────────────────────────────────────────────────────────────────────────────


def test_beginn_legt_sitzung_und_tagesordnung_an(mandat):
    aufgabe = sitzungstag(mandat)
    s = sitzung_beginnen(mandat, aufgabe, stream="https://www.parlament.gv.at/live", punkte=["A", " ", "B"])
    assert s.laeuft() and s.aufgabe == aufgabe and s.stream.startswith("https://")
    assert [(p.nummer, p.titel) for p in s.punkte.all()] == [(1, "A"), (2, "B")]
    assert typen("sitzung_begonnen") == [
        {"typ": "sitzung_begonnen", "mandat": mandat.pk, "sitzung": s.pk, "aufgabe": aufgabe.pk, "punkte": 2}
    ]


def test_beginn_nur_am_sitzungstag(mandat):
    morgen = sitzungstag(mandat, timezone.localdate() + timedelta(days=1))
    gestern = sitzungstag(mandat, timezone.localdate() - timedelta(days=1))
    for aufgabe in (morgen, gestern):
        with pytest.raises(SitzungFehler):
            sitzung_beginnen(mandat, aufgabe)
    ohne = Aufgabe.objects.create(mandat=mandat, titel="kein Sitzungstag", frist=wiener(timezone.localdate()))
    with pytest.raises(SitzungFehler):
        sitzung_beginnen(mandat, ohne)
    assert not Sitzung.objects.exists() and not typen("sitzung_begonnen")


def test_beginn_nur_eigene_aufgabe(mandat):
    fremd = mandat_anlegen(mitglied_anlegen("bernd"))
    with pytest.raises(SitzungFehler):
        sitzung_beginnen(mandat, sitzungstag(fremd))


def test_ein_sitzungstag_eine_sitzung(mandat):
    aufgabe = sitzungstag(mandat)
    s = sitzung_beginnen(mandat, aufgabe)
    sitzung_beenden(s)
    with pytest.raises(SitzungFehler):
        sitzung_beginnen(mandat, aufgabe)


def test_keine_zweite_laufende_sitzung(mandat):
    sitzung_beginnen(mandat, sitzungstag(mandat))
    with pytest.raises(SitzungFehler):
        sitzung_beginnen(mandat, sitzungstag(mandat, titel="Ausschuss"))


def test_ruhende_befugnis_und_beendetes_mandat_schreiben_nicht(mandat):
    """§ 7 Abs 10 lit f Z 6 und Z 8: dieselbe Bedingung wie für die Mandatsfrage."""
    aufgabe = sitzungstag(mandat)
    mandat.vertrauen_entzogen_am = timezone.now()
    mandat.save()
    assert not darf_live_melden(mandat)
    with pytest.raises(SitzungFehler):
        sitzung_beginnen(mandat, aufgabe)
    mandat.vertrauen_entzogen_am = None
    mandat.vertretung_beendet_am = timezone.localdate()
    mandat.save()
    with pytest.raises(SitzungFehler):
        sitzung_beginnen(mandat, aufgabe)
    mandat.vertretung_beendet_am = None
    mandat.beendet = timezone.localdate()
    mandat.save()
    with pytest.raises(SitzungFehler):
        sitzung_beginnen(mandat, aufgabe)


def test_stream_nur_https():
    assert stream_pruefen("") == ""
    assert stream_pruefen(" https://tv.example.org/x ") == "https://tv.example.org/x"
    for falsch in ("http://tv.example.org", "javascript:alert(1)", "https://", "ftp://x", "https://x/" + "a" * 600):
        with pytest.raises(SitzungFehler):
            stream_pruefen(falsch)


def test_zu_viele_punkte(mandat):
    with pytest.raises(SitzungFehler):
        sitzung_beginnen(mandat, sitzungstag(mandat), punkte=[f"P{i}" for i in range(61)])


# ── Punkte und Meldungen ──────────────────────────────────────────────────────────────────


def test_punkt_anhaengen_zaehlt_weiter(sitzung):
    p = punkt_anhaengen(sitzung, "Allfälliges")
    assert p.nummer == 3
    with pytest.raises(SitzungFehler):
        punkt_anhaengen(sitzung, "   ")
    assert typen("tagesordnungspunkt")[0]["punkt"] == p.pk


def test_punkt_verknuepfen_einmal(sitzung, ordnung):  # noqa: F811
    punkt = sitzung.punkte.get(nummer=1)
    antrag = antrag_einbringen(sitzung.mandat.mitglied, "Budget 2027", "Das Budget wird beschlossen.", "", ordnung)
    punkt_verknuepfen(punkt, antrag)
    punkt.refresh_from_db()
    assert punkt.antrag == antrag
    with pytest.raises(SitzungFehler):
        punkt_verknuepfen(punkt, antrag)
    assert typen("tagesordnungspunkt_verknuepft") == [
        {"typ": "tagesordnungspunkt_verknuepft", "mandat": sitzung.mandat_id, "sitzung": sitzung.pk,
         "punkt": punkt.pk, "antrag": antrag.pk}
    ]


def test_meldung_und_berichtigung(sitzung):
    punkt = sitzung.punkte.get(nummer=1)
    alt = meldung_abgeben(sitzung, "Ich stimme dafür.", punkt, "dafuer")
    neu = meldung_abgeben(sitzung, "Korrektur: dagegen, abgestimmt.", punkt, "dagegen", True, berichtigt=alt)
    assert neu.berichtigt == alt and alt.berichtigung == neu
    assert Livemeldung.objects.count() == 2  # die alte bleibt stehen
    with pytest.raises(SitzungFehler):
        meldung_abgeben(sitzung, "noch eine Korrektur", punkt, berichtigt=alt)
    # die Berichtigung lässt sich wieder berichtigen
    meldung_abgeben(sitzung, "Enthalten, abgestimmt.", punkt, "enthalten", True, berichtigt=neu)
    ereignisse = typen("livemeldung")
    assert [e.get("berichtigt") for e in ereignisse] == [None, alt.pk, neu.pk]
    assert all("text" not in e for e in ereignisse)  # das Audit trägt nie Inhalte


@pytest.mark.parametrize(
    ("text", "stimme", "abgestimmt"),
    [("", "", False), ("x" * 281, "", False), ("ok", "vielleicht", False), ("ok", "", True)],
)
def test_meldung_pruefungen(sitzung, text, stimme, abgestimmt):
    with pytest.raises(SitzungFehler):
        meldung_abgeben(sitzung, text, stimme=stimme, abgestimmt=abgestimmt)
    assert not Livemeldung.objects.exists()


def test_meldung_nur_zu_punkten_und_meldungen_derselben_sitzung(sitzung, mandat):
    fremd_mandat = mandat_anlegen(mitglied_anlegen("dora"))
    fremd = sitzung_beginnen(fremd_mandat, sitzungstag(fremd_mandat), punkte=["X"])
    with pytest.raises(SitzungFehler):
        meldung_abgeben(sitzung, "falscher Punkt", fremd.punkte.first())
    fremde_meldung = meldung_abgeben(fremd, "dort")
    with pytest.raises(SitzungFehler):
        meldung_abgeben(sitzung, "falsche Berichtigung", berichtigt=fremde_meldung)


def test_zeichengrenze_280(sitzung):
    assert meldung_abgeben(sitzung, "x" * 280).text == "x" * 280


# ── Ende, Höchstdauer, Schutz ─────────────────────────────────────────────────────────────


def test_ende_einmal_danach_nichts_mehr(sitzung):
    sitzung_beenden(sitzung)
    sitzung.refresh_from_db()
    assert not sitzung.laeuft() and sitzung.ende is not None and not sitzung.ende_durch_hoechstdauer
    for handlung in (
        lambda: sitzung_beenden(sitzung),
        lambda: meldung_abgeben(sitzung, "zu spät"),
        lambda: punkt_anhaengen(sitzung, "zu spät"),
        lambda: stream_setzen(sitzung, "https://x.example.org"),
    ):
        with pytest.raises(SitzungFehler):
            handlung()
    assert len(typen("sitzung_beendet")) == 1


def test_beenden_auch_bei_ruhender_befugnis(sitzung, mandat):
    mandat.vertrauen_entzogen_am = timezone.now()
    mandat.save()
    with pytest.raises(SitzungFehler):
        meldung_abgeben(sitzung, "ruht")
    sitzung_beenden(sitzung)
    assert not Sitzung.objects.get(pk=sitzung.pk).laeuft()


def test_hoechstdauer_beendet_lazy_mit_audit(sitzung):
    erstbestand_sicherstellen()
    Parameter.objects.filter(schluessel="live-hoechstdauer-stunden").update(wert="2")
    spaeter = sitzung.beginn + timedelta(hours=2, minutes=1)
    assert not sitzung.laeuft(spaeter)
    with pytest.raises(SitzungFehler):
        meldung_abgeben(sitzung, "nach der Höchstdauer", jetzt=spaeter)
    assert sitzung.fortschreiben(spaeter) is True
    assert sitzung.fortschreiben(spaeter) is False  # idempotent
    sitzung.refresh_from_db()
    assert sitzung.ende == sitzung.beginn + timedelta(hours=2) and sitzung.ende_durch_hoechstdauer
    assert typen("sitzung_beendet") == [
        {"typ": "sitzung_beendet", "mandat": sitzung.mandat_id, "sitzung": sitzung.pk, "grund": "hoechstdauer"}
    ]


def test_hoechstdauer_ist_geklemmt(sitzung):
    erstbestand_sicherstellen()
    Parameter.objects.filter(schluessel="live-hoechstdauer-stunden").update(wert="0")
    assert sitzung.laeuft(sitzung.beginn + timedelta(minutes=59))
    Parameter.objects.filter(schluessel="live-hoechstdauer-stunden").update(wert="1000")
    assert not sitzung.laeuft(sitzung.beginn + timedelta(hours=72))


def test_alle_fortschreiben(sitzung):
    assert Sitzung.alle_fortschreiben(sitzung.beginn + timedelta(hours=1)) == 0
    assert Sitzung.alle_fortschreiben(sitzung.beginn + timedelta(hours=19)) == 1


def test_stream_setzen(sitzung):
    stream_setzen(sitzung, "https://tv.example.org/gemeinderat")
    assert Sitzung.objects.get(pk=sitzung.pk).stream == "https://tv.example.org/gemeinderat"
    assert typen("sitzung_stream")


def test_nichts_laesst_sich_loeschen(sitzung):
    """Grundregel 7: Sitzungstag, Sitzung, Punkt und berichtigte Meldung sind gegen Löschen geschützt —
    einen Löschweg gibt es ohnehin nicht, die Datenbank hält zusätzlich stand."""
    alt = meldung_abgeben(sitzung, "bleibt", sitzung.punkte.first())
    meldung_abgeben(sitzung, "berichtigt", sitzung.punkte.first(), berichtigt=alt)
    for objekt in (sitzung.aufgabe, sitzung, sitzung.punkte.first(), alt, sitzung.mandat):
        with pytest.raises(ProtectedError), transaction.atomic():
            objekt.delete()


def test_punktnummer_eindeutig(sitzung):
    with pytest.raises(IntegrityError), transaction.atomic():
        Tagesordnungspunkt.objects.create(sitzung=sitzung, nummer=1, titel="doppelt")
