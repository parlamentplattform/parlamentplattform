"""Ring 0b — der Modell-Steckplatz (F-60): anbieterneutral, budgetiert,
archiviert, gekennzeichnet. Alle Tests laufen ohne Netz (Attrappe bzw.
gepatchtes urllib); der Mistral-Anbieter wird auf Anfrage-Bau geprüft."""

import io
import json

import pytest
from django.urls import reverse

from gremien.test_werkstatt import (  # noqa: F401
    ANTRAG,
    fenster_oeffnen,
    mitglied_anlegen,
    ordnung,
    rolle_geben,
    werkstatt_lage,
)
from ki.anbieter import AnbieterFehler, MistralAnbieter, SteckplatzStumm, anbieter_waehlen
from ki.models import KILauf, Zweck, lauf_ausfuehren

pytestmark = pytest.mark.django_db


# --- Der Steckplatz selbst ----------------------------------------------------


def test_ohne_schluessel_ist_der_steckplatz_ehrlich_leer(settings):
    settings.DDOE_KI_ANBIETER = "mistral"
    settings.DDOE_KI_SCHLUESSEL = ""
    assert anbieter_waehlen() is None
    with pytest.raises(SteckplatzStumm, match="Kein KI-Anbieter angeschlossen"):
        lauf_ausfuehren(Zweck.EINSCHAETZUNG, "Auftrag", "Eingabe", mitglied_anlegen())
    assert KILauf.objects.count() == 0


def test_attrappe_laeuft_und_wird_archiviert(settings):
    settings.DDOE_KI_ANBIETER = "attrappe"
    lauf = lauf_ausfuehren(Zweck.EINSCHAETZUNG, "Auftrag", "Ein Antragstext.", mitglied_anlegen())
    assert lauf.erfolgreich and lauf.anbieter == "attrappe"
    assert "Attrappen-Einschätzung" in lauf.antwort
    assert lauf.tokens_ein > 0 and lauf.tokens_aus > 0
    assert KILauf.monatsverbrauch() == lauf.tokens_ein + lauf.tokens_aus


def test_erschoepftes_budget_macht_den_steckplatz_stumm(settings):
    settings.DDOE_KI_ANBIETER = "attrappe"
    settings.DDOE_KI_MONATSTOKENS = 10
    anna = mitglied_anlegen()
    lauf_ausfuehren(Zweck.EINSCHAETZUNG, "A", "Langer Text weit über zehn Tokens hinaus.", anna)
    with pytest.raises(SteckplatzStumm, match="Monats-Tokenbudget"):
        lauf_ausfuehren(Zweck.EINSCHAETZUNG, "A", "Noch einmal.", anna)
    assert KILauf.objects.count() == 1  # der abgewiesene Versuch ruft keinen Anbieter


def test_anbieterfehler_wird_archiviert(settings, monkeypatch):
    settings.DDOE_KI_ANBIETER = "attrappe"
    from ki import anbieter as modul

    def kaputt(self, auftrag, eingabe):
        raise AnbieterFehler("HTTP 500 vom Anbieter")

    monkeypatch.setattr(modul.AttrappenAnbieter, "frage", kaputt)
    with pytest.raises(SteckplatzStumm, match="nicht geantwortet"):
        lauf_ausfuehren(Zweck.EINSCHAETZUNG, "A", "Text.", mitglied_anlegen())
    lauf = KILauf.objects.get()
    assert not lauf.erfolgreich and "HTTP 500" in lauf.fehler and lauf.antwort == ""


