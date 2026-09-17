"""Der Mitgliedsausweis (FB-K8, A0-12): eine Zeichnung, zwei Ausgaben.

- **PDF im EC-Kartenformat** (ID-1: 85,60 × 53,98 mm) samt 1,5 mm Beschnitt je Seite — Seite
  88,60 × 56,98 mm, `TrimBox` auf das Kartenmaß, alles Farbige läuft in den Beschnitt. Vektor,
  also auflösungsunabhängig (deckt 1046 × 673 wie 2093 × 1346 px ab). Zwei Seiten: Vorder- und
  Rückseite. Der Ausweis hängt am Freischaltungsbrief (`mitglieder/post.py`) und steht im Profil
  zum Herunterladen.
- **SVG** derselben Zeichnung für die Vorschau im Profil — Bild und PDF kommen aus einer Quelle.

Ohne neue Abhängigkeit: Der PDF-Schreiber unten kennt genau das, was die Karte braucht — Flächen
mit runden Ecken, Text in den Standardschriften (Helvetica, ohne Einbettung; WinAnsi deckt die
Umlaute), das Logo als Schablonenmaske aus dem Alphakanal des PNG (gefüllt in der jeweiligen
Farbe) und die QR-Module als Rechtecke (`segno` liefert die Matrix). Das ist keine PDF-Bibliothek,
und es will keine sein; ReportLab oder fpdf2 bräuchten ein ADR.

Was auf der Karte steht: Klarname (ersatzweise Anzeigename), Mitgliedsnummer (die Kontonummer),
„Mitglied seit“ (Beitrittsmonat), Identitätsstufe, ein QR-Code mit dem Prüflink. Keine Adresse,
kein Lichtbild, keine Werbung. Der Prüflink führt auf eine öffentliche Seite, die nur „gültig“
oder „nicht gültig“ sagt (Nummer, Beitrittsmonat, Stufe — kein Name).
"""

from __future__ import annotations

import base64
import secrets
import struct
import zlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.utils import formats, timezone, translation
from django.utils.translation import gettext as _

from mitglieder.models import Identitaetsstufe, Mitglied, Mitgliedsstatus
from verfahren.models import AuditEintrag

# ── Maße (mm) ────────────────────────────────────────────────────────────────────────────────

BESCHNITT_MM = 1.5
KARTE_BREITE_MM = 85.60  # ISO/IEC 7810 ID-1 — die EC-Karte
KARTE_HOEHE_MM = 53.98
SEITE_BREITE_MM = KARTE_BREITE_MM + 2 * BESCHNITT_MM  # 88,60
SEITE_HOEHE_MM = KARTE_HOEHE_MM + 2 * BESCHNITT_MM  # 56,98
ECKE_MM = 3.18  # Eckradius der ID-1-Karte — nur die Vorschau zeigt ihn, der Druck schneidet
PT = 72 / 25.4  # Punkt je Millimeter

# ── Farben (Tokens der Design-Spezifikation, base.html) ──────────────────────────────────────

TIEFE = "#0E4C5C"
GOLD = "#D9A441"
GOLD_SANFT = "#E8C27A"
PAPIER = "#FFFFFF"
LEISTENTINTE = "#E9E4D8"
TINTE = "#14232E"
GRUND = "#F4F1E9"
MATT = "#5E6F7A"

LOGO = Path(__file__).resolve().parent / "static" / "mitglieder" / "ddoe-logo.png"
CODE_LAENGE = 10  # Hex-Zeichen des Prüfcodes

#: Die Identitätsstufe in Kartenlänge — die Auswahltexte des Modells sind Sätze.
STUFE_KURZ = {
    Identitaetsstufe.GEPRUEFT: "geprüft",
    Identitaetsstufe.PRAESENZ: "persönlich geprüft",
    Identitaetsstufe.EID: "elektronisch geprüft",
}


# ── Daten ────────────────────────────────────────────────────────────────────────────────────


@dataclass(frozen=True)
class Ausweis:
    nummer: int
    name: str
    seit: str
    stufe: str
    ausgestellt: str
    code: str
    pruef_url: str

    @property
    def nummer_text(self) -> str:
        return f"{self.nummer:06d}"


