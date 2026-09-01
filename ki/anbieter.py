"""Der Modell-Steckplatz (F-60, Ring 0b): anbieterneutral.

Grundsatz L7/§ 2 Abs 6: **Die KI schlägt vor, sie entscheidet nie.** Jeder
Aufruf läuft über diesen Steckplatz — welcher Anbieter dahinter steckt, ist
eine Einstellung, kein Code-Umbau: heute Mistral (Env `DDOE_KI_SCHLUESSEL`),
morgen eine lokal betriebene KI oder ein anderer Dienst mit derselben
Chat-Schnittstelle. Ohne Schlüssel ist der Steckplatz ehrlich leer — die
Oberflächen sagen das, nichts bricht.

Bewusst nur die Standardbibliothek (urllib): kein neues Paket, keine
Anbieter-SDKs — die Schnittstelle bleibt schmal und prüfbar."""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass

MISTRAL_ENDPUNKT = "https://api.mistral.ai/v1/chat/completions"
ZEITGRENZE_SEKUNDEN = 45
ANTWORT_HOECHSTTOKENS = 900


@dataclass(frozen=True)
class Antwort:
    text: str
    modell: str
    tokens_ein: int
    tokens_aus: int


class AnbieterFehler(RuntimeError):
    """Der Anbieter hat nicht (brauchbar) geantwortet — Netz, Schlüssel, Format."""


class SteckplatzStumm(RuntimeError):
    """Der Steckplatz kann gerade nicht antworten; args[0] nennt den Grund
    (kein Anbieter angeschlossen, Monatsbudget erschöpft, Anbieterfehler)."""


class MistralAnbieter:
    """Chat-Completions-Aufruf gegen Mistral — nüchtern, ohne SDK."""

    name = "mistral"

    def __init__(self, schluessel: str, modell: str):
        self.schluessel = schluessel
        self.modell = modell

    def frage(self, auftrag: str, eingabe: str) -> Antwort:
        rumpf = json.dumps(
            {
                "model": self.modell,
                "temperature": 0.2,
                "max_tokens": ANTWORT_HOECHSTTOKENS,
                "messages": [
                    {"role": "system", "content": auftrag},
                    {"role": "user", "content": eingabe},
                ],
            }
        ).encode()
        anfrage = urllib.request.Request(
            MISTRAL_ENDPUNKT,
            data=rumpf,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.schluessel}",
                "User-Agent": "parlamentplattform-steckplatz",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(anfrage, timeout=ZEITGRENZE_SEKUNDEN) as antwort:
                daten = json.loads(antwort.read().decode())
        except urllib.error.HTTPError as fehler:
            raise AnbieterFehler(f"HTTP {fehler.code} vom Anbieter") from fehler
        except (urllib.error.URLError, TimeoutError, ValueError) as fehler:
            raise AnbieterFehler(f"Anbieter nicht erreichbar: {fehler}") from fehler
        try:
            text = daten["choices"][0]["message"]["content"].strip()
            verbrauch = daten.get("usage", {})
        except (KeyError, IndexError, AttributeError) as fehler:
            raise AnbieterFehler("Antwortformat unerwartet") from fehler
        return Antwort(
            text=text,
            modell=daten.get("model", self.modell),
            tokens_ein=int(verbrauch.get("prompt_tokens", 0)),
            tokens_aus=int(verbrauch.get("completion_tokens", 0)),
        )


class AttrappenAnbieter:
    """Für Tests und Vorführungen ohne Netz: antwortet vorhersehbar."""

    name = "attrappe"
    modell = "attrappe-1"

    def frage(self, auftrag: str, eingabe: str) -> Antwort:
        return Antwort(
            text="Attrappen-Einschätzung (kein echtes Modell): Der Text wurde entgegengenommen — "
            f"{len(eingabe)} Zeichen. Ein echter Anbieter würde hier zusammenfassen und Unklarheiten nennen.",
            modell=self.modell,
            tokens_ein=max(1, len(auftrag + eingabe) // 4),
            tokens_aus=40,
        )


def anbieter_waehlen():
    """Der Steckplatz: liefert den eingestellten Anbieter — oder None, wenn
    keiner angeschlossen ist (kein Schlüssel). Einstellung, kein Code."""
    from django.conf import settings

    art = getattr(settings, "DDOE_KI_ANBIETER", "mistral")
    if art == "attrappe":
        return AttrappenAnbieter()
    schluessel = getattr(settings, "DDOE_KI_SCHLUESSEL", "")
    if art == "mistral" and schluessel:
        return MistralAnbieter(schluessel, getattr(settings, "DDOE_KI_MODELL", "mistral-small-latest"))
    return None
