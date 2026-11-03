import hashlib
from io import BytesIO

import pytest
from reportlab.pdfgen import canvas

from faktenbasis import ressortbeleg
from plattform_core.test_personalressorts import METHODIK, TABELLE


def mini_pdf():
    daten = BytesIO()
    pdf = canvas.Canvas(daten)
    for text in (TABELLE, METHODIK):
        for i, zeile in enumerate(text.splitlines()):
            pdf.drawString(20, 800 - i*15, zeile)
        pdf.showPage()
    pdf.save()
    return daten.getvalue()


def test_zwei_bekannte_seiten_muessen_gemeinsam_pruefbar_sein(monkeypatch):
    roh = mini_pdf()
    monkeypatch.setattr(ressortbeleg, "ORIGINAL_SHA256", hashlib.sha256(roh).hexdigest())
    monkeypatch.setattr(ressortbeleg, "PDF_SEITEN", 2)
    monkeypatch.setattr(ressortbeleg, "TABELLE_INDEX", 0)
    monkeypatch.setattr(ressortbeleg, "METHODIK_INDEX", 1)
    d = ressortbeleg.lesen(roh)
    assert len(d["ressorts"]) == 14 and d["gesamt"]["gesamt"] == 138100
    assert d["seite"] == 30 and d["methodik_seite"] == 175 and d["tabelle"] == 7
    assert d["parser_fassung"] == 1 and d["ressorts"][0]["zentralstelle"] is None


@pytest.mark.parametrize("roh", [None, b"", b"keinPDF", b"%PDF-fremd", b"%PDF-"+b"x"*(6*1024*1024)],
    ids=["kein-typ", "leer", "kein-pdf", "unbekannter-hash", "zu-gross"])
def test_unbekannte_bytes_erreichen_nie_den_pdf_parser(roh, monkeypatch):
    import pypdf

    monkeypatch.setattr(pypdf, "PdfReader", lambda *a, **kw: pytest.fail("Unbekannte Datei im Parser"))
    with pytest.raises(ValueError):
        ressortbeleg.lesen(roh)


def test_unerwartete_seitenzahl_ist_kein_beleg(monkeypatch):
    roh = mini_pdf()
    monkeypatch.setattr(ressortbeleg, "ORIGINAL_SHA256", hashlib.sha256(roh).hexdigest())
    with pytest.raises(ValueError, match="ressort_pdf"):
        ressortbeleg.lesen(roh)
