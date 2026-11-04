"""CSP im tatsächlichen Antwortweg, ohne Änderungen an Datenantworten."""

import pytest
from django.http import HttpResponse
from django.urls import reverse

from config.sicherheitsheader import RICHTLINIE, BrowserQuellenBegrenzen


@pytest.mark.parametrize("typ", ["text/html", "Text/HTML; charset=utf-8", "application/xhtml+xml"])
def test_html_erhaelt_die_richtlinie_ohne_inhaltsaenderung(typ):
    inhalt = b"<p>Unveraenderter Inhalt</p>"
    antwort = HttpResponse(inhalt, content_type=typ, status=404)
    ergebnis = BrowserQuellenBegrenzen(lambda request: antwort)(None)
    assert ergebnis.status_code == 404 and ergebnis.content == inhalt
    assert ergebnis["Content-Security-Policy"] == RICHTLINIE


@pytest.mark.parametrize("typ,inhalt", [
    ("application/pdf", b"%PDF-1.7"), ("application/json", b'{"stand":1}'),
    ("image/svg+xml", b"<svg/>"), ("image/png", b"\x89PNG"), ("text/plain", b"Text"),
])
def test_datenantworten_bleiben_unveraendert(typ, inhalt):
    antwort = HttpResponse(inhalt, content_type=typ)
    ergebnis = BrowserQuellenBegrenzen(lambda request: antwort)(None)
    assert ergebnis.content == inhalt and ergebnis["Content-Type"] == typ
    assert "Content-Security-Policy" not in ergebnis


def test_vorhandene_strengere_richtlinie_bleibt_erhalten():
    antwort = HttpResponse("<p>Inhalt</p>", headers={"Content-Security-Policy": "default-src 'none'"})
    ergebnis = BrowserQuellenBegrenzen(lambda request: antwort)(None)
    assert ergebnis["Content-Security-Policy"] == "default-src 'none'"


@pytest.mark.django_db
@pytest.mark.parametrize("ziel", ["verfahren:index", "verfahren:rollen", "parameter:regeln", "mitglieder:login"])
def test_tatsaechliche_html_seiten_sind_begrenzt(client, ziel):
    antwort = client.get(reverse(ziel))
    assert antwort.status_code == 200
    assert antwort["Content-Security-Policy"] == RICHTLINIE


@pytest.mark.django_db
def test_ersetzte_htmx_anmeldeumleitung_erhaelt_den_header(client):
    antwort = client.post(reverse("verfahren:einbringen"), HTTP_HX_REQUEST="true")
    assert antwort.status_code == 200 and antwort["HX-Redirect"].startswith(reverse("mitglieder:login"))
    assert antwort["Content-Security-Policy"] == RICHTLINIE


@pytest.mark.django_db
def test_echte_fehlerseite_und_json_download(client, settings):
    settings.DEBUG = False
    fehler = client.get("/diese-seite-gibt-es-nicht/")
    assert fehler.status_code == 404 and fehler["Content-Security-Policy"] == RICHTLINIE
    daten = client.get(reverse("parameter:export"))
    assert daten.status_code == 200 and daten.json()["schema_version"]
    assert "Content-Security-Policy" not in daten
