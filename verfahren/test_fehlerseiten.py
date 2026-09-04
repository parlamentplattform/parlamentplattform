"""Die Fehlerseiten (404, 403, 500): kein Nutzer landet in einer Sackgasse.

Ohne eigene Vorlagen liefert Django mit DEBUG=False eine nackte englische Minimalseite —
ohne App-Leiste, ohne Gestaltung, ohne Weg zurück, mitten in einer sonst durchgehend
deutschen Anwendung. Diese Tests halten fest, dass es die Vorlagen gibt, dass sie deutsch
sind und dass jede einen Weg zurück anbietet.
"""

from __future__ import annotations

import pytest
from django.template.loader import get_template
from django.test import Client
from django.urls import reverse

pytestmark = pytest.mark.django_db

#: Jede Fehlerseite nennt ihre Nummer und führt irgendwohin zurück.
SEITEN = (("404.html", "404", "/parlament/"), ("403.html", "403", "/parlament/"), ("500.html", "500", "/parlament/"))


@pytest.mark.parametrize(("vorlage", "nummer", "weg"), SEITEN)
def test_fehlerseite_ist_deutsch_und_zeigt_einen_weg_zurueck(vorlage, nummer, weg):
    html = get_template(vorlage).render({})
    assert nummer in html, "die Nummer steht auf der Seite"
    assert weg in html, f"{vorlage} führt zurück ins Parlament"
    assert "Not Found" not in html and "Server Error" not in html, "kein englischer Django-Text"
    from verfahren.test_vorlagen import _ohne_skripte  # dieselbe Bereinigung wie dort

    sichtbar = _ohne_skripte(html)  # in CSS steht „width:100%}" — das ist kein Vorlagenrest
    for rest in ("{%", "{#", "%}", "#}"):
        assert rest not in sichtbar, f"{vorlage}: unausgewertete Vorlagensprache"


def test_die_fuenfhunderter_seite_traegt_sich_selbst():
    """Sie darf nicht von base.html abhängen: Wenn die Anwendung fällt, muss sie trotzdem stehen.

    Django rendert 500.html ohne Kontextprozessoren; eine Seite, die dabei erneut scheitert,
    hinterlässt den Nutzer mit gar nichts."""
    quelle = (get_template("500.html").origin.name)
    with open(quelle, encoding="utf-8") as f:
        text = f.read()
    assert "{% extends" not in text, "500.html erbt bewusst nicht"
    assert "<style>" in text, "sie bringt ihre Gestaltung selbst mit"
    assert "<script" not in text, "kein Skript auf der Fehlerseite"
    # Sie rendert auch mit völlig leerem Kontext (so ruft Django sie auf)
    assert "500" in get_template("500.html").render({})


def test_unbekannte_adresse_liefert_die_eigene_seite(client):
    """Mit DEBUG=False zieht Django 404.html von selbst — der Statuscode allein genügt nicht."""
    antwort = Client(raise_request_exception=False).get("/gibt-es-nicht/")
    assert antwort.status_code == 404
    inhalt = antwort.content.decode()
    # In Tests läuft DEBUG=False; die eigene Vorlage muss greifen
    assert "Diese Seite gibt es nicht" in inhalt, "die eigene 404-Seite wird ausgeliefert"
    assert reverse("verfahren:parlament") in inhalt, "mit einem Weg zurück"
