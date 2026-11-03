"""Nur den bekannten Originalbeleg prüfen; keine Quellen-/Modell-/Datenbankaufrufe."""

import hashlib
from io import BytesIO

from plattform_core.personalbeleg import VERSION, aus_text

QUELLE = "https://oeffentlicherdienst.gv.at/wp-content/uploads/2026/03/Das-Personal-des-Bundes-2026-1.pdf"
ORIGINAL_SHA256 = "40e720bb4aee9ae26df87452498c9e1021966d4b9a54288c46ccafa7b06ffd63"
HOECHSTBYTES = 6 * 1024 * 1024  # Schutz vor dem PDF-Parser; bekannter Beleg rund4.2MiB
PDF_SEITEN = 212
PDF_INDEX = 76


def lesen(inhalt):
    if not isinstance(inhalt, bytes) or not inhalt or len(inhalt) > HOECHSTBYTES or not inhalt.startswith(b"%PDF-"):
        raise ValueError("personal_datei")
    sha = hashlib.sha256(inhalt).hexdigest()
    if sha != ORIGINAL_SHA256:
        raise ValueError("personal_unbekannter_beleg")
    # Die Bibliothek erhält niemals frei gewählte/unbekannte PDF-Bytes.
    from pypdf import PdfReader

    try:
        reader = PdfReader(BytesIO(inhalt), strict=True)
        if reader.is_encrypted or len(reader.pages) != PDF_SEITEN:
            raise ValueError("personal_pdf")
        text = reader.pages[PDF_INDEX].extract_text()
    except Exception as fehler:
        raise ValueError("personal_pdf") from fehler
    return {**aus_text(text), "quelle": QUELLE, "original_sha256": sha,
            "parser_fassung": VERSION, "seite": 75, "tabelle": 20,
            "publikation": "Das Personal des Bundes 2026 – Daten und Fakten",
            "bereich": "Bundespersonal nach Art des Dienstverhältnisses"}
