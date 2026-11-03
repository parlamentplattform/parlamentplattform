"""Zwei bekannte Seiten des nachgewiesenen Originals, keine freie PDF-Auswahl."""

import hashlib
from io import BytesIO

from faktenbasis.personalbeleg import HOECHSTBYTES, ORIGINAL_SHA256, PDF_SEITEN, QUELLE
from plattform_core.personalressorts import VERSION, aus_text

TABELLE_INDEX = 31
METHODIK_INDEX = 176


def lesen(inhalt):
    if not isinstance(inhalt, bytes) or not inhalt or len(inhalt) > HOECHSTBYTES or not inhalt.startswith(b"%PDF-"):
        raise ValueError("ressort_datei")
    sha = hashlib.sha256(inhalt).hexdigest()
    if sha != ORIGINAL_SHA256:
        raise ValueError("ressort_unbekannter_beleg")
    from pypdf import PdfReader

    try:
        r = PdfReader(BytesIO(inhalt), strict=True)
        if r.is_encrypted or len(r.pages) != PDF_SEITEN:
            raise ValueError("ressort_pdf")
        tabelle = r.pages[TABELLE_INDEX].extract_text()
        methodik = r.pages[METHODIK_INDEX].extract_text()
    except Exception as fehler:
        raise ValueError("ressort_pdf") from fehler
    return {**aus_text(tabelle, methodik), "quelle": QUELLE, "original_sha256": sha,
        "parser_fassung": VERSION, "seite": 30, "methodik_seite": 175, "tabelle": 7,
        "publikation": "Das Personal des Bundes 2026 – Daten und Fakten"}
