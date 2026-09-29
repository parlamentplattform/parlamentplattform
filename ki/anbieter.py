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

import http.client
import json
import urllib.error
import urllib.request
from dataclasses import dataclass

MISTRAL_ENDPUNKT = "https://api.mistral.ai/v1/chat/completions"
MISTRAL_EINBETTUNG_ENDPUNKT = "https://api.mistral.ai/v1/embeddings"
EINBETTUNGSMODELL_STANDARD = "mistral-embed"
ZEITGRENZE_SEKUNDEN = 45
#: Dimension der Attrappen-Vektoren — klein genug für Tests, groß genug, dass Wörter selten kollidieren.
ATTRAPPEN_DIMENSION = 64
#: Rückfallwert; die geltende Obergrenze steht im Register unter „ki-antwort-hoechsttokens“.
ANTWORT_HOECHSTTOKENS = 900


def antwort_hoechsttokens() -> int:
    """Die Stellgröße „ki-antwort-hoechsttokens“ aus dem Parameterregister (§ 2 Abs 6) —
    mit ehrlichem Rückfall auf den eingebauten Zielwert, wenn das Register nicht bereit ist.
    Die Registerseite verspricht „Der Code liest von hier“; bis zur Gesamtprüfung 0.45 stand der
    Wert nur im Register und wirkte nicht (Befund #45)."""
    from parameter.models import zahl

    return max(1, zahl("ki-antwort-hoechsttokens", ANTWORT_HOECHSTTOKENS))


@dataclass(frozen=True)
class Antwort:
    text: str
    modell: str
    tokens_ein: int
    tokens_aus: int


@dataclass(frozen=True)
class Einbettung:
    """Textvektoren des Anbieters (Stufe 2 der Ähnlichkeit): ein Vektor je Eingabetext, in derselben
    Reihenfolge; `modell` kennzeichnet, mit welchem Modell sie vergleichbar sind."""

    vektoren: list[list[float]]
    modell: str
    tokens: int


class AnbieterFehler(RuntimeError):
    """Der Anbieter hat nicht (brauchbar) geantwortet — Netz, Schlüssel, Format."""


class SteckplatzStumm(RuntimeError):
    """Der Steckplatz kann gerade nicht antworten; args[0] nennt den Grund
    (kein Anbieter angeschlossen, Monatsbudget erschöpft, Anbieterfehler)."""


