"""Menschlichkeitsprüfung bei Registrierung und Login-Anforderung (F-49).

Bewusst OHNE Drittanbieter (kein reCAPTCHA, kein externer Dienst — keine
Datenweitergabe, keine Abhängigkeit) und OHNE JavaScript-Pflicht. Vier Lagen:

1. Honigtopf: ein für Menschen unsichtbares Feld — wer es ausfüllt, ist ein Bot.
2. Mindestzeit: das Formular trägt einen signierten Zeitstempel; wer schneller
   abschickt, als ein Mensch lesen kann, ist ein Bot.
3. Rechenfrage: eine simple Addition, serverseitig signiert und geprüft.
4. Drossel: je IP-Adresse nur wenige Versuche pro Stunde.

Das hält Massen-Bots und Formular-Spam ab. Gegen gezielte, bezahlte Angriffe
schützt es nicht — das muss es auch nicht: Rechte auf der Plattform gibt es
erst nach menschlicher Identitätsprüfung (§ 4, Identitätsstufen), und die
Beitrittswellen-Erkennung (F-04) meldet Auffälligkeiten dem Integritätsrat.
"""

from __future__ import annotations

import secrets
import time

from django import forms
from django.conf import settings
from django.core import signing
from django.core.cache import cache

SALZ = "ddoe-botschutz"
GUELTIG_SEKUNDEN = 3600


def mindestzeit() -> int:
    """Sekunden, die zwischen Anzeigen und Absenden mindestens vergehen müssen."""
    return getattr(settings, "DDOE_BOT_MINDESTZEIT", 5)


def aufgabe_erstellen() -> tuple[str, str]:
    """Erzeugt (frage_svg, signiertes_token) für ein frisches Formular."""
    a, b = secrets.randbelow(8) + 1, secrets.randbelow(8) + 1
    token = signing.dumps({"a": a, "b": b, "t": time.time()}, salt=SALZ)
    return aufgabe_als_bild(a, b), token


def aufgabe_als_bild(a: int, b: int) -> str:
    """Zeichnet die Rechenaufgabe als verzerrtes SVG-Bild (Captcha-Optik).

    Die Aufgabe steht bewusst NUR im Bild, nicht im Seitentext — einfache
    Formular-Bots lesen sie so nicht mit. (Barrierefreiheit: temporäre Lösung
    bis ID Austria, F-49/F-32; wer das Bild nicht lesen kann, wird im Formular
    auf didide@ddoe.at verwiesen.)"""

    def zufall(spanne: int) -> int:
        return secrets.randbelow(2 * spanne + 1) - spanne

    zeichen = list(f"{a} + {b} = ?")
    teile = []
    x = 16
    for z in zeichen:
        drehung = zufall(16)
        y = 40 + zufall(7)
        teile.append(
            f'<text x="{x}" y="{y}" transform="rotate({drehung} {x} {y})" '
            f'font-family="Georgia,serif" font-size="30" fill="#0E2230">{z}</text>'
        )
        x += 24
    linien = []
    for _ in range(3):
        linien.append(
            f'<path d="M{zufall(8) + 4},{20 + zufall(14)} C{60 + zufall(30)},{zufall(28) + 18} '
            f'{140 + zufall(30)},{44 + zufall(16)} {x + 4},{28 + zufall(18)}" '
            f'stroke="#B9822B" stroke-width="1.4" fill="none" opacity="0.65"/>'
        )
    punkte = "".join(
        f'<circle cx="{secrets.randbelow(x + 8)}" cy="{secrets.randbelow(56) + 4}" r="1.1" fill="#0E4C5C" opacity="0.5"/>'
        for _ in range(24)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{x + 12}" height="64" '
        f'viewBox="0 0 {x + 12} 64" role="img" aria-label="Sicherheitsaufgabe als Bild">'
        f'<rect width="100%" height="100%" rx="10" fill="#F6F3EC"/>'
        f"{''.join(linien)}{''.join(teile)}{punkte}</svg>"
    )


def klienten_ip(request) -> str:
    weitergeleitet = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if weitergeleitet:
        return weitergeleitet.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "unbekannt")


def drossel_zuviel(request, zweck: str, limit: int) -> bool:
    """True, wenn diese IP das Stundenlimit für `zweck` erreicht hat."""
    stunde = int(time.time() // 3600)
    schluessel = f"drossel:{zweck}:{klienten_ip(request)}:{stunde}"
    stand = cache.get_or_set(schluessel, 0, timeout=3700)
    if stand >= limit:
        return True
    try:
        cache.incr(schluessel)
    except ValueError:
        cache.set(schluessel, 1, timeout=3700)
    return False


class BotschutzMixin(forms.Form):
    """In Formulare einmischen; im Template unsichtbares Feld + Rechenfrage rendern."""

    # Honigtopf: heißt absichtlich harmlos „website“ — Menschen sehen es nie.
    website = forms.CharField(required=False, widget=forms.HiddenInput, label="")
    pruefung = forms.CharField(widget=forms.HiddenInput)
    rechenfrage = forms.IntegerField(label="Sicherheitsfrage")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        nutzlast = None
        if self.is_bound:
            try:
                nutzlast = signing.loads(self.data.get("pruefung", ""), salt=SALZ, max_age=GUELTIG_SEKUNDEN)
            except signing.BadSignature:
                nutzlast = None
        self.fields["rechenfrage"].label = "Sicherheitsfrage: Ergebnis der Rechnung im Bild"
        self.fields["rechenfrage"].help_text = (
            "Bitte lösen Sie die kleine Rechnung im Bild. Falls Sie das Bild nicht lesen können, "
            "schreiben Sie uns an didide@ddoe.at — wir helfen sofort."
        )
        if nutzlast:
            # Gleiche Aufgabe erneut anzeigen (z. B. nach einem Tippfehler im Formular).
            self.captcha_svg = aufgabe_als_bild(nutzlast["a"], nutzlast["b"])
        else:
            self.captcha_svg, token = aufgabe_erstellen()
            self.initial["pruefung"] = token

    def clean(self):
        daten = super().clean()
        fehler = "Die Sicherheitsfrage wurde nicht richtig beantwortet — bitte erneut versuchen."
        if daten.get("website"):
            raise forms.ValidationError(fehler)  # Honigtopf gefüllt
        try:
            nutzlast = signing.loads(daten.get("pruefung", ""), salt=SALZ, max_age=GUELTIG_SEKUNDEN)
        except signing.BadSignature:
            raise forms.ValidationError(fehler) from None
        if time.time() - nutzlast["t"] < mindestzeit():
            raise forms.ValidationError(fehler)  # schneller als ein Mensch lesen kann
        if daten.get("rechenfrage") != nutzlast["a"] + nutzlast["b"]:
            self.add_error("rechenfrage", fehler)
        return daten
