"""Der Beitragsabgleich (F-59): Referenz erkennt, Namen vergleicht, Fremdes ignoriert."""

from datetime import date
from decimal import Decimal

from plattform_core.beitraege import (
    eingaenge_zuordnen,
    name_passt,
    referenz_finden,
    umsatz_normalisieren,
)


def test_referenz_wird_auch_gestaucht_und_klein_gefunden():
    assert referenz_finden("DDOE-0042-A1B2C3 Mitgliedsbeitrag") == "DDOE-0042-A1B2C3"
    assert referenz_finden("Beitrag ddoe 0042 a1b2c3 danke") == "DDOE-0042-A1B2C3"
    assert referenz_finden("DDOE0042A1B2C3") == "DDOE-0042-A1B2C3"
    assert referenz_finden("nur ein Gruß") is None
    assert referenz_finden("") is None


def test_namensvergleich_ist_grosszuegig_aber_ehrlich():
    assert name_passt("Huber Maria", "Maria", "Huber")
    assert name_passt("MARIA HUBER-MOSER", "Maria", "Huber")
    assert name_passt("Müller Jörg", "Jörg", "Mueller")  # Umlaut-Schreibweisen egal
    assert not name_passt("Firma Beispiel GmbH", "Maria", "Huber")  # erkennbare Abweichung
    assert name_passt("", "Maria", "Huber")  # ohne Absendername kein Hinweis
    assert name_passt("Wer auch immer", "", "")  # ohne Mitgliedsname kein Hinweis


UMSATZ = {
    "internalTransactionId": "abc123",
    "transactionAmount": {"amount": "30.00", "currency": "EUR"},
    "bookingDate": "2026-08-25",
    "remittanceInformationUnstructured": "DDOE-0042-A1B2C3 Mitgliedsbeitrag",
    "debtorName": "Maria Huber",
}


def test_normalisierung_nimmt_nur_lesbare_gutschriften():
    e = umsatz_normalisieren(UMSATZ)
    assert (e.betrag, e.gebucht_am, e.absender) == (Decimal("30.00"), date(2026, 8, 25), "Maria Huber")
    assert umsatz_normalisieren({**UMSATZ, "transactionAmount": {"amount": "-30.00"}}) is None  # Ausgabe
    assert umsatz_normalisieren({**UMSATZ, "internalTransactionId": "", "transactionId": ""}) is None
    assert umsatz_normalisieren({**UMSATZ, "bookingDate": "irgendwann"}) is None
    assert umsatz_normalisieren({}) is None


def test_zuordnung_matcht_nur_bekannte_referenzen_in_euro():
    fremd = {**UMSATZ, "internalTransactionId": "x9", "remittanceInformationUnstructured": "Spende"}
    falsche_waehrung = {
        **UMSATZ,
        "internalTransactionId": "x8",
        "transactionAmount": {"amount": "30.00", "currency": "USD"},
    }
    treffer = eingaenge_zuordnen([UMSATZ, fremd, falsche_waehrung], {"DDOE-0042-A1B2C3": 7})
    assert [(mid, e.umsatz_id) for mid, e in treffer] == [(7, "abc123")]


def test_zuordnung_liest_auch_das_array_feld():
    umsatz = {
        "transactionId": "t2",
        "transactionAmount": {"amount": "15", "currency": "EUR"},
        "bookingDate": "2026-08-20",
        "remittanceInformationUnstructuredArray": ["Beitrag", "DDOE-0007-FFAA99"],
    }
    assert eingaenge_zuordnen([umsatz], {"DDOE-0007-FFAA99": 3})[0][0] == 3
