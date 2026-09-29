"""Die Schranke der Tendenz (D-D2 b, 0.51.0): bei 0 nie sichtbar, bei 1 erst ab erreichter Mindestbeteiligung
— mit derselben Bruchrechnung wie die Auszählung."""

import pytest
from hypothesis import given
from hypothesis import strategies as st

from plattform_core.policy import REGISTER_ZUORDNUNG, Policy, PolicyFehler, aus_register
from plattform_core.tally import Stimme, auszaehlen, mindestbeteiligung_erreicht, tendenz_sichtbar

BASIS = dict(
    id="p", version=1, unterstuetzung_schwelle=1, unterstuetzung_frist_tage=1, beratung_tage=21,
    abstimmung_tage=7, mindestbeteiligung=0.05,
)


@given(abgegeben=st.integers(0, 5000), stimmberechtigte=st.integers(1, 5000))
def test_bei_null_ist_die_tendenz_nie_sichtbar(abgegeben, stimmberechtigte):
    assert not tendenz_sichtbar(Policy(**BASIS), min(abgegeben, stimmberechtigte), stimmberechtigte)


@given(abgegeben=st.integers(0, 400), stimmberechtigte=st.integers(1, 400))
def test_bei_eins_sichtbar_genau_wenn_die_auszaehlung_die_beteiligung_bejaht(abgegeben, stimmberechtigte):
    abgegeben = min(abgegeben, stimmberechtigte)
    policy = Policy(**BASIS, tendenz_ab_mindestbeteiligung=1)
    stimmen = [(f"p{i}", Stimme.JA) for i in range(abgegeben)]
    erreicht = auszaehlen(stimmen, stimmberechtigte, policy).beteiligung_erreicht
    assert tendenz_sichtbar(policy, abgegeben, stimmberechtigte) is erreicht
    assert mindestbeteiligung_erreicht(abgegeben, stimmberechtigte, policy.mindestbeteiligung) is erreicht


def test_die_grenze_ohne_gleitkomma():
    assert mindestbeteiligung_erreicht(1, 20, 0.05)  # genau fünf Prozent
    assert not mindestbeteiligung_erreicht(4, 100, 0.05)
    assert not mindestbeteiligung_erreicht(0, 0, 0.05)


@pytest.mark.parametrize("wert", [2, -1, 7])
def test_nur_null_oder_eins(wert):
    with pytest.raises(PolicyFehler):
        Policy(**BASIS, tendenz_ab_mindestbeteiligung=wert)


def test_ein_alter_schnappschuss_ohne_feld_ist_verdeckt():
    daten = Policy(**BASIS).als_dict()
    daten.pop("tendenz_ab_mindestbeteiligung")
    assert Policy.aus_dict(daten).tendenz_ab_mindestbeteiligung == 0


@pytest.mark.parametrize("register, erwartet", [(1, 1), (0, 0), (7, 0)])
def test_nur_der_registerwert_eins_schaltet_ein(register, erwartet):
    werte = {schluessel: 21 for _f, (schluessel, _w) in REGISTER_ZUORDNUNG.items()}
    werte.update({
        "verfahren-unterstuetzung-anteil-prozent": 0, "verfahren-mindestbeteiligung-prozent": 5,
        "vorschlag-annahme-prozent": 50, "gremien-review-tage": 14, "gremien-ueberarbeitung-tage": 14,
        "verfahren-tendenz-ab-mindestbeteiligung": register,
    })
    assert aus_register(werte, "x", 1).tendenz_ab_mindestbeteiligung == erwartet
