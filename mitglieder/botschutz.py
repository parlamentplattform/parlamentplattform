"""Menschlichkeitsprüfung bei Registrierung und Login-Anforderung (F-49).

Bewusst OHNE Drittanbieter (kein reCAPTCHA, kein externer Dienst — keine
Datenweitergabe, keine Abhängigkeit) und OHNE JavaScript-Pflicht. Vier Lagen:

1. Honigtopf: ein für Menschen unsichtbares Feld — wer es ausfüllt, ist ein Bot.
2. Mindestzeit: die Aufgabe trägt serverseitig ihren Zeitstempel; wer schneller
   abschickt, als ein Mensch lesen kann, ist ein Bot.
3. Rechenfrage: eine simple Addition. Die Aufgabe liegt in der Sitzung, die Seite
   trägt nur eine zufällige Kennung — die Lösung verlässt den Server nicht. Eine
   gelöste Aufgabe ist verbraucht; dieselbe Antwort trägt kein zweites Mal.
4. Drossel: je Verbindung nur wenige Versuche pro Stunde. Der Zähler liegt in der
   Datenbank, nicht im prozesslokalen Cache — er gilt über alle Worker hinweg und
   übersteht Neustarts.

Welche Adresse „die Verbindung“ ist, entscheidet allein die Einstellung
DDOE_CLIENT_IP_KOPFZEILE (siehe `klienten_ip`); X-Forwarded-For wird nie gelesen,
denn sein erster Eintrag ist vom Client frei wählbar.

Das hält Massen-Bots und Formular-Spam ab. Gegen gezielte, bezahlte Angriffe
schützt es nicht — die tragende Schicht ist die Drossel, nicht das Rätsel (der
Lösungsraum sind fünfzehn Zahlen). Rechte auf der Plattform gibt es erst nach
Beitragseingang bzw. Identitätsprüfung (§ 4, Identitätsstufen), und die
Beitrittswellen-Erkennung (F-04) meldet Auffälligkeiten dem Integritätsrat.
"""

from __future__ import annotations

import secrets
import time

from django import forms
from django.conf import settings
from django.db import transaction
from django.db.models import F
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

GUELTIG_SEKUNDEN = 3600
SITZUNGSSCHLUESSEL = "botschutz"
HOECHSTZAHL_AUFGABEN = 3  # zwei offene Tabs sollen einander nicht die Aufgabe wegnehmen


def mindestzeit() -> int:
    """Sekunden, die zwischen Anzeigen und Absenden mindestens vergehen müssen."""
    return getattr(settings, "DDOE_BOT_MINDESTZEIT", 5)


def aufgabe_erstellen(request) -> tuple[str, str]:
    """Legt eine frische Aufgabe in der Sitzung ab; gibt (frage_svg, kennung) zurück.

    Die Kennung ist zufällig und verrät nichts; Summanden und Zeitstempel bleiben
    serverseitig (Befund #68 — ein signiertes Token wäre lesbar, nur nicht fälschbar)."""
    a, b = secrets.randbelow(8) + 1, secrets.randbelow(8) + 1
    kennung = secrets.token_urlsafe(16)
    aufgaben = dict(request.session.get(SITZUNGSSCHLUESSEL, {}))
    aufgaben[kennung] = {"a": a, "b": b, "t": time.time()}
    for alt in sorted(aufgaben, key=lambda k: aufgaben[k]["t"])[:-HOECHSTZAHL_AUFGABEN]:
        del aufgaben[alt]  # die ältesten fliegen raus — die Sitzung bleibt klein
    request.session[SITZUNGSSCHLUESSEL] = aufgaben
    return aufgabe_als_bild(a, b), kennung


def aufgabe_lesen(request, kennung: str) -> dict | None:
    """Die Aufgabe zur Kennung, solange sie noch gilt — sonst None."""
    aufgabe = request.session.get(SITZUNGSSCHLUESSEL, {}).get(kennung or "")
    if aufgabe is None or time.time() - aufgabe["t"] > GUELTIG_SEKUNDEN:
        return None
    return aufgabe


def aufgabe_verbrauchen(request, kennung: str) -> None:
    """Gelöst heißt verbraucht: Dieselbe Kennung trägt kein zweites Absenden."""
    aufgaben = dict(request.session.get(SITZUNGSSCHLUESSEL, {}))
    if aufgaben.pop(kennung, None) is not None:
        request.session[SITZUNGSSCHLUESSEL] = aufgaben


def aufgabe_als_bild(a: int, b: int) -> str:
    """Zeichnet die Rechenaufgabe als verzerrtes SVG-Bild (Captcha-Optik).

    Die Aufgabe steht nur im Bild; der Seitentext trägt allein die Kennung.
    (Barrierefreiheit: temporäre Lösung bis ID Austria, F-49/F-32; wer das Bild
    nicht lesen kann, wird im Formular auf didide@ddoe.at verwiesen.)"""

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
    for _nr in range(3):
        linien.append(
            f'<path d="M{zufall(8) + 4},{20 + zufall(14)} C{60 + zufall(30)},{zufall(28) + 18} '
            f'{140 + zufall(30)},{44 + zufall(16)} {x + 4},{28 + zufall(18)}" '
            f'stroke="#B9822B" stroke-width="1.4" fill="none" opacity="0.65"/>'
        )
    punkte = "".join(
        f'<circle cx="{secrets.randbelow(x + 8)}" cy="{secrets.randbelow(56) + 4}" r="1.1" fill="#0E4C5C" opacity="0.5"/>'
        for _punkt in range(24)
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{x + 12}" height="64" '
        f'viewBox="0 0 {x + 12} 64" role="img" aria-label="{_("Sicherheitsaufgabe als Bild")}">'
        f'<rect width="100%" height="100%" rx="10" fill="#F6F3EC"/>'
        f"{''.join(linien)}{''.join(teile)}{punkte}</svg>"
    )


