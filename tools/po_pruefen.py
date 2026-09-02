"""Übersetzungswerkzeug ohne gettext: Katalog prüfen und .mo schreiben.

Auf Arbeitsplätzen ohne installiertes gettext laufen `makemessages` und `compilemessages`
nicht. Dieses Skript ersetzt den zweiten Schritt vollständig und den ersten so weit, wie es
für die Definition of Done nötig ist:

    python tools/po_pruefen.py            # Katalog prüfen (leere, unsichere, doppelte Einträge)
    python tools/po_pruefen.py --mo       # locale/en/LC_MESSAGES/django.mo neu schreiben

Der Katalog bleibt handgepflegt. Neue Texte trägt man in die .po ein und ruft `--mo` auf;
der Test `test_uebersetzungen_vollstaendig` sichert, dass die Texte des App-Rahmens dort
stehen. Sobald gettext verfügbar ist, gilt wieder der Weg über `makemessages -l en
--no-location` (der Katalog führt bewusst keine Quellzeilen-Kommentare).
"""

from __future__ import annotations

import argparse
import struct
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):  # die Windows-Konsole schreibt sonst cp1252
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

WURZEL = Path(__file__).resolve().parent.parent
PO = WURZEL / "locale" / "en" / "LC_MESSAGES" / "django.po"
MO = PO.with_suffix(".mo")
KONTEXT_TRENNER = "\x04"


class Eintrag:
    """Ein Katalogeintrag: Quelltext, Übersetzung, ggf. Plural und Kontext."""

    def __init__(self) -> None:
        self.kontext: str | None = None
        self.msgid: str | None = None
        self.msgid_plural: str | None = None
        self.msgstr: str | None = None
        self.formen: list[str] = []
        self.fuzzy = False

    @property
    def schluessel(self) -> str:
        return f"{self.kontext}{KONTEXT_TRENNER}{self.msgid}" if self.kontext else (self.msgid or "")

    @property
    def uebersetzt(self) -> bool:
        return bool(self.msgstr) if not self.formen else all(self.formen)

    def mo_wert(self) -> str:
        return "\x00".join(self.formen) if self.formen else (self.msgstr or "")

    def mo_schluessel(self) -> str:
        return f"{self.schluessel}\x00{self.msgid_plural}" if self.msgid_plural else self.schluessel


def _text(roh: str) -> str:
    """Inhalt eines .po-Strings; die üblichen Maskierungen werden aufgelöst."""
    inhalt = roh.strip()[1:-1]
    return inhalt.replace('\\"', '"').replace("\\n", "\n").replace("\\t", "\t").replace("\\\\", "\\")


def lesen() -> list[Eintrag]:
    eintraege: list[Eintrag] = []
    aktuell = Eintrag()
    modus: str | None = None
    for zeile in PO.read_text(encoding="utf-8").splitlines():
        blank = zeile.strip()
        if not blank:
            if aktuell.msgid is not None:
                eintraege.append(aktuell)
            aktuell, modus = Eintrag(), None
        elif blank.startswith("#"):
            aktuell.fuzzy = aktuell.fuzzy or blank.startswith("#,") and "fuzzy" in blank
        elif blank.startswith("msgctxt "):
            modus, aktuell.kontext = "kontext", _text(blank[8:])
        elif blank.startswith("msgid_plural "):
            modus, aktuell.msgid_plural = "plural", _text(blank[13:])
        elif blank.startswith("msgid "):
            modus, aktuell.msgid = "id", _text(blank[6:])
        elif blank.startswith("msgstr["):
            modus = "form"
            aktuell.formen.append(_text(blank.split("]", 1)[1]))
        elif blank.startswith("msgstr "):
            modus, aktuell.msgstr = "str", _text(blank[7:])
        elif blank.startswith('"'):
            teil = _text(blank)
            if modus == "id":
                aktuell.msgid = (aktuell.msgid or "") + teil
            elif modus == "plural":
                aktuell.msgid_plural = (aktuell.msgid_plural or "") + teil
            elif modus == "str":
                aktuell.msgstr = (aktuell.msgstr or "") + teil
            elif modus == "form" and aktuell.formen:
                aktuell.formen[-1] += teil
            elif modus == "kontext":
                aktuell.kontext = (aktuell.kontext or "") + teil
    if aktuell.msgid is not None:
        eintraege.append(aktuell)
    return eintraege


def pruefen() -> int:
    eintraege = lesen()
    inhalte = [e for e in eintraege if e.msgid]
    leer = [e.schluessel for e in inhalte if not e.uebersetzt]
    fuzzy = [e.schluessel for e in inhalte if e.fuzzy]
    doppelt = sorted({e.schluessel for e in inhalte if [x.schluessel for x in inhalte].count(e.schluessel) > 1})
    for schluessel in leer:
        print(f"LEER:    {schluessel!r}")
    for schluessel in fuzzy:
        print(f"UNSICHER:{schluessel!r}")
    for schluessel in doppelt:
        print(f"DOPPELT: {schluessel!r}")
    print(f"{len(inhalte)} Einträge, {len(leer)} ohne Übersetzung, {len(fuzzy)} unsicher, {len(doppelt)} doppelt")
    return 1 if (leer or fuzzy or doppelt) else 0


def mo_schreiben() -> None:
    """Schreibt die .mo im GNU-Format — Ersatz für msgfmt."""
    eintraege = lesen()
    kopf = next((e for e in eintraege if e.msgid == ""), None)
    paare: list[tuple[bytes, bytes]] = []
    if kopf and kopf.msgstr:
        paare.append((b"", kopf.msgstr.encode("utf-8")))
    for e in eintraege:
        if not e.msgid:
            continue
        paare.append((e.mo_schluessel().encode("utf-8"), e.mo_wert().encode("utf-8")))
    paare.sort(key=lambda p: p[0])

    anzahl = len(paare)
    tabelle_s = 7 * 4
    tabelle_w = tabelle_s + 8 * anzahl
    puffer_start = tabelle_w + 8 * anzahl
    schluessel_bytes = b"".join(k + b"\x00" for k, _ in paare)
    eintrag_s, eintrag_w, versatz_k = b"", b"", puffer_start
    versatz_w = puffer_start + len(schluessel_bytes)
    for k, w in paare:
        eintrag_s += struct.pack("<II", len(k), versatz_k)
        eintrag_w += struct.pack("<II", len(w), versatz_w)
        versatz_k += len(k) + 1
        versatz_w += len(w) + 1
    daten = struct.pack("<Iiiiiii", 0x950412DE, 0, anzahl, tabelle_s, tabelle_w, 0, 0)
    daten += eintrag_s + eintrag_w + schluessel_bytes + b"".join(w + b"\x00" for _, w in paare)
    MO.write_bytes(daten)
    print(f"{MO.relative_to(WURZEL)} geschrieben: {anzahl} Einträge")


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--mo", action="store_true", help="Katalog nach .mo kompilieren")
    args = p.parse_args()
    code = pruefen()
    if args.mo and code == 0:
        mo_schreiben()
    sys.exit(code)
