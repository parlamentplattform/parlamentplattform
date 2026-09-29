"""Ähnlichkeit Fassung 2 (Anweisung des Gründers 28.9.2026, FB-H2): Wort-Ebene statt Zeichen-Ebene.

Die beiden Gründer-Beispiele — zwei Anträge ohne inhaltliche Nähe, die in Fassung 1 auf 29 Prozent
kamen — bleiben deutlich unter 15 Prozent; ein umformulierter gleicher Antrag liegt über 40.
Dazu Determinismus, Symmetrie und Grenzen per Hypothesis, und der Kosinus samt Vereinigung
beider Stufen für Stufe 2."""

from hypothesis import given, settings
from hypothesis import strategies as st

from plattform_core import similarity
from plattform_core.similarity import (
    STOPPWOERTER,
    aehnlichkeit,
    aehnlichste,
    kosinus,
    merkmale,
    stammform,
    vereinigen,
    woerter,
)

HOLZBRETTER = (
    "Verbot von Holzschneidebrettern in der Gastronomie",
    "Die Bundesregierung wird aufgefordert, dem Nationalrat einen Gesetzesentwurf vorzulegen, der die "
    "Verwendung von Holzschneidebrettern in gastronomischen Betrieben aus hygienischen Gründen untersagt. "
    "Betriebe sollen binnen zwei Jahren auf Kunststoff- oder Glasbretter umstellen.",
)
BOERSE = (
    "Börsennotierung von Rüstungs- und Pharmaunternehmen einschränken",
    "Die Bundesregierung wird aufgefordert, dem Nationalrat umgehend einen Gesetzesentwurf vorzulegen, der die "
    "Börsennotierung von Rüstungs- und Pharmaunternehmen an strenge Auflagen bindet, insbesondere an "
    "Transparenzpflichten gegenüber Anlegern.",
)
PROTOKOLLE = (
    "Sitzungsprotokolle binnen 48 Stunden veröffentlichen",
    "Die DDÖ veröffentlicht Protokolle aller Ratssitzungen binnen 48 Stunden.",
)
PROTOKOLLE_UMFORMULIERT = (
    "Ratssitzungsprotokolle innerhalb von 48 Stunden veröffentlichen",
    "Alle Protokolle der Ratssitzungen der DDÖ werden binnen 48 Stunden veröffentlicht.",
)

wort = st.text(alphabet=st.characters(whitelist_categories=("Ll", "Lu", "Nd")), min_size=1, max_size=12)
saetze = st.lists(wort, min_size=0, max_size=25).map(" ".join)


def test_die_fassung_ist_zwei():
    assert similarity.VERSION == 2


def test_die_gruender_beispiele_liegen_unter_15_prozent():
    """Fassung 1 meldete 29 Prozent — die Floskeln „Bundesregierung … aufgefordert … Nationalrat …
    Gesetzesentwurf vorzulegen“ zählten mit. Jetzt zählt der Gegenstand."""
    assert aehnlichkeit(HOLZBRETTER, BOERSE) < 0.15


def test_ein_umformulierter_gleicher_antrag_liegt_ueber_40_prozent():
    assert aehnlichkeit(PROTOKOLLE, PROTOKOLLE_UMFORMULIERT) > 0.40


def test_titelwoerter_zaehlen_doppelt():
    mit_titel = aehnlichkeit(("Radwege ausbauen", "Die Gemeinde baut Radwege aus."), ("Radwege ausbauen", "Anderes Thema hier."))
    ohne_titel = aehnlichkeit(("", "Radwege ausbauen. Die Gemeinde baut Radwege aus."), ("", "Radwege ausbauen. Anderes Thema hier."))
    assert mit_titel > ohne_titel
    gewichte, _paare = merkmale(("Radwege", "Radwege"))
    assert gewichte == {"radweg": 3.0}  # 2 (Titel) + 1 (Wortlaut)


def test_die_reihenfolge_zaehlt_ueber_die_wortpaare():
    gleich = aehnlichkeit("Kinder schützen Wälder", "Kinder schützen Wälder")
    vertauscht = aehnlichkeit("Kinder schützen Wälder", "Wälder schützen Kinder")
    assert gleich == 1.0 and 0.6 < vertauscht < 1.0  # Wortmenge gleich, Paare verschieden


