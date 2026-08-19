"""Stimmberechtigung: Anwartschaftsfristen nach § 4 Abs 4."""

from datetime import date, timedelta

from hypothesis import given
from hypothesis import strategies as st

from plattform_core import Gegenstand, stimmberechtigt
from plattform_core.eligibility import monate_addieren


class TestGrenzfaelle:
    def test_sachfrage_genau_drei_monate(self):
        beitritt = date(2026, 1, 15)
        assert not stimmberechtigt(beitritt, Gegenstand.SACHFRAGE, date(2026, 4, 14))
        assert stimmberechtigt(beitritt, Gegenstand.SACHFRAGE, date(2026, 4, 15))

    def test_personenwahl_braucht_zwoelf_monate(self):
        beitritt = date(2026, 1, 15)
        assert stimmberechtigt(beitritt, Gegenstand.SACHFRAGE, date(2026, 6, 1))
        assert not stimmberechtigt(beitritt, Gegenstand.PERSONENWAHL, date(2026, 6, 1))
        assert stimmberechtigt(beitritt, Gegenstand.PERSONENWAHL, date(2027, 1, 15))

    def test_monatsletzter_wird_geklemmt(self):
        # 30. November + 3 Monate -> "30. Februar" existiert nicht -> 28./29. Februar
        assert monate_addieren(date(2026, 11, 30), 3) == date(2027, 2, 28)
        assert monate_addieren(date(2023, 11, 30), 3) == date(2024, 2, 29)  # Schaltjahr
        beitritt = date(2026, 11, 30)
        assert stimmberechtigt(beitritt, Gegenstand.SACHFRAGE, date(2027, 2, 28))

    def test_beitritt_nach_stichtag_nie_berechtigt(self):
        assert not stimmberechtigt(date(2026, 6, 1), Gegenstand.SACHFRAGE, date(2026, 5, 1), uebergang=True)

    def test_uebergangsregel_hebt_anwartschaft_auf(self):
        beitritt = date(2026, 8, 1)
        assert not stimmberechtigt(beitritt, Gegenstand.PERSONENWAHL, date(2026, 8, 15))
        assert stimmberechtigt(beitritt, Gegenstand.PERSONENWAHL, date(2026, 8, 15), uebergang=True)


@given(
    beitritt=st.dates(date(2000, 1, 1), date(2030, 12, 31)),
    tage_danach=st.integers(0, 4000),
    gegenstand=st.sampled_from(list(Gegenstand)),
)
def test_eigenschaft_berechtigung_ist_monoton_in_der_zeit(beitritt, tage_danach, gegenstand):
    """Wer an einem Stichtag berechtigt ist, ist es an jedem späteren auch
    (bei ununterbrochener Mitgliedschaft)."""
    stichtag = beitritt + timedelta(days=tage_danach)
    if stimmberechtigt(beitritt, gegenstand, stichtag):
        assert stimmberechtigt(beitritt, gegenstand, stichtag + timedelta(days=1))


@given(beitritt=st.dates(date(2000, 1, 1), date(2030, 12, 31)), monate=st.integers(0, 48))
def test_eigenschaft_monatsaddition_bleibt_im_gueltigen_kalender(beitritt, monate):
    ergebnis = monate_addieren(beitritt, monate)
    assert ergebnis >= beitritt
    # Tag wird nie größer als der Ursprungstag (Klemmung nach unten erlaubt)
    assert ergebnis.day <= max(beitritt.day, 28) or ergebnis.day == beitritt.day
