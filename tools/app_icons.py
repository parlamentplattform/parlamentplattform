"""Erzeugt die App-Symbole für das Web-App-Manifest (Teil 7) aus dem DDÖ-Logo — einmalig, das
Ergebnis ist eingecheckt (`verfahren/static/verfahren/icon-*.png`). Pillow ist dafür nur auf
dem Arbeitsplatz nötig, nie zur Laufzeit.

    python tools/app_icons.py

- icon-192.png, icon-512.png: das Logo in Petrol (--deep) auf Papier (--papier), 8 % Rand.
- icon-maskable-512.png: Papier-Logo auf Petrol, das Logo in der sicheren Zone (innere 80 %,
  Logo auf 56 %), damit runde oder abgerundete Masken nichts abschneiden.

Die Farben sind die Tokens aus base.html (--deep #0E4C5C, --papier #FFFFFF).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image

WURZEL = Path(__file__).resolve().parent.parent
LOGO = WURZEL / "mitglieder" / "static" / "mitglieder" / "ddoe-logo.png"
ZIEL = WURZEL / "verfahren" / "static" / "verfahren"
DEEP = (0x0E, 0x4C, 0x5C)
PAPIER = (0xFF, 0xFF, 0xFF)


def _gefaerbt(logo: Image.Image, vorder: tuple[int, int, int], grund: tuple[int, int, int]) -> Image.Image:
    """Das Logo ist eine schwarz-weiße Scheibe auf transparentem Grund: Schwarz wird zur Vorder-,
    Weiß zur Grundfarbe (nach Helligkeit gemischt), die Transparenz bleibt erhalten."""
    logo = logo.convert("RGBA")
    helligkeit = logo.convert("L")
    dunkel = helligkeit.point(lambda v: 255 - v)  # 255 = schwarz im Original = Vorderfarbe
    flaeche = Image.composite(Image.new("RGBA", logo.size, vorder + (255,)), Image.new("RGBA", logo.size, grund + (255,)), dunkel)
    flaeche.putalpha(logo.getchannel("A"))
    return flaeche


def symbol(groesse: int, *, anteil: float, vorder: tuple[int, int, int], grund: tuple[int, int, int]) -> Image.Image:
    logo = _gefaerbt(Image.open(LOGO), vorder, grund)
    kante = round(groesse * anteil)
    logo = logo.resize((kante, kante), Image.LANCZOS)
    bild = Image.new("RGBA", (groesse, groesse), grund + (255,))
    rand = (groesse - kante) // 2
    bild.alpha_composite(logo, (rand, rand))
    return bild.convert("RGB")


def main() -> None:
    ZIEL.mkdir(parents=True, exist_ok=True)
    symbol(192, anteil=0.84, vorder=DEEP, grund=PAPIER).save(ZIEL / "icon-192.png", optimize=True)
    symbol(512, anteil=0.84, vorder=DEEP, grund=PAPIER).save(ZIEL / "icon-512.png", optimize=True)
    symbol(512, anteil=0.56, vorder=PAPIER, grund=DEEP).save(ZIEL / "icon-maskable-512.png", optimize=True)
    for datei in sorted(ZIEL.glob("icon-*.png")):
        print(f"{datei.relative_to(WURZEL)}: {datei.stat().st_size} Bytes")


if __name__ == "__main__":
    main()
