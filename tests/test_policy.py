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


@pytest.mark.parametrize(
    "feld,wert",
    [
        ("review_tage", 15),  # § 5 Abs 12: „binnen 14 Tagen“ — eine Obergrenze
        ("ueberarbeitung_tage", 15),
        ("review_tage", 0),
        ("ueberarbeitung_tage", 0),
        ("pruefung_tage", 0),
        ("hoechstrunden", 0),
        ("vorschlag_annahme_anteil", 1.0),  # 100 % kann niemand überschreiten
        ("vorschlag_annahme_anteil", -0.1),
    ],
)
def test_die_schleifenregeln_halten_die_satzungsgrenzen(feld, wert):
    """Befund #3: Die Entwurfsschleife gehört zur eingefrorenen Ordnung. § 5 Abs 12 gibt den
    Unterstützern und dem Expertenrat je Runde „binnen 14 Tagen“ — das ist ein Höchstwert,
    kein Minimum: Eine Ordnung darf kürzer sein, nie länger."""
    with pytest.raises(PolicyFehler):
        Policy(**{**GUELTIG, feld: wert})


def test_eine_satzungskonforme_kurze_schleifenfrist_ist_erlaubt():
    """Sieben Tage liegen „binnen 14 Tagen“ — die Grenze wirkt nach oben, nicht nach unten."""
    p = Policy(**{**GUELTIG, "review_tage": 7, "ueberarbeitung_tage": 7})
    assert p.review_tage == 7 and p.ueberarbeitung_tage == 7


def test_alte_snapshots_ohne_schleifenfelder_laden_mit_den_registerwerten_des_erstbestands():
    """Befund #3: Vor 0.45 trug kein Snapshot die Schleifenfelder. Sie laden mit den Vorgaben,
    die bis dahin im Register standen — ein laufendes Verfahren rechnet damit weiter wie
    zuvor, nur jetzt aus seiner eigenen Kopie (§ 5 Abs 5)."""
    p = Policy.aus_dict(dict(GUELTIG))
    assert (p.vorschlag_annahme_anteil, p.hoechstrunden, p.review_tage, p.ueberarbeitung_tage, p.pruefung_tage) == (
        0.5,
        3,
        14,
        14,
        7,
    )
    assert "review_tage" in p.als_dict()  # neue Snapshots tragen die Felder ausdrücklich


def test_unbekannte_felder_im_snapshot_werden_abgewiesen():
    with pytest.raises(PolicyFehler):
        Policy.aus_dict({**GUELTIG, "geheimes_feld": True})


def test_policy_ist_unveraenderlich():
    p = Policy(**GUELTIG)
    with pytest.raises((AttributeError, TypeError)):  # FrozenInstanceError
        p.beratung_tage = 5  # type: ignore[misc]


# ── 0.48: Verfahren ohne Beratungsphase (§ 7 Abs 10) ─────────────────────────────────────


def test_die_vorgaben_der_fassung_3_lassen_alte_snapshots_unveraendert():
    """Ein Snapshot aus 0.47 kennt weder `beratung_entfaellt` noch die Abstimmungsfenster —
    er lädt trotzdem und verhält sich wie bisher (§ 5 Abs 5)."""
    alt = Policy.aus_dict(dict(GUELTIG))
    assert alt.beratung_entfaellt is False
    assert alt.abstimmung_fruehestens_tage == 0
    assert alt.abstimmung_spaetestens_tage_nach_schwelle == 0
    assert set(alt.als_dict()) >= {"beratung_entfaellt", "abstimmung_fruehestens_tage"}
    assert Policy.aus_dict(alt.als_dict()) == alt


def test_ohne_beratungsphase_darf_die_schwelle_null_sein():
    """Bestätigungsantrag (§ 7 Abs 10 lit f Z 3): keine Unterstützungsphase, Schwelle 0."""
    p = Policy(
        **{**GUELTIG, "unterstuetzung_schwelle": 0, "beratung_entfaellt": True, "abstimmung_fruehestens_tage": 7}
    )
    assert p.unterstuetzung_schwelle == 0 and p.beratung_entfaellt


@pytest.mark.parametrize(
    "felder",
    [
        {"unterstuetzung_schwelle": -1, "beratung_entfaellt": True},
        {"abstimmung_fruehestens_tage": -1, "beratung_entfaellt": True},
        {"abstimmung_spaetestens_tage_nach_schwelle": -1, "beratung_entfaellt": True},
        {"abstimmung_fruehestens_tage": 7},  # Fenster nur ohne Beratungsphase
        {"abstimmung_spaetestens_tage_nach_schwelle": 3},
    ],
)
def test_die_fenster_ohne_beratung_halten_ihre_grenzen(felder):
    with pytest.raises(PolicyFehler):
        Policy(**{**GUELTIG, **felder})
