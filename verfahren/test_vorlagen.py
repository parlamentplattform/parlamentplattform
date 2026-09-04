"""Wächter über die Vorlagen: Was der Nutzer sieht, muss für ihn bestimmt sein.

Anlass (4.9.2026): In `_gespraeche_panel.html` stand ein **mehrzeiliger** `{# … #}`-Kommentar.
Django wertet diese Kurzform nur einzeilig aus — mehrzeilig landet der Kommentartext sichtbar
im HTML. Weil das Panel über den Kontextprozessor auf jeder Seite liegt, stand der Text auf
**jeder** Seite der Plattform, und keiner der 703 Tests schlug an: Sie prüfen, ob etwas da ist,
nie, ob etwas zu viel da ist.

Diese Datei prüft beides — die Quelle (mehrzeilige Kurzkommentare) und das Ergebnis
(Template-Syntax im ausgelieferten HTML).
"""

from __future__ import annotations

import pathlib
import re

import pytest
from django.urls import reverse

from verfahren.models import antrag_einbringen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    mitglied_anlegen,
    ordnung,
)

WURZEL = pathlib.Path(__file__).resolve().parent.parent

#: Was nach dem Rendern nie mehr im Text stehen darf — Reste unausgewerteter Vorlagensprache.
RESTE = ("{#", "#}", "{%", "%}", "endcomment", "endblocktranslate", "{{", "}}")


def vorlagen() -> list[pathlib.Path]:
    return [
        d
        for d in WURZEL.rglob("*.html")
        if "node_modules" not in d.parts and ".venv" not in d.parts and "venv" not in d.parts
    ]


def test_keine_mehrzeiligen_kurzkommentare():
    """`{# … #}` gilt nur einzeilig — mehrzeilig wird der Kommentar zum Seiteninhalt.

    Für längere Anmerkungen gehört `{% comment %} … {% endcomment %}` verwendet."""
    fehler = []
    for d in vorlagen():
        text = d.read_text(encoding="utf-8")
        for treffer in re.finditer(r"\{#", text):
            rest = text[treffer.start():]
            zeilenende, schluss = rest.find("\n"), rest.find("#}")
            if schluss == -1 or (zeilenende != -1 and schluss > zeilenende):
                fehler.append(f"{d.relative_to(WURZEL)}:{text[:treffer.start()].count(chr(10)) + 1}")
    assert not fehler, (
        "Mehrzeilige {# … #}-Kommentare landen als Text auf der Seite — "
        f"stattdessen {{% comment %}} verwenden: {fehler}"
    )


def test_jede_vorlage_schliesst_ihre_kommentarbloecke():
    fehler = [
        str(d.relative_to(WURZEL))
        for d in vorlagen()
        if (t := d.read_text(encoding="utf-8")).count("{% comment %}") != t.count("{% endcomment %}")
    ]
    assert not fehler, f"{{% comment %}} ohne {{% endcomment %}}: {fehler}"


def _ohne_skripte(html: str) -> str:
    """Der sichtbare Teil — in <script> und <style> darf geschweiftes Zeug stehen."""
    ohne = re.sub(r"<script\b.*?</script>", "", html, flags=re.S | re.I)
    return re.sub(r"<style\b.*?</style>", "", ohne, flags=re.S | re.I)


def _pruefe(html: str, wo: str) -> None:
    sichtbar = _ohne_skripte(html)
    gefunden = [rest for rest in RESTE if rest in sichtbar]
    assert not gefunden, f"{wo}: unausgewertete Vorlagensprache im HTML — {gefunden}"


@pytest.mark.django_db
def test_seiten_liefern_kein_vorlagen_rohmaterial_aus(client, ordnung):  # noqa: F811
    """Was der Server ausliefert, enthält keine Reste der Vorlagensprache — auf keiner Seite.

    Das Gesprächs-Panel liegt auf jeder Seite; ein Fehler darin trifft alle. Deshalb wird
    angemeldet **und** als Gast geprüft."""
    mitglied = mitglied_anlegen("leserin")
    antrag = antrag_einbringen(mitglied, **ANTRAG, ordnung=ordnung)
    antrag.kommentare.create(mitglied=mitglied, text="Ein Beitrag, damit der Chat etwas zeigt.")

    ziele = [
        ("/", "Startseite"),
        (reverse("verfahren:parlament"), "Parlament"),
        (reverse("verfahren:antrag", args=[antrag.pk]), "Antragsseite"),
        (reverse("verfahren:archiv_export", args=[antrag.pk, "md"]), "Archiv-Export"),
        (reverse("parameter:liste"), "Parameterregister"),
    ]
    for pfad, name in ziele:
        _pruefe(client.get(pfad).content.decode(), f"Gast · {name}")

    client.force_login(mitglied)
    for pfad, name in [*ziele, (reverse("verfahren:gespraeche"), "Meine Gespräche")]:
        _pruefe(client.get(pfad).content.decode(), f"Mitglied · {name}")
