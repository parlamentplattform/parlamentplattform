"""Kontoauszug-Leser (F-59): camt.053 und CSV landen im selben Umsatz-Schema."""

from plattform_core.bankauszug import auszug_lesen, camt053_lesen, csv_lesen
from plattform_core.beitraege import eingaenge_zuordnen

CAMT = """<?xml version="1.0" encoding="UTF-8"?>
<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.053.001.08">
 <BkToCstmrStmt><Stmt>
  <Ntry>
   <NtryRef>SPK-77</NtryRef>
   <Amt Ccy="EUR">30.00</Amt>
   <CdtDbtInd>CRDT</CdtDbtInd>
   <BookgDt><Dt>2026-08-28</Dt></BookgDt>
   <NtryDtls><TxDtls>
     <RltdPties><Dbtr><Nm>Maria Huber</Nm></Dbtr></RltdPties>
     <RmtInf><Ustrd>DDOE-0042-A1B2C3 Mitgliedsbeitrag</Ustrd></RmtInf>
   </TxDtls></NtryDtls>
  </Ntry>
  <Ntry>
   <Amt Ccy="EUR">99.00</Amt>
   <CdtDbtInd>DBIT</CdtDbtInd>
   <BookgDt><Dt>2026-08-28</Dt></BookgDt>
  </Ntry>
 </Stmt></BkToCstmrStmt>
</Document>"""

CSV_GEORGE = "\n".join(
    [
        "Buchungsdatum;Teilnehmer;Verwendungszweck;Betrag;Währung",
        "28.08.2026;Huber Maria;DDOE-0042-A1B2C3 Beitrag;30,00;EUR",
        "27.08.2026;Strom AG;Rechnung 123;-55,10;EUR",
    ]
)


def test_camt_liest_nur_gutschriften_mit_kennung_und_absender():
    umsaetze = camt053_lesen(CAMT)
    assert len(umsaetze) == 1
    u = umsaetze[0]
    assert u["internalTransactionId"] == "SPK-77"
    assert u["debtorName"] == "Maria Huber"
    assert "DDOE-0042-A1B2C3" in u["remittanceInformationUnstructured"]


def test_csv_erkennt_kopfzeile_deutsche_betraege_und_ist_stabil():
    umsaetze = csv_lesen(CSV_GEORGE)
    assert len(umsaetze) == 2  # die Ausgabe filtert erst der Abgleich (Betrag <= 0)
    u = umsaetze[0]
    assert u["transactionAmount"]["amount"] == "30.00"
    assert u["bookingDate"] == "2026-08-28"
    assert u["internalTransactionId"] == csv_lesen(CSV_GEORGE)[0]["internalTransactionId"]  # Fingerabdruck stabil


def test_beide_wege_muenden_im_selben_abgleich():
    referenzen = {"DDOE-0042-A1B2C3": 7}
    for inhalt in (CAMT, CSV_GEORGE):
        treffer = eingaenge_zuordnen(auszug_lesen(inhalt), referenzen)
        assert [mid for mid, _e in treffer] == [7]


def test_unlesbares_gibt_leere_liste():
    assert auszug_lesen("<kaputt") == []
    assert auszug_lesen("nur eine zeile ohne kopf") == []
