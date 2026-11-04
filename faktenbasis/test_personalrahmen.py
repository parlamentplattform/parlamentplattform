"""Bestände und Fehlstellen festhalten, ohne Kapazitäten oder Effekte zu erfinden."""

import copy
from datetime import timedelta

import pytest
from django.utils import timezone

from faktenbasis.models import PersonalAggregat, PersonalRessorttabelle
from faktenbasis.personalrahmen import PersonalrahmenFehler, _hash, festhalten, pruefen
from faktenbasis.test_personalimport import DATEN as AGGREGAT
from faktenbasis.test_ressortimport import DATEN as RESSORT
from ki.models import KILauf

pytestmark = pytest.mark.django_db
TEXT = "a" * 64


def daten(*, aggregat=True, ressort=True, jetzt=None):
    zeit = jetzt or timezone.now() - timedelta(minutes=1)
    if aggregat:
        PersonalAggregat.objects.create(**copy.deepcopy(AGGREGAT), erfasst_am=zeit)
    if ressort:
        PersonalRessorttabelle.objects.create(**copy.deepcopy(RESSORT), erfasst_am=zeit)


def neu_hashen(r):
    r.pop("sha256", None)
    return {**r, "sha256": _hash(r)}


def test_vorhandene_bestandswerte_werden_genau_mit_herkunft_getrennt_festgehalten(django_assert_num_queries):
    daten()
    vorher = list(PersonalRessorttabelle.objects.values())
    with django_assert_num_queries(2):
        r = festhalten(TEXT)
    assert r["zustand"] == "vorhanden"
    assert r["aggregat"]["beamte"] == 60312 and r["aggregat"]["vertragliches_personal"] == 77788
    assert r["ressorttabelle"]["ressorts"] == RESSORT["ressorts"]
    assert r["ressorttabelle"]["ressorts"][0]["zentralstelle"] is None
    assert r["ressorttabelle"]["gesamt"] == RESSORT["gesamt"]
    assert r["umfang"] == "bundespersonal_bestand_ohne_folgenprognose"
    assert not any("delta" in k or "kapazitaet" in k for k in r)
    assert PersonalRessorttabelle.objects.values().get() == vorher[0]
    assert not KILauf.objects.exists()


@pytest.mark.parametrize("aggregat,ressort,zustand", [(False, False, "leer"), (True, False, "teilweise"), (False, True, "teilweise")])
def test_fehlende_bestaende_werden_nicht_zu_null(aggregat, ressort, zustand):
    daten(aggregat=aggregat, ressort=ressort)
    r = festhalten(TEXT)
    assert r["zustand"] == zustand
    assert (r["aggregat"] is None) == (not aggregat)
    assert (r["ressorttabelle"] is None) == (not ressort)


def test_spaetere_aufnahme_wird_nicht_in_den_alten_rahmen_eingeschoben(django_assert_num_queries):
    jetzt = timezone.now()
    alt = festhalten(TEXT, jetzt=jetzt)
    daten(jetzt=jetzt + timedelta(seconds=1))
    assert festhalten(TEXT, jetzt=jetzt)["zustand"] == "leer"
    assert festhalten(TEXT, jetzt=jetzt + timedelta(seconds=2))["zustand"] == "vorhanden"
    with django_assert_num_queries(0):
        assert pruefen(alt, text_sha256=TEXT)["zustand"] == "leer"


@pytest.mark.parametrize("feld,wert", [("quelle", "https://example.org/fremd.pdf"), ("einheit", "Personen"),
                                     ("seite", 74), ("tabelle", 19), ("datenjahr", 2024)])
def test_falsche_metadaten_geben_keinen_teilbestand_als_vollstaendig_aus(feld, wert):
    d = {**copy.deepcopy(AGGREGAT), feld: wert}
    PersonalAggregat.objects.create(**d, erfasst_am=timezone.now() - timedelta(seconds=1))
    daten(aggregat=False)
    r = festhalten(TEXT)
    assert r["zustand"] == "fehler" and r["fehler"] == ["aggregat"]
    assert r["aggregat"] is None and r["ressorttabelle"] is None


def test_fremder_originalbeleg_wird_nicht_zum_bekannten_bericht_erklaert():
    PersonalAggregat.objects.create(**{**copy.deepcopy(AGGREGAT), "original_sha256": "b" * 64})
    assert festhalten(TEXT)["zustand"] == "leer"


def test_mehrdeutige_belege_werden_nicht_still_ausgewaehlt():
    daten()
    PersonalAggregat.objects.create(**{**copy.deepcopy(AGGREGAT), "bereich": "Unbekannte zweite Zeile"})
    r = festhalten(TEXT)
    assert r["zustand"] == "fehler" and r["fehler"] == ["aggregat"]


def test_fremde_textbindung_und_nachtraegliche_aenderung_werden_erkannt():
    daten()
    r = festhalten(TEXT)
    with pytest.raises(PersonalrahmenFehler):
        pruefen(r, text_sha256="b" * 64)
    r["aggregat"]["gesamt"] += 1
    with pytest.raises(PersonalrahmenFehler):
        pruefen(r, text_sha256=TEXT)


@pytest.mark.parametrize("fall", ["reihung", "doppelt", "bool", "leere_zahl", "einheit", "stichtag", "methodik", "zukunft", "teil", "fremdfeld", "naiv", "version"])
def test_erneut_gehashte_fehlerhafte_struktur_ist_keine_bestaetigte_basis(fall):
    daten()
    r = festhalten(TEXT)
    p = r["ressorttabelle"]
    if fall == "reihung":
        p["ressorts"] = list(reversed(p["ressorts"]))
    elif fall == "doppelt":
        p["ressorts"][1] = copy.deepcopy(p["ressorts"][0])
    elif fall == "bool":
        p["ressorts"][1]["gesamt"] = True
    elif fall == "leere_zahl":
        p["ressorts"][0]["zentralstelle"] = 0
    elif fall == "einheit":
        r["aggregat"]["einheit"] = "Köpfe"
    elif fall == "stichtag":
        p["stichtag"] = "2026-12-31"
    elif fall == "methodik":
        p["methodik_seite"] = 30
    elif fall == "zukunft":
        p["erfasst_am"] = (timezone.now() + timedelta(days=1)).isoformat()
    elif fall == "teil":
        r["aggregat"] = None
    elif fall == "fremdfeld":
        p["kapazitaet"] = 100
    elif fall == "naiv":
        r["erfasst_am"] = "2026-11-03T12:00:00"
    else:
        r["version"] = True
    with pytest.raises(PersonalrahmenFehler):
        pruefen(neu_hashen(r), text_sha256=TEXT)


def test_originalrundung_wird_nicht_als_fehler_oder_deltabedarf_ausgeglichen():
    daten()
    r = festhalten(TEXT)
    inneres = next(z for z in r["ressorttabelle"]["ressorts"] if z["ressort"] == "Inneres")
    assert inneres["gesamt"] == 37900
    assert inneres["zentralstelle"] + inneres["nachgeordnet"] == 37899
    assert pruefen(r, text_sha256=TEXT)["ressorttabelle"]["ressorts"] == RESSORT["ressorts"]