def klienten_ip(request) -> str:
    """Adresse der Verbindung — für Drossel (F-49) und Besuchszählung (F-52).

    Nie X-Forwarded-For: Dessen erster Eintrag ist vom Client frei wählbar, und
    Cloudflare wie Render hängen nur an (Befunde #19, #66). Steht ein vertrauens-
    würdiger Proxy davor, nennt DDOE_CLIENT_IP_KOPFZEILE dessen einwertige Kopfzeile
    in META-Schreibweise (Render hinter Cloudflare: HTTP_CF_CONNECTING_IP). Unbesetzt —
    etwa auf einer Partner-Instanz ohne Proxy — zählt ausschließlich REMOTE_ADDR, denn
    dort könnte ein Client dieselbe Kopfzeile selbst setzen."""
    kopfzeile = getattr(settings, "DDOE_CLIENT_IP_KOPFZEILE", "")
    if kopfzeile:
        wert = request.META.get(kopfzeile, "").strip()
        if wert:
            return wert
    return request.META.get("REMOTE_ADDR", "unbekannt")


def drossel_zuviel(request, zweck: str, limit: int) -> bool:
    """True, wenn diese Verbindung das Stundenlimit für `zweck` erreicht hat.

    Zählt in der Datenbank (`Drosselzaehler`), damit zwei gunicorn-Worker nicht
    zwei Eimer führen und ein Neustart den Stand nicht löscht."""
    from mitglieder.models import Drosselzaehler

    stunde = int(time.time() // 3600)
    kennung = klienten_ip(request)[:64]
    with transaction.atomic():
        zaehler, neu = Drosselzaehler.objects.select_for_update().get_or_create(
            zweck=zweck, kennung=kennung, stunde=stunde
        )
        if zaehler.anzahl >= limit:
            return True
        Drosselzaehler.objects.filter(pk=zaehler.pk).update(anzahl=F("anzahl") + 1)
    if neu:
        # Aufräumen im Vorbeigehen: Zähler sind keine Verfahrensdaten, nach zwei Stunden
        # sagen sie nichts mehr aus.
        Drosselzaehler.objects.filter(stunde__lt=stunde - 1).delete()
    return False


class BotschutzMixin(forms.Form):
    """In Formulare einmischen; im Template unsichtbares Feld + Rechenfrage rendern.
    Braucht `request` (Sitzung), z. B. `LoginFormular(request.POST, request=request)`."""

    # Honigtopf: heißt absichtlich harmlos „website“ — Menschen sehen es nie.
    website = forms.CharField(required=False, widget=forms.HiddenInput, label="")
    pruefung = forms.CharField(widget=forms.HiddenInput)
    rechenfrage = forms.IntegerField(label=gettext_lazy("Sicherheitsfrage"))

    def __init__(self, *args, request, **kwargs):
        super().__init__(*args, **kwargs)
        self.request = request
        aufgabe = aufgabe_lesen(request, self.data.get("pruefung", "")) if self.is_bound else None
        self.fields["rechenfrage"].label = _("Sicherheitsfrage: Ergebnis der Rechnung im Bild")
        self.fields["rechenfrage"].help_text = _(
            "Bitte lösen Sie die kleine Rechnung im Bild. Falls Sie das Bild nicht lesen können, "
            "schreiben Sie uns an didide@ddoe.at — wir helfen sofort."
        )
        if aufgabe:
            # Gleiche Aufgabe erneut anzeigen (z. B. nach einem Tippfehler im Formular).
            self.captcha_svg = aufgabe_als_bild(aufgabe["a"], aufgabe["b"])
        else:
            self.captcha_svg, kennung = aufgabe_erstellen(request)
            self.initial["pruefung"] = kennung
            if self.is_bound:
                # Abgelaufene oder verbrauchte Kennung: Das Formular zeigt eine neue Aufgabe,
                # also muss auch das versteckte Feld die neue Kennung tragen.
                self.data = self.data.copy()
                self.data["pruefung"] = kennung

    def clean(self):
        daten = super().clean()
        fehler = _("Die Sicherheitsfrage wurde nicht richtig beantwortet — bitte erneut versuchen.")
        if daten.get("website"):
            raise forms.ValidationError(fehler)  # Honigtopf gefüllt
        kennung = daten.get("pruefung", "")
        aufgabe = aufgabe_lesen(self.request, kennung)
        if aufgabe is None:
            raise forms.ValidationError(fehler)  # unbekannt, abgelaufen oder schon verbraucht
        if time.time() - aufgabe["t"] < mindestzeit():
            raise forms.ValidationError(fehler)  # schneller als ein Mensch lesen kann
        if daten.get("rechenfrage") != aufgabe["a"] + aufgabe["b"]:
            self.add_error("rechenfrage", fehler)
        elif not self.errors:
            # Erst wenn das ganze Formular trägt, ist die Aufgabe verbraucht — nach einem
            # Tippfehler anderswo bleibt dieselbe Aufgabe stehen (sie wird ja erneut gezeigt).
            aufgabe_verbrauchen(self.request, kennung)
        return daten
