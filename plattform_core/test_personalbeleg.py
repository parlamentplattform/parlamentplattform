import pytest

from plattform_core.personalbeleg import DATENJAHR, VERSION, aus_text

BELEG = """75Das Personal des Bundes 2026
Tabelle 20: Bundespersonal nach Art des Dienstverhältnisses*
Jahr
Beamtinnen
und Beamte
vertragliches
Personal Gesamtpersonalstand
2024 61.661 76.026 137.687
2025 60.312 77.788 138.100
* in VBÄ
"""


def test_eindeutige_amtliche_zeile_mit_passender_einheit_ohne_prognose():
    assert VERSION == 1 and DATENJAHR == 2025
    assert aus_text(BELEG) == {"datenjahr": 2025, "einheit": "VBÄ", "beamte": 60312,
        "vertragliches_personal": 77788, "gesamt": 138100}
    assert aus_text(BELEG.replace(" ", "\u00a0")) == aus_text(BELEG)


@pytest.mark.parametrize("alt,neu,code", [
    ("75Das", "74Das", "personal_seite"),
    ("Bundes 2026", "Bundes 2025", "personal_seite"),
    ("Tabelle 20:", "Tabelle 21:", "personal_spalten"),
    ("Personal Gesamtpersonalstand", "Gesamtpersonalstand Personal", "personal_spalten"),
    ("* in VBÄ", "* in Köpfen", "personal_einheit"),
    ("2025 60.312 77.788 138.100", "2026 60.312 77.788 138.100", "personal_jahr"),
    ("2025 60.312 77.788 138.100", "2025 60.312 77.788 138.100\n2025 60.312 77.788 138.100", "personal_jahr"),
    ("60.312", "60,312", "personal_zahlen"),
    ("60.312", "６0.312", "personal_zahlen"),
    ("60.312", "-60.312", "personal_zahlen"),
    ("60.312", "060.312", "personal_zahlen"),
    ("138.100", "138.101", "personal_summe"),
    ("2025 60.312 77.788 138.100", "2025 0 0 0", "personal_summe"),
])
def test_vertauschte_oder_unpassende_angaben_nicht_reparieren(alt, neu, code):
    with pytest.raises(ValueError, match=code):
        aus_text(BELEG.replace(alt, neu))


@pytest.mark.parametrize("text", [None, b"PDF", "", "x"*20001])
def test_technische_textgrenzen(text):
    with pytest.raises(ValueError, match="personal_text"):
        aus_text(text)