def test_mistral_anbieter_baut_die_anfrage_korrekt(monkeypatch):
    """Ohne Netz: urlopen wird abgefangen, Anfrage und Antwort-Parsing geprüft."""
    gesehen = {}

    class Scheinantwort(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    def schein_urlopen(anfrage, timeout=None):
        gesehen["url"] = anfrage.full_url
        gesehen["auth"] = anfrage.get_header("Authorization")
        gesehen["rumpf"] = json.loads(anfrage.data.decode())
        return Scheinantwort(
            json.dumps(
                {
                    "model": "mistral-small-latest",
                    "choices": [{"message": {"content": " Die Einschätzung. "}}],
                    "usage": {"prompt_tokens": 120, "completion_tokens": 45},
                }
            ).encode()
        )

    monkeypatch.setattr("urllib.request.urlopen", schein_urlopen)
    antwort = MistralAnbieter("geheim", "mistral-small-latest").frage("Auftrag.", "Eingabe.")
    assert gesehen["url"].startswith("https://api.mistral.ai/")
    assert gesehen["auth"] == "Bearer geheim"
    assert gesehen["rumpf"]["messages"][0] == {"role": "system", "content": "Auftrag."}
    assert gesehen["rumpf"]["max_tokens"] <= 900
    assert antwort.text == "Die Einschätzung." and antwort.tokens_ein == 120 and antwort.tokens_aus == 45


# --- Die erste Nutzung: Einschätzung in der Gremien-Werkstatt -----------------


def test_werkstatt_einschaetzung_als_gekennzeichneter_beitrag(client, settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    antrag, _, er = werkstatt_lage(ordnung)
    fenster_oeffnen(client, antrag, er[0])
    client.post(reverse("gremien:fenster_aktion", args=[antrag.pk]), {"aktion": "ki_einschaetzung"})
    entwurf = antrag.entwurf
    beitrag = entwurf.beitraege.get()
    assert beitrag.ki_lauf is not None and "Attrappen-Einschätzung" in beitrag.text
    lauf = beitrag.ki_lauf
    assert lauf.zweck == Zweck.EINSCHAETZUNG and lauf.antrag_id == antrag.pk
    assert ANTRAG["wortlaut"] in lauf.eingabe  # die Fassung ging in die Eingabe
    inhalt = client.get(reverse("gremien:fenster", args=[antrag.pk])).content.decode()
    assert "KI-Vorschlag" in inhalt and "attrappe-1" in inhalt  # Kennzeichnung sichtbar


def test_werkstatt_sagt_ehrlich_wenn_der_steckplatz_leer_ist(client, settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "mistral"
    settings.DDOE_KI_SCHLUESSEL = ""
    antrag, _, er = werkstatt_lage(ordnung)
    fenster_oeffnen(client, antrag, er[0])
    inhalt = client.get(reverse("gremien:fenster", args=[antrag.pk])).content.decode()
    assert "kein Anbieter angeschlossen" in inhalt
    client.post(reverse("gremien:fenster_aktion", args=[antrag.pk]), {"aktion": "ki_einschaetzung"})
    assert antrag.entwurf.beitraege.count() == 0 and KILauf.objects.count() == 0


# --- Öffentliche Rechenschaft -------------------------------------------------


def test_zukunftswerkstatt_zeigt_steckplatz_zahlen(client, settings):
    settings.DDOE_KI_ANBIETER = "attrappe"
    inhalt = client.get(reverse("verfahren:zukunftswerkstatt")).content.decode()
    assert "Rechenschaft in Zahlen" in inhalt and "attrappe-1" in inhalt
    lauf_ausfuehren(Zweck.EINSCHAETZUNG, "A", "Text.", mitglied_anlegen())
    inhalt = client.get(reverse("verfahren:zukunftswerkstatt")).content.decode()
    assert "Archivierte Läufe: 1" in inhalt and "Zuletzt archivierte Läufe" in inhalt


def test_zukunftswerkstatt_ohne_anbieter_bleibt_ehrlich(client, settings):
    settings.DDOE_KI_ANBIETER = "mistral"
    settings.DDOE_KI_SCHLUESSEL = ""
    inhalt = client.get(reverse("verfahren:zukunftswerkstatt")).content.decode()
    assert "kein Anbieter angeschlossen" in inhalt