def ausweis_moeglich(mitglied: Mitglied) -> bool:
    """Einen Ausweis bekommt, wer Mitglied ist: aktives Konto, geprüfte Identität (§ 4 Abs 1),
    nicht ausgetreten oder ausgeschlossen."""
    return (
        mitglied.is_active
        and mitglied.identitaetsstufe != Identitaetsstufe.UNGEPRUEFT
        and mitglied.status not in (Mitgliedsstatus.AUSGETRETEN, Mitgliedsstatus.AUSGESCHLOSSEN)
    )


def ausweis_gueltig(mitglied: Mitglied | None, code: str) -> bool:
    """Die Prüfseite: gültig ist ein Ausweis nur mit dem vergebenen Code und solange die
    Mitgliedschaft besteht — nach Austritt oder Ausschluss sagt sie „nicht gültig“."""
    return (
        mitglied is not None
        and bool(mitglied.ausweis_code)
        and secrets.compare_digest(mitglied.ausweis_code, code)
        and ausweis_moeglich(mitglied)
    )


def ausweis_code_sicherstellen(mitglied: Mitglied, jetzt=None) -> str:
    """Vergibt den Prüfcode einmal je Konto — mit dem ersten Ausweis; danach bleibt er, damit
    QR-Codes gedruckter Karten weiter stimmen. Audit nur mit der Mitgliedsnummer."""
    if mitglied.ausweis_code:
        return mitglied.ausweis_code
    mitglied.ausweis_code = secrets.token_hex(CODE_LAENGE // 2)
    mitglied.ausweis_ausgestellt_am = jetzt or timezone.now()
    mitglied.save(update_fields=["ausweis_code", "ausweis_ausgestellt_am"])
    AuditEintrag.anhaengen({"typ": "ausweis_ausgestellt", "mitglied": mitglied.pk})
    return mitglied.ausweis_code


def pruef_url(mitglied: Mitglied) -> str:
    basis = settings.DDOE_BASIS_URL.rstrip("/")
    return f"{basis}/ausweis/{mitglied.pk}/{mitglied.ausweis_code}/"


def ausweis_daten(mitglied: Mitglied) -> Ausweis:
    """Die Angaben der Karte — immer Deutsch (wie die Briefe; ein Sprachfeld am Konto gibt es nicht)."""
    ausweis_code_sicherstellen(mitglied)
    with translation.override("de"):
        beitritt = mitglied.beitritt or timezone.localdate(mitglied.ausweis_ausgestellt_am)
        return Ausweis(
            nummer=mitglied.pk,
            name=mitglied.get_full_name() or mitglied.anzeigename,
            seit=formats.date_format(beitritt, "F Y"),
            stufe=STUFE_KURZ.get(mitglied.identitaetsstufe, "geprüft"),
            ausgestellt=formats.date_format(timezone.localdate(mitglied.ausweis_ausgestellt_am), "d.m.Y"),
            code=mitglied.ausweis_code,
            pruef_url=pruef_url(mitglied),
        )


def dateiname(mitglied: Mitglied) -> str:
    return f"Mitgliedsausweis-DDOE-{mitglied.pk:06d}.pdf"


# ── Schriftmaße: Helvetica-Breiten (Adobe-Standardmetrik, 1/1000 em) für das Einpassen ───────

_BREITEN = {
    " ": 278, "!": 278, '"': 355, "#": 556, "$": 556, "%": 889, "&": 667, "'": 191, "(": 333, ")": 333,
    "*": 389, "+": 584, ",": 278, "-": 333, ".": 278, "/": 278, "0": 556, "1": 556, "2": 556, "3": 556,
    "4": 556, "5": 556, "6": 556, "7": 556, "8": 556, "9": 556, ":": 278, ";": 278, "=": 584, "?": 556,
    "@": 1015, "A": 667, "B": 667, "C": 722, "D": 722, "E": 667, "F": 611, "G": 778, "H": 722, "I": 278,
    "J": 500, "K": 667, "L": 556, "M": 833, "N": 722, "O": 778, "P": 667, "Q": 778, "R": 722, "S": 667,
    "T": 611, "U": 722, "V": 667, "W": 944, "X": 667, "Y": 667, "Z": 611, "a": 556, "b": 556, "c": 500,
    "d": 556, "e": 556, "f": 278, "g": 556, "h": 556, "i": 222, "j": 222, "k": 500, "l": 222, "m": 833,
    "n": 556, "o": 556, "p": 556, "q": 556, "r": 333, "s": 500, "t": 278, "u": 556, "v": 500, "w": 722,
    "x": 500, "y": 500, "z": 500, "Ä": 667, "Ö": 778, "Ü": 722, "ä": 556, "ö": 556, "ü": 556, "ß": 611,
    "§": 556, "·": 278, "–": 556, "—": 1000, "„": 333, "“": 333, "é": 556, "è": 556, "á": 556, "à": 556,
}
_BREITEN_FETT = {
    **_BREITEN, "a": 556, "c": 556, "e": 556, "f": 333, "i": 278, "j": 278, "k": 556, "l": 278, "m": 889,
    "r": 389, "s": 556, "t": 333, "v": 556, "w": 778, "x": 556, "y": 556, "A": 722, "B": 722, "J": 556,
    "K": 722, "L": 611, "?": 611, "&": 722, "'": 238, '"': 474, "„": 500, "“": 500,
}


def textbreite_mm(text: str, groesse_pt: float, fett: bool = False, laufweite_pt: float = 0.0) -> float:
    tabelle = _BREITEN_FETT if fett else _BREITEN
    em = sum(tabelle.get(z, 600) for z in text) / 1000
    return (em * groesse_pt + laufweite_pt * max(len(text) - 1, 0)) / PT


def _einpassen(text: str, groesse_pt: float, breite_mm: float, fett: bool, mindest_pt: float) -> float:
    """Die größte Schriftgröße ≤ `groesse_pt`, mit der der Text in die Breite passt — nie unter `mindest_pt`."""
    while groesse_pt > mindest_pt and textbreite_mm(text, groesse_pt, fett) > breite_mm:
        groesse_pt -= 0.5
    return groesse_pt


def _umbrechen(text: str, groesse_pt: float, breite_mm: float, fett: bool = False) -> list[str]:
    zeilen, zeile = [], ""
    for wort in text.split():
        probe = f"{zeile} {wort}".strip()
        if zeile and textbreite_mm(probe, groesse_pt, fett) > breite_mm:
            zeilen.append(zeile)
            zeile = wort
        else:
            zeile = probe
    if zeile:
        zeilen.append(zeile)
    return zeilen


# ── Das Logo: Schablone aus dem Alphakanal des PNG ───────────────────────────────────────────


@lru_cache(maxsize=1)
def _png(pfad: str = str(LOGO)) -> tuple[int, int, bytes, bytes]:
    """Breite, Höhe, die Zeichenfläche (ein Byte je Pixel: 1 = dunkel und deckend, 0 = frei) und
    die Rohdatei — nur 8-Bit-PNG ohne Verschachtelung, Farbtyp 6 (RGBA), 4 (Grau+Alpha), 2 (RGB)
    oder 0 (Grau). Das Logo ist schwarz mit deckend weißen Innenflächen; gemalt wird nur das Schwarze."""
    daten = Path(pfad).read_bytes()
    if daten[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Logo ist kein PNG.")
    pos, idat, breite, hoehe, farbtyp = 8, [], 0, 0, 0
    while pos + 8 <= len(daten):
        laenge = int.from_bytes(daten[pos : pos + 4], "big")
        typ = daten[pos + 4 : pos + 8]
        inhalt = daten[pos + 8 : pos + 8 + laenge]
        if typ == b"IHDR":
            breite, hoehe, tiefe, farbtyp, _komp, _filt, verschachtelt = struct.unpack(">IIBBBBB", inhalt)
            if tiefe != 8 or verschachtelt:
                raise ValueError("Logo muss ein 8-Bit-PNG ohne Verschachtelung sein.")
        elif typ == b"IDAT":
            idat.append(inhalt)
        pos += 12 + laenge
    kanaele = {0: 1, 2: 3, 4: 2, 6: 4}[farbtyp]
    roh = zlib.decompress(b"".join(idat))
    schritt = breite * kanaele
    vorige = bytearray(schritt)
    flaeche = bytearray()
    for zeile in range(hoehe):
        start = zeile * (schritt + 1)
        filter_typ = roh[start]
        akt = bytearray(roh[start + 1 : start + 1 + schritt])
        if filter_typ == 1:  # Sub
            for i in range(kanaele, schritt):
                akt[i] = (akt[i] + akt[i - kanaele]) & 0xFF
        elif filter_typ == 2:  # Up
            for i in range(schritt):
                akt[i] = (akt[i] + vorige[i]) & 0xFF
        elif filter_typ == 3:  # Average
            for i in range(schritt):
                links = akt[i - kanaele] if i >= kanaele else 0
                akt[i] = (akt[i] + ((links + vorige[i]) >> 1)) & 0xFF
        elif filter_typ == 4:  # Paeth
            for i in range(schritt):
                a = akt[i - kanaele] if i >= kanaele else 0
                b = vorige[i]
                c = vorige[i - kanaele] if i >= kanaele else 0
                p = a + b - c
                pa, pb, pc = abs(p - a), abs(p - b), abs(p - c)
                vorhersage = a if pa <= pb and pa <= pc else b if pb <= pc else c
                akt[i] = (akt[i] + vorhersage) & 0xFF
        for x in range(breite):
            px = akt[x * kanaele : (x + 1) * kanaele]
            deckend = px[-1] >= 128 if farbtyp in (4, 6) else True
            hell = sum(px[:3]) // 3 if farbtyp in (2, 6) else px[0]
            flaeche.append(1 if deckend and hell < 128 else 0)
        vorige = akt
    return breite, hoehe, bytes(flaeche), daten


@lru_cache(maxsize=1)
def _logo_schablone() -> tuple[int, int, bytes]:
    """1 Bit je Pixel, zeilenweise auf Bytes aufgefüllt: 0 = malen, 1 = frei — genau die Form,
    die ein PDF-`ImageMask` erwartet (Decode-Vorgabe [0 1])."""
    breite, hoehe, flaeche, _ = _png()
    zeilenbytes = (breite + 7) // 8
    bits = bytearray()
    for y in range(hoehe):
        zeile = bytearray(b"\xff" * zeilenbytes)
        basis = y * breite
        for x in range(breite):
            if flaeche[basis + x]:
                zeile[x >> 3] &= ~(0x80 >> (x & 7)) & 0xFF
        bits += zeile
    return breite, hoehe, bytes(bits)


# ── Die Zeichnung: ein Blatt, zwei Ausgaben ──────────────────────────────────────────────────


def _rgb(hexfarbe: str) -> tuple[float, float, float]:
    h = hexfarbe.lstrip("#")
    return tuple(int(h[i : i + 2], 16) / 255 for i in (0, 2, 4))  # type: ignore[return-value]


class Zeichner:
    """Koordinaten in Millimetern, Ursprung links oben (wie am Bildschirm); jede Ausgabe rechnet um."""

    def seite_beginnen(self, hintergrund: str) -> None:
        raise NotImplementedError

    def flaeche(self, x: float, y: float, b: float, h: float, farbe: str, radius: float = 0.0) -> None:
        raise NotImplementedError

    def text(self, x: float, y: float, inhalt: str, groesse: float, farbe: str, fett: bool = False,
             kursiv: bool = False, laufweite: float = 0.0) -> None:
        """`y` ist die Grundlinie; `groesse` und `laufweite` in Punkt."""
        raise NotImplementedError

    def logo(self, x: float, y: float, groesse: float, farbe: str) -> None:
        raise NotImplementedError

    def qr(self, x: float, y: float, groesse: float, matrix, farbe: str) -> None:
        raise NotImplementedError


def _qr_matrix(inhalt: str):
    import segno

    return segno.make(inhalt, error="m").matrix


def zeichne_vorderseite(z: Zeichner, a: Ausweis) -> None:
    """Tiefe Fläche, Goldlinie, weißes Logo, Name groß, drei Angaben, QR-Code im weißen Feld."""
    r = BESCHNITT_MM  # Kartenrand; Innenrand 5 mm ab Kartenrand
    innen = r + 5
    z.seite_beginnen(TIEFE)
    # Ein sanfter Schatten der Tiefe am unteren Rand — Fläche, keine Deko-Grafik
    z.flaeche(0, SEITE_HOEHE_MM - 9.5, SEITE_BREITE_MM, 9.5, "#0B3F4D")
    z.logo(innen, innen - 0.5, 11, PAPIER)
    z.text(innen + 13.5, innen + 3.6, "Direkte Demokratie Österreich", 8.5, PAPIER, fett=True)
    z.text(innen + 13.5, innen + 8.1, "MITGLIEDSAUSWEIS", 6, GOLD, laufweite=1.4)
    z.flaeche(innen, innen + 13.2, SEITE_BREITE_MM - 2 * innen, 0.3, GOLD)
    # Name über die volle Breite; darunter links drei Angaben, rechts der QR-Code
    name_groesse = _einpassen(a.name, 13, SEITE_BREITE_MM - 2 * innen, True, 8)
    z.text(innen, innen + 18.4, a.name, name_groesse, PAPIER, fett=True)
    feld = 16.5
    fx, fy = SEITE_BREITE_MM - innen - feld, innen + 21.2
    spalten = ((innen, "MITGLIEDSNUMMER", a.nummer_text), (innen + 23.5, "MITGLIED SEIT", a.seit))
    for x, beschriftung, wert in spalten:
        z.text(x, innen + 24.6, beschriftung, 4.6, GOLD_SANFT, laufweite=0.7)
        z.text(x, innen + 28.8, wert, _einpassen(wert, 8, 21, False, 6), PAPIER)
    z.text(innen, innen + 33.6, "IDENTITÄT", 4.6, GOLD_SANFT, laufweite=0.7)
    z.text(innen, innen + 37.8, a.stufe, _einpassen(a.stufe, 8, fx - innen - 3, False, 6), PAPIER)
    z.text(innen, SEITE_HOEHE_MM - innen - 0.6, "Wir sind das Werkzeug.", 6, GOLD, kursiv=True)
    z.text(innen + 31, SEITE_HOEHE_MM - innen - 0.6, "parlament.ddoe.at", 6, LEISTENTINTE)
    # QR: weißes Feld rechts, Module mit 1,3 mm Ruhezone — Prüflink der Karte
    z.flaeche(fx, fy, feld, feld, PAPIER, radius=1.6)
    z.qr(fx + 1.3, fy + 1.3, feld - 2.6, _qr_matrix(a.pruef_url), TINTE)


def zeichne_rueckseite(z: Zeichner, a: Ausweis) -> None:
    """Helle Rückseite: worum es geht, Prüfadresse, Ausstellung, Kontakt."""
    innen = BESCHNITT_MM + 5
    z.seite_beginnen(GRUND)
    z.flaeche(0, 0, SEITE_BREITE_MM, 8.5, TIEFE)
    z.logo(innen, 1.6, 5.3, PAPIER)
    z.text(innen + 7, 5.7, "Direkte Demokratie Österreich", 6.5, PAPIER, fett=True)
    z.text(SEITE_BREITE_MM - innen - 14.5, 5.7, "Rückseite", 5, LEISTENTINTE)
    y = 15.5
    for zeile in _umbrechen(
        "Dieser Ausweis gehört zu einer Mitgliedschaft bei Direkte Demokratie Österreich (DDÖ). "
        "Er gilt, solange die Mitgliedschaft besteht, und ist jederzeit prüfbar unter:",
        6.2, SEITE_BREITE_MM - 2 * innen,
    ):
        z.text(innen, y, zeile, 6.2, TINTE)
        y += 3.4
    z.text(innen, y + 0.8, a.pruef_url.replace("https://", ""), _einpassen(a.pruef_url, 6.4, SEITE_BREITE_MM - 2 * innen, True, 5), TIEFE, fett=True)
    y += 8.2
    zeile = f"Mitgliedsnummer {a.nummer_text} · ausgestellt am {a.ausgestellt} · Identität {a.stufe}"
    z.text(innen, y, zeile, _einpassen(zeile, 5.6, SEITE_BREITE_MM - 2 * innen, False, 4.5), MATT)
    z.flaeche(innen, y + 3.2, SEITE_BREITE_MM - 2 * innen, 0.3, GOLD)
    z.text(innen, y + 8.4, "Kontakt: didide@ddoe.at · www.ddoe.at · plattform@ddoe.at", 5.6, TINTE)
    z.text(innen, y + 12.4, "Die Mitgliederversammlung entscheidet — eine Person, eine Stimme (§ 4 Abs 4).", 5.6, TINTE)
    z.text(innen, SEITE_HOEHE_MM - innen - 0.5, "Wir sind das Werkzeug.", 6, TIEFE, kursiv=True)


# ── Ausgabe 1: PDF ───────────────────────────────────────────────────────────────────────────


def _pdf_string(text: str) -> bytes:
    roh = text.encode("cp1252", "replace")
    return b"(" + roh.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)") + b")"


