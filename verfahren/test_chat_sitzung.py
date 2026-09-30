"""Der Chat einer Sitzung (FB-L5): derselbe Beitrag mit Bezug auf die Sitzung statt auf einen Antrag —
genau ein Bezug, offen solange die Sitzung läuft (E1), Fragen als beantwortet markierbar, nicht in den
Gesprächen der Anträge."""

from datetime import timedelta

import pytest
from django.db import IntegrityError, transaction
from django.utils import timezone

from mandatare.sitzung import sitzung_beenden, sitzung_beginnen
from mandatare.test_mandatare import mandat_anlegen
from mandatare.test_sitzung_modelle import sitzungstag
from verfahren.chat import (
    ChatGesperrt,
    als_beantwortet_markieren,
    beitrag_schreiben,
    gespraeche,
    sitzung_beitrag_schreiben,
    sitzung_chat_offen,
    sitzung_faden,
    sitzung_gelesen_merken,
)
from verfahren.models import AuditEintrag, Kommentar, Lesestand, antrag_einbringen
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def sitzung():
    mandat = mandat_anlegen(mitglied_anlegen("anna"))
    return sitzung_beginnen(mandat, sitzungstag(mandat), punkte=["Budget"])


def test_beitrag_und_antwort(sitzung):
    bernd, cora = mitglied_anlegen("bernd"), mitglied_anlegen("cora")
    frage = sitzung_beitrag_schreiben(sitzung, bernd, "  Wie stimmen Sie zum Budget?  ")
    antwort = sitzung_beitrag_schreiben(sitzung, cora, "Das frage ich mich auch.", frage)
    weitere = sitzung_beitrag_schreiben(sitzung, bernd, "Und zur Antwort darauf?", antwort)
    assert frage.sitzung == sitzung and frage.antrag is None and frage.phase == "sitzung"
    assert frage.text == "Wie stimmen Sie zum Budget?"
    assert antwort.antwort_auf == frage and weitere.antwort_auf == frage  # eine Ebene tief
    with pytest.raises(ValueError):
        sitzung_beitrag_schreiben(sitzung, bernd, "   ")


def test_antwort_nur_in_derselben_sitzung(sitzung, ordnung):  # noqa: F811
    andere_mandat = mandat_anlegen(mitglied_anlegen("dora"))
    andere = sitzung_beginnen(andere_mandat, sitzungstag(andere_mandat))
    fremd = sitzung_beitrag_schreiben(andere, mitglied_anlegen("emil"), "dort")
    with pytest.raises(ValueError):
        sitzung_beitrag_schreiben(sitzung, mitglied_anlegen("fritz"), "hier", fremd)
    # und umgekehrt: Der Antragschat nimmt keine Antwort auf einen Sitzungsbeitrag an
    antrag = antrag_einbringen(mitglied_anlegen("gerda"), "Radweg", "Ein Radweg.", "", ordnung)
    with pytest.raises(ValueError):
        beitrag_schreiben(antrag, mitglied_anlegen("hans"), "quer", fremd)


def test_chat_schliesst_mit_dem_ende(sitzung):
    """E1: Mit dem Ende der Sitzung schließt der Chat; er bleibt als Teil des Protokolls lesbar."""
    bernd = mitglied_anlegen("bernd")
    sitzung_beitrag_schreiben(sitzung, bernd, "vorher")
    sitzung_beenden(sitzung)
    assert not sitzung_chat_offen(sitzung)
    with pytest.raises(ChatGesperrt):
        sitzung_beitrag_schreiben(sitzung, bernd, "nachher")
    assert [f["k"].text for f in sitzung_faden(sitzung)] == ["vorher"]


def test_genau_ein_bezug(sitzung, ordnung):  # noqa: F811
    bernd = mitglied_anlegen("bernd")
    antrag = antrag_einbringen(bernd, "Radweg", "Ein Radweg.", "", ordnung)
    for bezug in ({}, {"antrag": antrag, "sitzung": sitzung}):
        with pytest.raises(IntegrityError), transaction.atomic():
            Kommentar.objects.create(mitglied=bernd, text="x", **bezug)
    with pytest.raises(IntegrityError), transaction.atomic():
        Lesestand.objects.create(mitglied=bernd)


def test_faden_juengster_zuerst_antworten_chronologisch(sitzung):
    bernd = mitglied_anlegen("bernd")
    jetzt = timezone.now()
    a = sitzung_beitrag_schreiben(sitzung, bernd, "erste Frage", jetzt=jetzt)
    b = sitzung_beitrag_schreiben(sitzung, bernd, "zweite Frage", jetzt=jetzt + timedelta(seconds=1))
    r1 = sitzung_beitrag_schreiben(sitzung, bernd, "Antwort 1", a, jetzt=jetzt + timedelta(seconds=2))
    r2 = sitzung_beitrag_schreiben(sitzung, bernd, "Antwort 2", a, jetzt=jetzt + timedelta(seconds=3))
    faden = sitzung_faden(sitzung)
    assert [f["k"] for f in faden] == [b, a]
    assert [x["k"] for x in faden[1]["antworten"]] == [r1, r2]


def test_lesestand_je_sitzung(sitzung):
    bernd, cora = mitglied_anlegen("bernd"), mitglied_anlegen("cora")
    jetzt = timezone.now()
    sitzung_beitrag_schreiben(sitzung, cora, "alt", jetzt=jetzt)
    sitzung_gelesen_merken(sitzung, bernd, jetzt + timedelta(seconds=1))
    sitzung_gelesen_merken(sitzung, bernd, jetzt)  # nie rückwärts
    sitzung_beitrag_schreiben(sitzung, cora, "neu", jetzt=jetzt + timedelta(seconds=2))
    neu = {f["k"].text: f["neu"] for f in sitzung_faden(sitzung, bernd)}
    assert neu == {"alt": False, "neu": True}
    assert Lesestand.objects.get(mitglied=bernd, sitzung=sitzung).gelesen_bis == jetzt + timedelta(seconds=1)
    sitzung_gelesen_merken(sitzung, None)  # Gäste haben keinen Lesestand


def test_beantwortet_einmal_mit_audit(sitzung):
    frage = sitzung_beitrag_schreiben(sitzung, mitglied_anlegen("bernd"), "Wie stimmen Sie?")
    assert als_beantwortet_markieren(frage) is True
    assert als_beantwortet_markieren(frage) is False
    frage.refresh_from_db()
    assert frage.beantwortet_am is not None
    ereignisse = [e.ereignis for e in AuditEintrag.objects.filter(ereignis__typ="frage_beantwortet")]
    assert len(ereignisse) == 1 and ereignisse[0]["beitrag"] == frage.pk and "text" not in ereignisse[0]


def test_beantwortet_nicht_im_antragschat(ordnung):  # noqa: F811
    bernd = mitglied_anlegen("bernd")
    antrag = antrag_einbringen(bernd, "Radweg", "Ein Radweg.", "", ordnung)
    beitrag = beitrag_schreiben(antrag, bernd, "Beitrag")
    assert als_beantwortet_markieren(beitrag) is False


def test_gespraeche_nur_aus_antragschats(sitzung):
    bernd, cora = mitglied_anlegen("bernd"), mitglied_anlegen("cora")
    frage = sitzung_beitrag_schreiben(sitzung, bernd, "Frage")
    sitzung_beitrag_schreiben(sitzung, cora, "Antwort", frage)
    sitzung_gelesen_merken(sitzung, bernd)
    assert gespraeche(bernd) == [] and gespraeche(cora) == []