def test_stammform_kappt_nur_ab_fuenf_zeichen_und_laesst_genug_stamm():
    assert stammform("häuser") == "häus"
    assert stammform("hause") == "haus"
    assert stammform("haus") == "haus"
    assert stammform("essen") == "ess"
    assert stammform("enten") == "ent"  # -en vor -n: die längere Endung zuerst


def test_stoppwoerter_sind_die_floskeln_der_antragssprache():
    for floskel in ("bundesregierung", "aufgefordert", "nationalrat", "gesetzesentwurf", "vorzulegen", "umgehend", "insbesondere"):
        assert floskel in STOPPWOERTER
    assert len(STOPPWOERTER) >= 150
    assert woerter("Die Bundesregierung wird aufgefordert") == []


def test_aehnlichste_nimmt_paare_und_strings_gemischt():
    treffer = aehnlichste(PROTOKOLLE, [(1, PROTOKOLLE_UMFORMULIERT), (2, HOLZBRETTER), (3, "Sitzungsprotokolle der Ratssitzungen binnen 48 Stunden veröffentlichen")])
    ids = [kid for kid, _ in treffer]
    assert 1 in ids and 3 in ids and 2 not in ids


@settings(max_examples=60, deadline=None)
@given(a=saetze, b=saetze)
def test_symmetrie_determinismus_und_grenzen(a, b):
    x, y = aehnlichkeit(a, b), aehnlichkeit(b, a)
    assert x == y == aehnlichkeit(a, b)
    assert 0.0 <= x <= 1.0


@settings(max_examples=40, deadline=None)
@given(a=saetze)
def test_ein_text_ist_sich_selbst_gleich_wenn_er_tragende_woerter_hat(a):
    assert aehnlichkeit(a, a) == (1.0 if woerter(a) else 0.0)


@settings(max_examples=40, deadline=None)
@given(a=saetze, titel=saetze)
def test_paar_und_string_sind_dieselbe_regel(a, titel):
    assert aehnlichkeit(("", a), a) == aehnlichkeit(a, a)
    assert aehnlichkeit((titel, a), (titel, a)) == (1.0 if woerter(titel + " " + a) else 0.0)


# ── Stufe 2: Kosinus und Vereinigung ──────────────────────────────────────────────────────────


def test_kosinus_rechnet_und_klemmt():
    assert kosinus([1.0, 0.0], [1.0, 0.0]) == 1.0
    assert kosinus([1.0, 0.0], [0.0, 1.0]) == 0.0
    assert kosinus([1.0, 0.0], [-1.0, 0.0]) == 0.0  # negativ wird auf 0 geklemmt
    assert round(kosinus([1.0, 1.0], [1.0, 0.0]), 4) == 0.7071


def test_kosinus_ist_bei_kaputten_vektoren_ehrlich_null():
    assert kosinus([], [1.0]) == 0.0
    assert kosinus([1.0, 2.0], [1.0]) == 0.0  # anderes Modell, andere Dimension
    assert kosinus([0.0, 0.0], [1.0, 1.0]) == 0.0


@settings(max_examples=40, deadline=None)
@given(v=st.lists(st.floats(-5, 5, allow_nan=False), min_size=1, max_size=8), w=st.lists(st.floats(-5, 5, allow_nan=False), min_size=1, max_size=8))
def test_kosinus_symmetrisch_und_begrenzt(v, w):
    assert kosinus(v, w) == kosinus(w, v)
    assert 0.0 <= kosinus(v, w) <= 1.0


def test_vereinigen_nimmt_jede_stufe_und_sortiert_nach_dem_hoeheren_wert():
    wort = {1: 0.35, 2: 0.10, 3: 0.50, 4: 0.05}
    bedeutung = {1: 0.60, 2: 0.90, 4: 0.20}
    zeilen = vereinigen(wort, bedeutung, wort_schwelle=0.30, bedeutung_schwelle=0.78, limit=3)
    assert zeilen == [(2, 0.10, 0.90), (1, 0.35, 0.60), (3, 0.50, None)]


def test_vereinigen_respektiert_limit_und_bricht_gleichstand_per_id():
    wort = {5: 0.5, 2: 0.5, 9: 0.5}
    assert vereinigen(wort, {}, 0.3, 0.78, limit=2) == [(2, 0.5, None), (5, 0.5, None)]
    assert vereinigen({}, {}, 0.3, 0.78) == []