def _f(wert: float) -> str:
    return f"{wert:.3f}".rstrip("0").rstrip(".")


class PdfZeichner(Zeichner):
    FONTS = {(False, False): "/F1", (True, False): "/F2", (False, True): "/F3", (True, True): "/F4"}

    def __init__(self) -> None:
        self.seiten: list[list[str]] = []

    @property
    def _s(self) -> list[str]:
        return self.seiten[-1]

    @staticmethod
    def _y(y_mm: float) -> float:
        return (SEITE_HOEHE_MM - y_mm) * PT

    def seite_beginnen(self, hintergrund: str) -> None:
        self.seiten.append([])
        self.flaeche(0, 0, SEITE_BREITE_MM, SEITE_HOEHE_MM, hintergrund)

    def _farbe(self, farbe: str) -> str:
        return " ".join(_f(c) for c in _rgb(farbe)) + " rg"

    def flaeche(self, x, y, b, h, farbe, radius=0.0):
        x0, y0, bp, hp = x * PT, self._y(y + h), b * PT, h * PT
        if radius <= 0:
            self._s.append(f"{self._farbe(farbe)} {_f(x0)} {_f(y0)} {_f(bp)} {_f(hp)} re f")
            return
        rp = min(radius * PT, bp / 2, hp / 2)
        k = 0.5523 * rp
        x1, y1 = x0 + bp, y0 + hp
        pfad = [
            f"{_f(x0 + rp)} {_f(y0)} m",
            f"{_f(x1 - rp)} {_f(y0)} l {_f(x1 - rp + k)} {_f(y0)} {_f(x1)} {_f(y0 + rp - k)} {_f(x1)} {_f(y0 + rp)} c",
            f"{_f(x1)} {_f(y1 - rp)} l {_f(x1)} {_f(y1 - rp + k)} {_f(x1 - rp + k)} {_f(y1)} {_f(x1 - rp)} {_f(y1)} c",
            f"{_f(x0 + rp)} {_f(y1)} l {_f(x0 + rp - k)} {_f(y1)} {_f(x0)} {_f(y1 - rp + k)} {_f(x0)} {_f(y1 - rp)} c",
            f"{_f(x0)} {_f(y0 + rp)} l {_f(x0)} {_f(y0 + rp - k)} {_f(x0 + rp - k)} {_f(y0)} {_f(x0 + rp)} {_f(y0)} c h f",
        ]
        self._s.append(f"{self._farbe(farbe)} " + " ".join(pfad))

    def text(self, x, y, inhalt, groesse, farbe, fett=False, kursiv=False, laufweite=0.0):
        font = self.FONTS[(fett, kursiv)]
        self._s.append(
            f"BT {self._farbe(farbe)} {font} {_f(groesse)} Tf {_f(laufweite)} Tc "
            f"1 0 0 1 {_f(x * PT)} {_f(self._y(y))} Tm {_pdf_string(inhalt).decode('latin-1')} Tj ET"
        )

    def logo(self, x, y, groesse, farbe):
        self._s.append(
            f"q {self._farbe(farbe)} {_f(groesse * PT)} 0 0 {_f(groesse * PT)} {_f(x * PT)} {_f(self._y(y + groesse))} cm /Logo Do Q"
        )

    def qr(self, x, y, groesse, matrix, farbe):
        n = len(matrix)
        modul = groesse / n
        teile = [self._farbe(farbe)]
        for zeile_nr, zeile in enumerate(matrix):
            for spalte, dunkel in enumerate(zeile):
                if dunkel:
                    mx = (x + spalte * modul) * PT
                    my = self._y(y + (zeile_nr + 1) * modul)
                    teile.append(f"{_f(mx)} {_f(my)} {_f(modul * PT + 0.15)} {_f(modul * PT + 0.15)} re")
        teile.append("f")
        self._s.append(" ".join(teile))

    def pdf(self, titel: str, jetzt) -> bytes:
        """Objekte: Katalog, Seitenbaum, je Seite Seite+Inhalt, vier Schriften, das Logo, Info."""
        objekte: list[bytes] = []

        def obj(inhalt: bytes) -> int:
            objekte.append(inhalt)
            return len(objekte)

        def strom(kopf: str, daten: bytes) -> bytes:
            komprimiert = zlib.compress(daten, 9)
            return f"<< {kopf} /Filter /FlateDecode /Length {len(komprimiert)} >>\nstream\n".encode() + komprimiert + b"\nendstream"

        fonts = {}
        for kennung, name in (("/F1", "Helvetica"), ("/F2", "Helvetica-Bold"), ("/F3", "Helvetica-Oblique"), ("/F4", "Helvetica-BoldOblique")):
            fonts[kennung] = obj(f"<< /Type /Font /Subtype /Type1 /BaseFont /{name} /Encoding /WinAnsiEncoding >>".encode())
        breite, hoehe, bits = _logo_schablone()
        logo_nr = obj(strom(f"/Type /XObject /Subtype /Image /Width {breite} /Height {hoehe} /ImageMask true /Decode [0 1]", bits))
        ressourcen = (
            "<< /Font << " + " ".join(f"{k} {n} 0 R" for k, n in fonts.items()) + f" >> /XObject << /Logo {logo_nr} 0 R >> >>"
        )
        seiten_nr = len(objekte) + 1 + 2 * len(self.seiten)  # der Seitenbaum kommt nach den Seiten
        seiten_objekte = []
        mediabox = f"[0 0 {_f(SEITE_BREITE_MM * PT)} {_f(SEITE_HOEHE_MM * PT)}]"
        trimbox = f"[{_f(BESCHNITT_MM * PT)} {_f(BESCHNITT_MM * PT)} {_f((SEITE_BREITE_MM - BESCHNITT_MM) * PT)} {_f((SEITE_HOEHE_MM - BESCHNITT_MM) * PT)}]"
        for inhalt in self.seiten:
            inhalt_nr = obj(strom("", "\n".join(inhalt).encode("latin-1")))
            seiten_objekte.append(
                obj(
                    f"<< /Type /Page /Parent {seiten_nr} 0 R /MediaBox {mediabox} /BleedBox {mediabox} /TrimBox {trimbox} "
                    f"/Resources {ressourcen} /Contents {inhalt_nr} 0 R >>".encode()
                )
            )
        kids = " ".join(f"{n} 0 R" for n in seiten_objekte)
        baum_nr = obj(f"<< /Type /Pages /Kids [{kids}] /Count {len(seiten_objekte)} >>".encode())
        assert baum_nr == seiten_nr
        katalog_nr = obj(f"<< /Type /Catalog /Pages {baum_nr} 0 R >>".encode())
        stempel = timezone.localtime(jetzt).strftime("%Y%m%d%H%M%S")
        info_nr = obj(
            b"<< /Title " + _pdf_string(titel) + b" /Producer (ParlamentPlattform) /Creator (Direkte Demokratie \xd6sterreich)"
            + f" /CreationDate (D:{stempel}) >>".encode()
        )
        # Datei zusammensetzen — Querverweistabelle mit exakten Byte-Offsets
        aus = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for nr, inhalt in enumerate(objekte, start=1):
            offsets.append(len(aus))
            aus += f"{nr} 0 obj\n".encode() + inhalt + b"\nendobj\n"
        xref = len(aus)
        aus += f"xref\n0 {len(objekte) + 1}\n0000000000 65535 f \n".encode()
        for o in offsets:
            aus += f"{o:010d} 00000 n \n".encode()
        aus += f"trailer\n<< /Size {len(objekte) + 1} /Root {katalog_nr} 0 R /Info {info_nr} 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
        return bytes(aus)


