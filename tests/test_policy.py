"""Policy: Satzungsminima sind im Code nicht unterschreitbar."""

import pytest

from plattform_core import Policy
from plattform_core.policy import PolicyFehler

GUELTIG = dict(
    id="sachantrag-standard",
    version=1,
    unterstuetzung_schwelle=10,
    unterstuetzung_frist_tage=14,
    beratung_tage=21,
    abstimmung_tage=7,
    mindestbeteiligung=0.05,
    mehrheitsbasis="ja_nein",
)


def test_gueltige_policy_laesst_sich_bauen_und_serialisieren():
    p = Policy(**GUELTIG)
    assert Policy.aus_dict(p.als_dict()) == p


@pytest.mark.parametrize(
    "feld,wert",
    [
        ("beratung_tage", 20),  # § 5 Abs 3 lit c: mindestens 21
        ("abstimmung_tage", 6),  # § 5 Abs 3 lit d: mindestens 7
        ("mindestbeteiligung", 0.04),  # § 5 Abs 4: mindestens 5 %
        ("unterstuetzung_schwelle", 0),
        ("unterstuetzung_frist_tage", 0),
        ("mehrheitsbasis", "zweidrittel-vielleicht"),
    ],
)
def test_satzungswidrige_policy_wird_abgewiesen(feld, wert):
    with pytest.raises(PolicyFehler):
        Policy(**{**GUELTIG, feld: wert})


def test_unbekannte_felder_im_snapshot_werden_abgewiesen():
    with pytest.raises(PolicyFehler):
        Policy.aus_dict({**GUELTIG, "geheimes_feld": True})


def test_policy_ist_unveraenderlich():
    p = Policy(**GUELTIG)
    with pytest.raises((AttributeError, TypeError)):  # FrozenInstanceError
        p.beratung_tage = 5  # type: ignore[misc]
