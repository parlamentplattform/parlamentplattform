"""Textvektoren über den Modell-Steckplatz (ADR-011, Stufe 2 der Ähnlichkeit): Attrappe ohne Netz,
Mistral nur auf Anfrage-Bau geprüft, Budget und Archiv wie bei `lauf_ausfuehren`, Fehler archiviert."""

import io
import json

import pytest

from ki.anbieter import (
    ATTRAPPEN_DIMENSION,
    AttrappenAnbieter,
    MistralAnbieter,
    SteckplatzStumm,
    anbieter_waehlen,
    attrappen_vektor,
)
from ki.models import KILauf, Zweck, einbettung_ausfuehren
from plattform_core.similarity import kosinus
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


class _Scheinantwort(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


# --- Attrappe: deterministisch, bedeutungsähnlich ---------------------------------------------


def test_attrappen_vektor_ist_deterministisch_und_normiert():
    a = attrappen_vektor("Radwege in jeder Gemeinde ausbauen")
    assert a == attrappen_vektor("Radwege in jeder Gemeinde ausbauen")
    assert len(a) == ATTRAPPEN_DIMENSION
    assert round(sum(x * x for x in a), 6) == 1.0
    assert attrappen_vektor("die der das") == [0.0] * ATTRAPPEN_DIMENSION  # nur Stoppwörter: leer, keine Ausnahme


def test_attrappe_stellt_bedeutung_nach():
    """Gemeinsame tragende Wörter → hoher Kosinus; fremde Texte → niedrig. Genug, um Stufe 2 zu testen."""
    nah = kosinus(attrappen_vektor("Radwege ausbauen in jeder Gemeinde"), attrappen_vektor("Gemeinde baut Radwege aus"))
    fern = kosinus(attrappen_vektor("Radwege ausbauen in jeder Gemeinde"), attrappen_vektor("Börsennotierung von Pharmaunternehmen"))
    assert nah > 0.5 > fern


def test_attrappe_einbetten_liefert_je_text_einen_vektor():
    e = AttrappenAnbieter().einbetten(["eins zwei", "drei vier"])
    assert len(e.vektoren) == 2 and e.modell == "attrappe-einbettung-1" and e.tokens > 0


# --- Der Weg durch den Steckplatz --------------------------------------------------------------


def test_einbettung_wird_archiviert_und_zaehlt_aufs_budget(settings):
    settings.DDOE_KI_ANBIETER = "attrappe"
    lauf, e = einbettung_ausfuehren(["Radwege ausbauen", "Wasserzähler ablesen"], mitglied_anlegen())
    assert lauf.zweck == Zweck.AEHNLICHKEIT and lauf.erfolgreich and lauf.anbieter == "attrappe"
    assert lauf.modell == "attrappe-einbettung-1" and "2 Vektoren" in lauf.antwort
    assert "Radwege ausbauen" in lauf.eingabe and lauf.tokens_ein == e.tokens
    assert KILauf.monatsverbrauch() == e.tokens


def test_ohne_anbieter_ist_die_einbettung_stumm(settings):
    settings.DDOE_KI_ANBIETER = "mistral"
    settings.DDOE_KI_SCHLUESSEL = ""
    with pytest.raises(SteckplatzStumm, match="Kein KI-Anbieter"):
        einbettung_ausfuehren(["x"], mitglied_anlegen())
    assert KILauf.objects.count() == 0


def test_erschoepftes_budget_stoppt_auch_einbettungen(settings):
    from parameter.models import Parameter

    settings.DDOE_KI_ANBIETER = "attrappe"
    Parameter.objects.create(schluessel="ki-monatstokens", wert="10", beschreibung="x", quelle="Test")
    m = mitglied_anlegen()
    einbettung_ausfuehren(["ein sehr langer Text mit vielen Wörtern darin drin"], m)
    with pytest.raises(SteckplatzStumm, match="Monats-Tokenbudget"):
        einbettung_ausfuehren(["noch einer"], m)


def test_anbieterfehler_wird_als_fehllauf_archiviert(settings, monkeypatch):
    settings.DDOE_KI_ANBIETER = "attrappe"

    def kaputt(self, texte):
        from ki.anbieter import AnbieterFehler

        raise AnbieterFehler("HTTP 500 vom Anbieter")

    monkeypatch.setattr(AttrappenAnbieter, "einbetten", kaputt)
    with pytest.raises(SteckplatzStumm, match="nicht geantwortet"):
        einbettung_ausfuehren(["x y z"], mitglied_anlegen())
    lauf = KILauf.objects.get()
    assert not lauf.erfolgreich and "HTTP 500" in lauf.fehler and lauf.zweck == Zweck.AEHNLICHKEIT


# --- Mistral: Anfrage-Bau und Antwort-Lesen ohne Netz -----------------------------------------


def test_mistral_einbetten_baut_die_anfrage_und_liest_die_vektoren(settings, monkeypatch):
    settings.DDOE_KI_ANBIETER = "mistral"
    settings.DDOE_KI_SCHLUESSEL = "geheim"
    settings.DDOE_KI_EINBETTUNGSMODELL = "mistral-embed-test"
    gesehen = {}

    def schein_urlopen(anfrage, timeout=None):
        gesehen["url"] = anfrage.full_url
        gesehen["rumpf"] = json.loads(anfrage.data.decode())
        antwort = {
            "model": "mistral-embed-test",
            "data": [{"index": 1, "embedding": [0.0, 1.0]}, {"index": 0, "embedding": [1.0, 0.0]}],
            "usage": {"total_tokens": 7},
        }
        return _Scheinantwort(json.dumps(antwort).encode())

    monkeypatch.setattr("urllib.request.urlopen", schein_urlopen)
    anbieter = anbieter_waehlen()
    assert isinstance(anbieter, MistralAnbieter) and anbieter.einbettungsmodell == "mistral-embed-test"
    e = anbieter.einbetten(["a", "b"])
    assert gesehen["url"].endswith("/v1/embeddings")
    assert gesehen["rumpf"] == {"model": "mistral-embed-test", "input": ["a", "b"]}
    assert e.vektoren == [[1.0, 0.0], [0.0, 1.0]]  # nach Index geordnet
    assert e.tokens == 7 and e.modell == "mistral-embed-test"


def test_mistral_einbetten_meldet_kaputte_antworten(monkeypatch):
    from ki.anbieter import AnbieterFehler

    monkeypatch.setattr(
        "urllib.request.urlopen", lambda anfrage, timeout=None: _Scheinantwort(json.dumps({"data": [{"embedding": [1.0]}]}).encode())
    )
    with pytest.raises(AnbieterFehler, match="nicht je Text"):
        MistralAnbieter("geheim", "m").einbetten(["a", "b"])
    monkeypatch.setattr("urllib.request.urlopen", lambda anfrage, timeout=None: _Scheinantwort(b'{"data": "kaputt"}'))
    with pytest.raises(AnbieterFehler, match="Antwortformat"):
        MistralAnbieter("geheim", "m").einbetten(["a"])
    monkeypatch.setattr("urllib.request.urlopen", lambda anfrage, timeout=None: _Scheinantwort(b"[]"))
    with pytest.raises(AnbieterFehler, match="Antwortformat"):
        MistralAnbieter("geheim", "m").frage("A", "E")
