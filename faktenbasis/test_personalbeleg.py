import hashlib
from io import BytesIO

import pytest
from reportlab.pdfgen import canvas

from faktenbasis import personalbeleg
from plattform_core.test_personalbeleg import BELEG


def mini_pdf(text=BELEG):
    daten = BytesIO()
    pdf = canvas.Canvas(daten)
    pdf.drawString(30, 780, "Synthetisches Testblatt")
    pdf.showPage()
    y = 780
    for zeile in text.splitlines():
        pdf.drawString(30, y, zeile)
        y -= 15
    pdf.showPage()
    pdf.save()
    return daten.getvalue()


def test_synthetischer_pdf_beleg_wird_ohne_netz_oder_datenbank_gelesen(monkeypatch):
    # Nur diese Fixture ersetzt die bekannte Quellfassung für einen kleinen Offline-Test.
    daten = mini_pdf()
    monkeypatch.setattr(personalbeleg, "ORIGINAL_SHA256", hashlib.sha256(daten).hexdigest())
    monkeypatch.setattr(personalbeleg, "PDF_SEITEN", 2)
    monkeypatch.setattr(personalbeleg, "PDF_INDEX", 1)
    d = personalbeleg.lesen(daten)
    assert d["beamte"] == 60312 and d["gesamt"] == 138100 and d["einheit"] == "VBÄ"
    assert d["original_sha256"] == hashlib.sha256(daten).hexdigest()
    assert d["seite"] == 75 and d["tabelle"] == 20 and d["parser_fassung"] == 1


@pytest.mark.parametrize("daten", [None, b"", b"kein PDF", b"%PDF-unbekannt", b"%PDF-"+b"x"*(6*1024*1024)],
    ids=["kein-typ", "leer", "kein-pdf", "unbekannter-hash", "zu-gross"])
def test_unbekannte_bytes_werden_vor_jedem_pdf_parser_abgewiesen(daten, monkeypatch):
    import pypdf
    monkeypatch.setattr(pypdf, "PdfReader", lambda *args, **kwargs: pytest.fail("Unbekannte Bytes im PDF-Parser"))
    with pytest.raises(ValueError):
        personalbeleg.lesen(daten)


def test_bekannter_beleg_muss_erwartete_seitenzahl_haben(monkeypatch):
    daten = mini_pdf()
    monkeypatch.setattr(personalbeleg, "ORIGINAL_SHA256", hashlib.sha256(daten).hexdigest())
    assert personalbeleg.PDF_SEITEN == 212 and personalbeleg.PDF_INDEX == 76
    with pytest.raises(ValueError, match="personal_pdf"):
        personalbeleg.lesen(daten)
