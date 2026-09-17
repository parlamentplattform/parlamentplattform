"""Einseitiger Mitgliedsausweis mit 1,5 mm Beschnitt (ADR-010, A0-13).

Nach bestätigter Anmeldung mit Status „Prüfung ausständig“, nach Freischaltung
ohne Angabe der Nachweismethode. Das PDF bettet die Schrift ein und verändert Namen
nicht. Der QR-Code zeigt den aktuellen Status ohne Namen und gewährt keine Rechte.
"""

from __future__ import annotations

import base64
import secrets
import struct
import unicodedata
import zlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from django.conf import settings
from django.utils import formats, timezone, translation
from django.utils.translation import gettext as _
from django.utils.translation import gettext_noop

from mitglieder.models import Identitaetsstufe, Mitglied, Mitgliedsstatus
from verfahren.models import AuditEintrag

# ── Maße (mm) ────────────────────────────────────────────────────────────────────────────────

BESCHNITT_MM = 1.5
SICHERHEIT_MM = 3.0  # innerhalb der Schnittkante bleibt alles Wichtige mindestens so weit weg
KARTE_BREITE_MM = 85.60  # ISO/IEC 7810 ID-1 — die EC-Karte
KARTE_HOEHE_MM = 53.98
SEITE_BREITE_MM = KARTE_BREITE_MM + 2 * BESCHNITT_MM  # 88,60
SEITE_HOEHE_MM = KARTE_HOEHE_MM + 2 * BESCHNITT_MM  # 56,98
ECKE_MM = 3.18  # Eckradius der ID-1-Karte — nur die Vorschau zeigt ihn, der Druck schneidet
INNEN_MM = BESCHNITT_MM + 5.0  # Innenrand der Karte: 5 mm ab Schnittkante
PT = 72 / 25.4  # Punkt je Millimeter
QR_FELD_MM = 18.0  # weißes Feld des QR-Codes
QR_RAND_MM = 1.8  # Ruhezone: 4 Module bei Version 4 (ISO/IEC 18004)

# ── Farben (Tokens der Design-Spezifikation, base.html) ──────────────────────────────────────

TIEFE = "#0E4C5C"
TIEFE_SCHATTEN = "#0B3F4D"
GOLD = "#D9A441"
GOLD_SANFT = "#E8C27A"
PAPIER = "#FFFFFF"
LEISTENTINTE = "#E9E4D8"
TINTE = "#14232E"
GRUND = "#F4F1E9"
MATT = "#5E6F7A"

LOGO = Path(__file__).resolve().parent / "static" / "mitglieder" / "ddoe-logo.png"
CODE_LAENGE = 10  # Hex-Zeichen des Prüfcodes