# ── Ausgabe 2: SVG (Vorschau) ────────────────────────────────────────────────────────────────


def _svg_text(inhalt: str) -> str:
    return inhalt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


class SvgZeichner(Zeichner):
    """Eine Seite je Aufruf — die Vorschau zeigt Vorder- und Rückseite als zwei Bilder."""

    def __init__(self, beschreibung: str, kennung: str) -> None:
        self.teile: list[str] = []
        self.beschreibung = beschreibung
        self.kennung = kennung  # Präfix aller ids — zwei Bilder auf einer Seite dürfen sich nicht überschneiden

    def seite_beginnen(self, hintergrund: str) -> None:
        self.teile = []
        # Die Vorschau zeigt die geschnittene Karte mit runden Ecken; der Beschnitt bleibt außen weg.
        self.teile.append(
            f'<clipPath id="{self.kennung}-karte"><rect x="{BESCHNITT_MM}" y="{BESCHNITT_MM}" width="{KARTE_BREITE_MM}" '
            f'height="{KARTE_HOEHE_MM}" rx="{ECKE_MM}"/></clipPath>'
        )
        self.teile.append(f'<g clip-path="url(#{self.kennung}-karte)">')
        self.flaeche(0, 0, SEITE_BREITE_MM, SEITE_HOEHE_MM, hintergrund)

    def flaeche(self, x, y, b, h, farbe, radius=0.0):
        rx = f' rx="{_f(radius)}"' if radius else ""
        self.teile.append(f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(b)}" height="{_f(h)}" fill="{farbe}"{rx}/>')

    def text(self, x, y, inhalt, groesse, farbe, fett=False, kursiv=False, laufweite=0.0):
        stil = f'font-size="{_f(groesse / PT)}"' + (' font-weight="700"' if fett else "") + (' font-style="italic"' if kursiv else "")
        if laufweite:
            stil += f' letter-spacing="{_f(laufweite / PT)}"'
        self.teile.append(f'<text x="{_f(x)}" y="{_f(y)}" fill="{farbe}" {stil}>{_svg_text(inhalt)}</text>')

    def logo(self, x, y, groesse, farbe):
        _, _, _, roh = _png()
        daten = base64.b64encode(roh).decode("ascii")
        kennung = f"{self.kennung}-logo{len(self.teile)}"
        # Die Maske nimmt das PNG umgekehrt (weiß, wo das schwarze Logo war) — das Rechteck füllt sie in der Farbe.
        self.teile.append(
            f'<mask id="{kennung}" maskUnits="userSpaceOnUse" x="{_f(x)}" y="{_f(y)}" width="{_f(groesse)}" height="{_f(groesse)}">'
            f'<image href="data:image/png;base64,{daten}" x="{_f(x)}" y="{_f(y)}" width="{_f(groesse)}" height="{_f(groesse)}" '
            f'style="filter:invert(1)"/></mask>'
            f'<rect x="{_f(x)}" y="{_f(y)}" width="{_f(groesse)}" height="{_f(groesse)}" fill="{farbe}" mask="url(#{kennung})"/>'
        )

    def qr(self, x, y, groesse, matrix, farbe):
        n = len(matrix)
        modul = groesse / n
        pfad = []
        for zeile_nr, zeile in enumerate(matrix):
            for spalte, dunkel in enumerate(zeile):
                if dunkel:
                    pfad.append(f"M{_f(x + spalte * modul)} {_f(y + zeile_nr * modul)}h{_f(modul + 0.02)}v{_f(modul + 0.02)}h-{_f(modul + 0.02)}z")
        self.teile.append(f'<path fill="{farbe}" d="{"".join(pfad)}"/>')

    def svg(self) -> str:
        return (
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {SEITE_BREITE_MM} {SEITE_HOEHE_MM}" '
            f'width="100%" role="img" aria-label="{_svg_text(self.beschreibung)}" '
            f'style="font-family:Helvetica,Arial,sans-serif;max-width:420px;display:block">'
            f"<title>{_svg_text(self.beschreibung)}</title>" + "".join(self.teile) + "</g></svg>"
        )


# ── Öffentliche Schnittstelle ────────────────────────────────────────────────────────────────


def ausweis_pdf(mitglied: Mitglied, jetzt=None) -> bytes:
    """Der Ausweis als PDF — Vorder- und Rückseite, Kartenmaß mit Beschnitt."""
    a = ausweis_daten(mitglied)
    z = PdfZeichner()
    zeichne_vorderseite(z, a)
    zeichne_rueckseite(z, a)
    return z.pdf(f"Mitgliedsausweis DDÖ Nr. {a.nummer_text}", jetzt or timezone.now())


def ausweis_svg(mitglied: Mitglied) -> tuple[str, str]:
    """Vorder- und Rückseite als zwei SVG-Bilder für die Vorschau im Profil."""
    a = ausweis_daten(mitglied)
    vorne = SvgZeichner(_("Mitgliedsausweis, Vorderseite: Direkte Demokratie Österreich, Nr. %(nummer)s") % {"nummer": a.nummer_text}, "ausweis-v")
    zeichne_vorderseite(vorne, a)
    hinten = SvgZeichner(_("Mitgliedsausweis, Rückseite mit Prüfadresse"), "ausweis-h")
    zeichne_rueckseite(hinten, a)
    return vorne.svg(), hinten.svg()
