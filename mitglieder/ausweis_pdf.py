"""PDF-Zeichner mit eingebetteten TrueType-Schriften (ADR-010)."""
from functools import lru_cache
from io import BytesIO
from pathlib import Path
from threading import Lock

from reportlab.lib.colors import HexColor
from reportlab.lib.utils import ImageReader
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen.canvas import Canvas

FONT_LOCK = Lock()


@lru_cache(maxsize=1)
def schriften():
    with FONT_LOCK:
        pfad = Path(__file__).parent / "static" / "mitglieder" / "fonts"
        for name, datei in (("DDOE", "DejaVuSans.ttf"), ("DDOE-Bold", "DejaVuSans-Bold.ttf"),
                            ("DDOE-Italic", "DejaVuSans-Oblique.ttf")):
            if name not in pdfmetrics.getRegisteredFontNames():
                pdfmetrics.registerFont(TTFont(name, str(pfad / datei)))


def schrift(fett=False, kursiv=False):
    schriften()
    return "DDOE-Bold" if fett else "DDOE-Italic" if kursiv else "DDOE"


def textbreite(text, groesse, fett=False, laufweite_pt=0):
    return (pdfmetrics.stringWidth(text, schrift(fett), groesse)
            + max(0, len(text)-1) * laufweite_pt) / (72 / 25.4)


class UnicodePdfZeichner:
    def __init__(self):
        from mitglieder.ausweis import PT, SEITE_BREITE_MM, SEITE_HOEHE_MM
        self.pt = PT
        self.h = SEITE_HOEHE_MM
        self.b = SEITE_BREITE_MM
        self.puffer = BytesIO()
        self.c = Canvas(self.puffer, pagesize=(self.b*PT, self.h*PT), pdfVersion=(1, 4), pageCompression=1)
        self.c.setTrimBox((1.5*PT, 1.5*PT, (self.b-1.5)*PT, (self.h-1.5)*PT))
        self.c.setBleedBox((0, 0, self.b*PT, self.h*PT))

    def seite_beginnen(self, hintergrund):
        self.flaeche(0, 0, self.b, self.h, hintergrund)

    def flaeche(self, x, y, b, h, farbe, radius=0):
        self.c.setFillColor(HexColor(farbe))
        self.c.roundRect(x*self.pt, (self.h-y-h)*self.pt, b*self.pt, h*self.pt,
                         radius*self.pt, stroke=0, fill=1)

    def text(self, x, y, inhalt, groesse, farbe, fett=False, kursiv=False, laufweite=0):
        font = schrift(fett, kursiv)
        fehlend = [z for z in inhalt if ord(z) not in pdfmetrics.getFont(font).face.charToGlyph]
        if fehlend:
            raise ValueError("Die Kartenschrift enthält nicht alle benötigten Zeichen.")
        t = self.c.beginText(x*self.pt, (self.h-y)*self.pt)
        t.setFont(font, groesse)
        t.setFillColor(HexColor(farbe))
        t.setCharSpace(laufweite)
        t.textOut(inhalt)
        self.c.drawText(t)

    def logo(self, x, y, groesse, farbe):
        from PIL import Image

        from mitglieder.ausweis import _logo_schablone
        b, h, daten = _logo_schablone()
        maske = Image.frombytes("1", (b, h), daten).convert("L")
        # PDF-ImageMask: gesetzte Bits sind transparent, Nullbits tragen das Logo.
        from PIL import ImageOps
        bild = Image.new("RGBA", (b, h), farbe)
        bild.putalpha(ImageOps.invert(maske))
        self.c.drawImage(ImageReader(bild), x*self.pt, (self.h-y-groesse)*self.pt,
                         groesse*self.pt, groesse*self.pt, mask="auto")

    def qr(self, x, y, groesse, matrix, farbe):
        modul = groesse/len(matrix)
        for zeile, werte in enumerate(matrix):
            for spalte, dunkel in enumerate(werte):
                if dunkel:
                    self.flaeche(x+spalte*modul, y+zeile*modul, modul, modul, farbe)

    def pdf(self, titel, jetzt):
        self.c.setTitle(titel)
        self.c.setAuthor("Direkte Demokratie Österreich")
        self.c.showPage()
        self.c.save()
        return self.puffer.getvalue()