class MistralAnbieter:
    """Chat-Completions-Aufruf gegen Mistral — nüchtern, ohne SDK."""

    name = "mistral"

    def __init__(self, schluessel: str, modell: str, einbettungsmodell: str = EINBETTUNGSMODELL_STANDARD):
        self.schluessel = schluessel
        self.modell = modell
        self.einbettungsmodell = einbettungsmodell

    def frage(self, auftrag: str, eingabe: str) -> Antwort:
        daten = self._senden(
            MISTRAL_ENDPUNKT,
            {
                "model": self.modell,
                "temperature": 0.2,
                "max_tokens": antwort_hoechsttokens(),
                "messages": [
                    {"role": "system", "content": auftrag},
                    {"role": "user", "content": eingabe},
                ],
            },
        )
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

    def einbetten(self, texte: list[str]) -> Einbettung:
        """Ein Aufruf für alle Texte — die Antwort trägt je Text einen Vektor mit seinem Index."""
        daten = self._senden(MISTRAL_EINBETTUNG_ENDPUNKT, {"model": self.einbettungsmodell, "input": texte})
        try:
            zeilen = sorted(daten["data"], key=lambda z: int(z.get("index", 0)))
            vektoren = [[float(x) for x in z["embedding"]] for z in zeilen]
            tokens = int(daten.get("usage", {}).get("total_tokens", 0))
        except (KeyError, TypeError, ValueError, AttributeError) as fehler:
            raise AnbieterFehler("Antwortformat unerwartet") from fehler
        if len(vektoren) != len(texte):
            raise AnbieterFehler("Anbieter lieferte nicht je Text einen Vektor")
        return Einbettung(vektoren=vektoren, modell=daten.get("model", self.einbettungsmodell), tokens=tokens)

    def _senden(self, endpunkt: str, rumpf: dict) -> dict:
        anfrage = urllib.request.Request(
            endpunkt,
            data=json.dumps(rumpf).encode(),
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
        except (urllib.error.URLError, OSError, http.client.HTTPException, ValueError) as fehler:
            # OSError deckt Verbindungsabbrüche beim Lesen (ConnectionResetError), HTTPException
            # abgebrochene Antworten (IncompleteRead, RemoteDisconnected): Jeder Netz- und
            # Protokollfehler wird ein AnbieterFehler und landet damit im Archiv (Befund #99) —
            # vorher endete ein Abbruch mitten in der Antwort als 500-Seite ohne Archiveintrag.
            raise AnbieterFehler(f"Anbieter nicht erreichbar: {fehler}") from fehler
        if not isinstance(daten, dict):
            raise AnbieterFehler("Antwortformat unerwartet")
        return daten


class AttrappenAnbieter:
    """Für Tests und Vorführungen ohne Netz: antwortet vorhersehbar."""

    name = "attrappe"
    modell = "attrappe-1"
    einbettungsmodell = "attrappe-einbettung-1"

    def frage(self, auftrag: str, eingabe: str) -> Antwort:
        return Antwort(
            text="Attrappen-Einschätzung (kein echtes Modell): Der Text wurde entgegengenommen — "
            f"{len(eingabe)} Zeichen. Ein echter Anbieter würde hier zusammenfassen und Unklarheiten nennen.",
            modell=self.modell,
            tokens_ein=max(1, len(auftrag + eingabe) // 4),
            tokens_aus=40,
        )

    def einbetten(self, texte: list[str]) -> Einbettung:
        """Deterministische Vektoren aus Wort-Hashes: Texte mit gemeinsamen Wörtern liegen nah beieinander,
        fremde weit auseinander — genug, damit Tests die Bedeutungsstufe ohne Netz nachstellen können."""
        return Einbettung(
            vektoren=[attrappen_vektor(t) for t in texte],
            modell=self.einbettungsmodell,
            tokens=max(1, sum(len(t) for t in texte) // 4),
        )


def attrappen_vektor(text: str, dimension: int = ATTRAPPEN_DIMENSION) -> list[float]:
    """Jedes tragende Wort (Stammform, ohne Stoppwörter) zeigt auf eine Achse; das Vorzeichen kommt aus
    dem Hash. Der Vektor ist normiert — leer, wenn der Text keine tragenden Wörter hat."""
    import hashlib

    from plattform_core.similarity import woerter

    vektor = [0.0] * dimension
    for wort in woerter(text):
        h = hashlib.sha256(wort.encode()).digest()
        achse = int.from_bytes(h[:4], "big") % dimension
        vektor[achse] += 1.0 if h[4] % 2 == 0 else -1.0
    norm = sum(x * x for x in vektor) ** 0.5
    return [x / norm for x in vektor] if norm else vektor


def anbieter_waehlen():
    """Der Steckplatz: liefert den eingestellten Anbieter — oder None, wenn
    keiner angeschlossen ist (kein Schlüssel). Einstellung, kein Code."""
    from django.conf import settings

    art = getattr(settings, "DDOE_KI_ANBIETER", "mistral")
    if art == "attrappe":
        return AttrappenAnbieter()
    schluessel = getattr(settings, "DDOE_KI_SCHLUESSEL", "")
    if art == "mistral" and schluessel:
        return MistralAnbieter(
            schluessel,
            getattr(settings, "DDOE_KI_MODELL", "mistral-small-latest"),
            getattr(settings, "DDOE_KI_EINBETTUNGSMODELL", EINBETTUNGSMODELL_STANDARD),
        )
    return None