#: Der Nachweis in Kartenlänge — die Auswahltexte des Modells sind Sätze. „geprüft (Beitragseingang
#: verbucht)“ ist kein Ausweis-Nachweis, sondern die Selbsteinschätzung nach § 4 Abs 3; die Karte
#: sagt darum, was geschah. Deutsch auf der Karte; die Prüfseite übersetzt dieselben Wörter.
STUFE_KURZ = {
    Identitaetsstufe.UNGEPRUEFT: gettext_noop("Prüfung ausständig"),
    Identitaetsstufe.GEPRUEFT: gettext_noop("Beitrag verbucht"),
    Identitaetsstufe.PRAESENZ: gettext_noop("persönlich geprüft"),
    Identitaetsstufe.EID: gettext_noop("elektronisch geprüft"),
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
    plattform: str  # die Adresse der Instanz ohne Schema — steht vorne auf der Karte

    @property
    def nummer_text(self) -> str:
        return f"{self.nummer:06d}"

    @property
    def pruef_adresse(self) -> str:
        return _ohne_schema(self.pruef_url)


def _ohne_schema(url: str) -> str:
    return url.removeprefix("https://").removeprefix("http://").rstrip("/")


def ausweis_moeglich(mitglied: Mitglied) -> bool:
    """Einen gültigen Ausweis hat, wer Mitglied mit geprüfter Stufe ist: aktives Konto, Stufe nicht
    „ungeprüft“ (§ 4 Abs 1 und 3), nicht ausgetreten oder ausgeschlossen."""
    return (
        mitglied.is_active
        and not mitglied.testkonto
        and mitglied.status not in (Mitgliedsstatus.AUSGETRETEN, Mitgliedsstatus.AUSGESCHLOSSEN)
    )


def name_fuer_karte(mitglied: Mitglied) -> str:
    """Der Name auf der Karte: der Klarname, ersatzweise der gewählte Anzeigename. Der Platzhalter
    „Mitglied n“ ist kein Name — dann gibt es keine Karte, bis die Stammdaten ergänzt sind."""
    return " ".join((mitglied.get_full_name() or mitglied.pseudonym_oeffentlich or "").split())


def ausweis_erstellbar(mitglied: Mitglied) -> bool:
    """Ausstellen lässt sich der Ausweis nur mit einem Namen darauf."""
    return ausweis_moeglich(mitglied) and bool(name_fuer_karte(mitglied))


def ausweis_gueltig(mitglied: Mitglied | None, code: str) -> bool:
    """Die Prüfseite: gültig ist ein Ausweis nur mit dem vergebenen Code und solange eine aktive
    Mitgliedschaft mit geprüfter Stufe besteht — nach Austritt, Ausschluss oder Rücknahme der Stufe
    sagt sie „nicht gültig“. Verglichen wird byteweise in konstanter Zeit; ein Code außerhalb von
    ASCII kann nie stimmen und fällt ohne Fehler durch."""
    return (
        mitglied is not None
        and bool(mitglied.ausweis_code)
        and isinstance(code, str)
        and code.isascii()
        and secrets.compare_digest(mitglied.ausweis_code.encode(), code.encode())
        and ausweis_moeglich(mitglied)
        and mitglied.identitaetsstufe != Identitaetsstufe.UNGEPRUEFT
    )


def ausweis_code_sicherstellen(mitglied: Mitglied, jetzt=None) -> str:
    """Vergibt den Prüfcode einmal je Konto — mit dem ersten Ausweis; danach bleibt er, damit
    QR-Codes gedruckter Karten weiter stimmen. Die bedingte UPDATE-Anweisung ist atomar: Zwei
    gleichzeitige erste Aufrufe vergeben genau einen Code. Audit nur mit der Mitgliedsnummer."""
    if mitglied.ausweis_code:
        return mitglied.ausweis_code
    neu = secrets.token_hex(CODE_LAENGE // 2)
    getroffen = Mitglied.objects.filter(pk=mitglied.pk, ausweis_code="").update(
        ausweis_code=neu, ausweis_ausgestellt_am=jetzt or timezone.now()
    )
    mitglied.refresh_from_db(fields=["ausweis_code", "ausweis_ausgestellt_am"])
    if getroffen:
        AuditEintrag.anhaengen({"typ": "ausweis_ausgestellt", "mitglied": mitglied.pk})
    return mitglied.ausweis_code


def pruef_url(mitglied: Mitglied) -> str:
    basis = settings.DDOE_BASIS_URL.rstrip("/")
    return f"{basis}/ausweis/{mitglied.pk}/{mitglied.ausweis_code}/"


def ausweis_daten(mitglied: Mitglied) -> Ausweis:
    """Die Angaben der Karte — immer Deutsch (wie die Briefe; ein Sprachfeld am Konto gibt es nicht)."""
    from mitglieder.nummern import sicherstellen
    nummer = sicherstellen(mitglied)
    if nummer is None:
        raise ValueError("Testkonten erhalten keinen Mitgliedsausweis.")
    ausweis_code_sicherstellen(mitglied)
    with translation.override("de"):
        beitritt = mitglied.beitritt or timezone.localdate(mitglied.ausweis_ausgestellt_am)
        return Ausweis(
            nummer=nummer,
            name=name_fuer_karte(mitglied),
            seit=formats.date_format(beitritt, "F Y"),
            stufe=STUFE_KURZ.get(mitglied.identitaetsstufe, "geprüft"),
            ausgestellt=formats.date_format(timezone.localdate(mitglied.ausweis_ausgestellt_am), "d.m.Y"),
            code=mitglied.ausweis_code,
            pruef_url=pruef_url(mitglied),
            plattform=_ohne_schema(settings.DDOE_BASIS_URL),
        )


def dateiname(mitglied: Mitglied) -> str:
    from mitglieder.nummern import sicherstellen
    return f"Mitgliedsausweis-DDOE-{sicherstellen(mitglied):06d}.pdf"


# ── Schrift: WinAnsi und die Helvetica-Breiten (Adobe-Standardmetrik, 1/1000 em) ─────────────

#: Buchstaben ohne Unicode-Zerlegung, die WinAnsi nicht kennt — NFKD hilft dort nicht.
_ERSATZ = {"Đ": "D", "đ": "d", "Ł": "L", "ł": "l", "ı": "i", "İ": "I", "Ħ": "H", "ħ": "h", "Ŧ": "T", "ŧ": "t", "ŋ": "n", "Ŋ": "N"}


def _winansi(text: str) -> str:
    """Was die Standardschrift nicht kennt, verliert sein Diakritikum (č → c, ş → s, ğ → g) statt zu
    „?“ zu werden; was auch dann nicht darstellbar ist (andere Schriftsysteme, Symbole), entfällt."""
    aus = []
    for z in text:
        try:
            z.encode("cp1252")
            aus.append(z)
            continue
        except UnicodeEncodeError:
            pass
        ersatz = _ERSATZ.get(z) or "".join(c for c in unicodedata.normalize("NFKD", z) if not unicodedata.combining(c))
        try:
            ersatz.encode("cp1252")
            aus.append(ersatz)
        except UnicodeEncodeError:
            pass
    return " ".join("".join(aus).split()) if text.strip() else text


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
    **_BREITEN, "a": 556, "b": 611, "c": 556, "d": 611, "e": 556, "f": 333, "g": 611, "h": 611, "i": 278,
    "j": 278, "k": 556, "l": 278, "m": 889, "n": 611, "o": 611, "p": 611, "q": 611, "r": 389, "s": 556,
    "t": 333, "u": 611, "v": 556, "w": 778, "x": 556, "y": 556, "ö": 611, "ü": 611, "A": 722, "B": 722,
    "J": 556, "K": 722, "L": 611, "Ä": 722, ":": 333, ";": 333, "!": 333, "?": 611, "&": 722, "@": 975,
    "'": 238, '"': 474, "„": 500, "“": 500,
}


def textbreite_mm(text, groesse, fett=False, laufweite_pt=0):
    from mitglieder.ausweis_pdf import textbreite
    return textbreite(text, groesse, fett, laufweite_pt)


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


# ── Das Logo: Schablone aus dem PNG ──────────────────────────────────────────────────────────


@lru_cache(maxsize=1)
def _png(pfad: str = str(LOGO)) -> tuple[int, int, bytes, bytes]:
    """Breite, Höhe, die Zeichenfläche (ein Byte je Pixel: 1 = dunkel und deckend, 0 = frei) und
    die Rohdatei — nur 8-Bit-PNG ohne Verschachtelung, Farbtyp 6 (RGBA), 4 (Grau+Alpha), 2 (RGB)
    oder 0 (Grau). Das Logo ist schwarz mit deckend weißen Innenflächen; gemalt wird nur das Schwarze.
    Jede Unlesbarkeit wird ein ValueError — die Aufrufer schicken dann den Brief ohne Anhang und
    zeigen im Profil eine Störung statt eines Fehlers."""
    daten = Path(pfad).read_bytes()
    if daten[:8] != b"\x89PNG\r\n\x1a\n":
        raise ValueError("Logo ist kein PNG.")
    try:
        return _png_lesen(daten)
    except (KeyError, IndexError, struct.error, zlib.error) as e:
        raise ValueError("Logo-PNG nicht lesbar (nur 8-Bit ohne Palette und Verschachtelung).") from e


def _png_lesen(daten: bytes) -> tuple[int, int, bytes, bytes]:
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
    if len(roh) < hoehe * (schritt + 1):
        raise ValueError("Logo-PNG unvollständig.")
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


def _name_zeilen(name: str, breite: float) -> list[tuple[str, float]]:
    """Der Name in einer Zeile bis herunter zu 9 pt; ist er dann noch zu breit, in zwei Zeilen zu
    höchstens 8,5 pt — jede Zeile für sich eingepasst, damit nichts über den Innenrand läuft."""
    groesse = _einpassen(name, 13, breite, True, 9)
    if textbreite_mm(name, groesse, True) <= breite:
        return [(name, groesse)]
    zeilen = _umbrechen(name, 8.5, breite, fett=True)
    erste, zweite = zeilen[0], " ".join(zeilen[1:])
    return [(z, _einpassen(z, 8.5, breite, True, 6)) for z in (erste, zweite) if z]


def zeichne_vorderseite(z: Zeichner, a: Ausweis) -> None:
    """Tiefe Fläche, Goldlinie, weißes Logo, Name groß, drei Angaben, QR-Code im weißen Feld."""
    innen = INNEN_MM
    breite = SEITE_BREITE_MM - 2 * innen
    z.seite_beginnen(TIEFE)
    # Ein sanfter Schatten der Tiefe am unteren Rand — Fläche, keine Deko-Grafik
    z.flaeche(0, SEITE_HOEHE_MM - 8.5, SEITE_BREITE_MM, 8.5, TIEFE_SCHATTEN)
    z.logo(innen, innen - 0.5, 11, PAPIER)
    z.text(innen + 13.5, innen + 3.6, "Direkte Demokratie Österreich", 8.5, PAPIER, fett=True)
    z.text(innen + 13.5, innen + 8.1, "MITGLIEDSAUSWEIS", 6, GOLD_SANFT, laufweite=1.4)
    z.flaeche(innen, innen + 13.2, breite, 0.3, GOLD)
    # Name über die volle Breite (eine Zeile, notfalls zwei); darunter links die Angaben, rechts der QR-Code
    zeilen = _name_zeilen(a.name, breite)
    if len(zeilen) == 1:
        z.text(innen, innen + 18.4, zeilen[0][0], zeilen[0][1], PAPIER, fett=True)
    else:
        for (zeile, groesse), grundlinie in zip(zeilen, (innen + 16.3, innen + 19.9), strict=False):
            z.text(innen, grundlinie, zeile, groesse, PAPIER, fett=True)
    fx, fy = SEITE_BREITE_MM - innen - QR_FELD_MM, innen + 21.2
    spalten = ((innen, "MITGLIEDSNUMMER", a.nummer_text), (innen + 23.5, ("ANGEMELDET SEIT" if a.stufe == "Prüfung ausständig" else "MITGLIED SEIT"), a.seit))
    for x, beschriftung, wert in spalten:
        z.text(x, innen + 24.6, beschriftung, 4.6, GOLD_SANFT, laufweite=0.7)
        z.text(x, innen + 28.8, wert, _einpassen(wert, 8, 21, False, 6), PAPIER)
    if a.stufe == "Prüfung ausständig":
        z.text(innen, innen + 37.8, a.stufe, 8, PAPIER)
    fuss = SEITE_HOEHE_MM - innen + 1.0  # Grundlinie in der Mitte des Schattenbands, 3,5 mm über der Kante
    z.text(innen, fuss, "Wir sind das Werkzeug.", 6, GOLD, kursiv=True)
    z.text(innen + 31, fuss, a.plattform, _einpassen(a.plattform, 6, breite - 31, False, 4.5), LEISTENTINTE)
    # QR: weißes Feld rechts, Ruhezone QR_RAND_MM (4 Module bei Version 4) — Prüflink der Karte
    z.flaeche(fx, fy, QR_FELD_MM, QR_FELD_MM, PAPIER, radius=1.6)
    z.qr(fx + QR_RAND_MM, fy + QR_RAND_MM, QR_FELD_MM - 2 * QR_RAND_MM, _qr_matrix(a.pruef_url), TINTE)


def zeichne_rueckseite(z: Zeichner, a: Ausweis) -> None:
    """Helle Rückseite: worum es geht, Prüfadresse, Ausstellung, Kontakt."""
    innen = INNEN_MM
    breite = SEITE_BREITE_MM - 2 * innen
    z.seite_beginnen(GRUND)
    z.flaeche(0, 0, SEITE_BREITE_MM, 11.0, TIEFE)
    z.logo(innen, 4.5, 5.3, PAPIER)  # Oberkante 3 mm unter der Schnittkante — wie der Innenrand
    z.text(innen + 7, 8.6, "Direkte Demokratie Österreich", 6.5, PAPIER, fett=True)
    z.text(SEITE_BREITE_MM - innen - 14.5, 8.6, "Rückseite", 5, LEISTENTINTE)
    y = 16.0
    for zeile in _umbrechen(
        "Dieser Ausweis gehört zu einer Mitgliedschaft bei Direkte Demokratie Österreich (DDÖ). "
        "Er gilt, solange die Mitgliedschaft mit geprüftem Nachweis besteht, und ist jederzeit prüfbar unter:",
        6.2, breite,
    ):
        z.text(innen, y, zeile, 6.2, TINTE)
        y += 3.4
    z.text(innen, y + 0.8, a.pruef_adresse, _einpassen(a.pruef_adresse, 6.4, breite, True, 5), TIEFE, fett=True)
    y += 8.2
    zeile = f"Mitgliedsnummer {a.nummer_text} · ausgestellt am {a.ausgestellt} · Nachweis: {a.stufe}"
    z.text(innen, y, zeile, _einpassen(zeile, 5.6, breite, False, 4.5), MATT)
    z.flaeche(innen, y + 3.2, breite, 0.3, GOLD)
    z.text(innen, y + 8.4, "Kontakt: didide@ddoe.at · www.ddoe.at · plattform@ddoe.at", 5.6, TINTE)
    leitsatz = "Die Mitgliederversammlung entscheidet — ein Mensch, eine Stimme (§ 3 Abs 1 lit b)."
    z.text(innen, y + 12.4, leitsatz, _einpassen(leitsatz, 5.6, breite, False, 4.5), TINTE)
    z.text(innen, SEITE_HOEHE_MM - innen - 0.5, "Wir sind das Werkzeug.", 6, TIEFE, kursiv=True)


# ── Ausgabe 1: PDF ───────────────────────────────────────────────────────────────────────────


def _pdf_string(text: str) -> bytes:
    roh = _winansi(text).encode("cp1252", "replace")
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
        """Objekte: vier Schriften, das Logo, je Seite Inhalt+Seite, Seitenbaum, Katalog, Info."""
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
            "<< /ProcSet [/PDF /Text /ImageB] /Font << " + " ".join(f"{k} {n} 0 R" for k, n in fonts.items())
            + f" >> /XObject << /Logo {logo_nr} 0 R >> >>"
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
    return inhalt.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


LOGO_BILD_ID = "ausweis-logo-bild"


class SvgZeichner(Zeichner):
    """Eine Seite je Bild — die Vorschau zeigt Vorder- und Rückseite als zwei Bilder auf einer
    Seite. Das Logo (PNG als Base64) trägt nur das erste Bild; das zweite verweist mit `<use>`
    darauf, damit die Profilseite es nicht zweimal lädt. `viewBox` zeigt die geschnittene Karte."""

    def __init__(self, beschreibung: str, kennung: str, logo_einbetten: bool = True) -> None:
        self.teile: list[str] = []
        self.beschreibung = beschreibung
        self.kennung = kennung  # Präfix aller ids — zwei Bilder auf einer Seite dürfen sich nicht überschneiden
        self.logo_einbetten = logo_einbetten

    def seite_beginnen(self, hintergrund: str) -> None:
        self.teile = []
        # Die Vorschau zeigt die geschnittene Karte mit runden Ecken; der Beschnitt bleibt außen weg —
        # auch die viewBox zeigt nur das Kartenmaß, damit Schatten und Rundung an der Karte liegen.
        self.teile.append(
            f'<clipPath id="{self.kennung}-karte"><rect x="{BESCHNITT_MM}" y="{BESCHNITT_MM}" width="{KARTE_BREITE_MM}" '
            f'height="{KARTE_HOEHE_MM}" rx="{ECKE_MM}"/></clipPath>'
        )
        if self.logo_einbetten:
            _, _, _, roh = _png()
            daten = base64.b64encode(roh).decode("ascii")
            # Umgekehrt (weiß, wo das schwarze Logo war): als Leuchtdichte-Maske füllt ein Rechteck die Form.
            self.teile.append(
                f'<defs><image id="{LOGO_BILD_ID}" href="data:image/png;base64,{daten}" x="0" y="0" width="1" height="1" '
                f'preserveAspectRatio="none" style="filter:invert(1)"/></defs>'
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
        kennung = f"{self.kennung}-logo{len(self.teile)}"
        self.teile.append(
            f'<mask id="{kennung}" maskUnits="objectBoundingBox" maskContentUnits="objectBoundingBox" x="0" y="0" width="1" height="1">'
            f'<use href="#{LOGO_BILD_ID}"/></mask>'
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
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{BESCHNITT_MM} {BESCHNITT_MM} {KARTE_BREITE_MM} {KARTE_HOEHE_MM}" '
            f'width="100%" role="img" aria-label="{_svg_text(self.beschreibung)}" '
            f'style="font-family:DDOEKarte,Arial,sans-serif;max-width:420px;display:block">'
            f"<title>{_svg_text(self.beschreibung)}</title>" + "".join(self.teile) + "</g></svg>"
        )


# ── Öffentliche Schnittstelle ────────────────────────────────────────────────────────────────


def ausweis_pdf(mitglied: Mitglied, jetzt=None) -> bytes:
    """Der Ausweis als einseitiges PDF im Kartenmaß mit Beschnitt."""
    a = ausweis_daten(mitglied)
    from mitglieder.ausweis_pdf import UnicodePdfZeichner
    z = UnicodePdfZeichner()
    zeichne_vorderseite(z, a)
    return z.pdf(f"Mitgliedsausweis DDÖ Nr. {a.nummer_text}", jetzt or timezone.now())


def ausweis_svg(mitglied: Mitglied) -> tuple[str, str]:
    """Einseitige Vorschau; der zweite Rückgabewert bleibt aus Kompatibilität leer."""
    a = ausweis_daten(mitglied)
    vorne = SvgZeichner(
        _("Mitgliedsausweis, Vorderseite: %(name)s, Nr. %(nummer)s, seit %(seit)s")
        % {"name": a.name, "nummer": a.nummer_text, "seit": a.seit},
        "ausweis-v",
    )
    zeichne_vorderseite(vorne, a)
    return vorne.svg(), ""
