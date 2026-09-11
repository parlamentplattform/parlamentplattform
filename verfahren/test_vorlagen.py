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


@pytest.mark.django_db
def test_keine_doppelten_kennungen_im_dokument(client, ordnung):  # noqa: F811
    """Jede id kommt einmal vor — sonst greifen htmx-Ziele daneben.

    Anlass: Das Gesprächs-Panel liegt auf jeder Seite und brachte `#gespraeche-liste` mit;
    auf /gespraeche/ trug die Seitenliste dieselbe id. htmx nimmt beim Auflösen von `hx-target`
    den **ersten** Treffer im Dokument — also tauschte das Panel die Liste der Seite aus und
    blieb selbst auf „Wird geladen …" stehen."""
    mitglied = mitglied_anlegen("doppelt")
    antrag = antrag_einbringen(mitglied, **ANTRAG, ordnung=ordnung)
    client.force_login(mitglied)
    for pfad, name in (
        (reverse("verfahren:gespraeche"), "Meine Gespräche"),
        (reverse("verfahren:parlament"), "Parlament"),
        (reverse("verfahren:antrag", args=[antrag.pk]), "Antragsseite"),
    ):
        html = client.get(pfad).content.decode()
        kennungen = re.findall(r'\sid="([^"]+)"', html)
        doppelt = sorted({k for k in kennungen if kennungen.count(k) > 1})
        assert not doppelt, f"{name}: id mehrfach vergeben — {doppelt}"


# ── Sprachregeln des Gründers (CLAUDE.md, Fahrtenbuch „Namen") ───────────────────────────

#: Wörter, die in keinem Nutzer-Text vorkommen dürfen, mit ihrer Ersatzform.
VERBOTEN = {
    "Prototyp": "Alpha-Phase",
    "Regierungsform": "die logisch nächste Form der gesamtgesellschaftlichen Selbstorganisation",
    "Vorlage": "Vorschlag",
    "Minderheiten": "Betroffene und Fachkundige",
}

#: Begründete Ausnahmen — hier meint das Wort etwas anderes als die Sprachregel.
AUSNAHMEN = {
    # „Docker- und Render-Vorlage" ist eine Einrichtungsdatei, kein Vorschlag des Expertenrats.
    "Docker- und Render-Vorlage",
    # ebenso die „Instanz-Vorlagen" des Übertragungspakets (docs/partner/instanz/).
    "Instanz-Vorlagen",
}


def msgids() -> list[str]:
    """Alle deutschen Ausgangstexte des Katalogs — per Definition Nutzer-Texte.

    Gelesen mit demselben strengen Leser wie `tools/po_pruefen.py` (Befund #59): Die frühere
    zeilenweise Lesung brach bei einem rohen Zeilenumbruch ab, und ein verbotenes Wort ab der
    zweiten Zeile eines solchen Blocks blieb dem Wächter verborgen."""
    import sys

    sys.path.insert(0, str(WURZEL / "tools"))
    from po_pruefen import lesen

    ids = []
    for e in lesen():
        ids.append(e.msgid or "")
        ids.append(e.msgid_plural or "")
    return [i.replace("\n", " ") for i in ids if i]


def datentexte() -> list[tuple[str, str]]:
    """Nutzer-Texte, die nicht im Katalog stehen, weil sie als Daten in `plattform_core` und im
    Erstbestand des Registers liegen: Rollenmatrix, Regelverzeichnis, Parameterbeschreibungen.
    Der Sprachregel-Wächter prüfte bisher nur den Katalog — „ueber andere Fragen" auf /rollen/
    blieb deshalb unbemerkt (Befund #89)."""
    from parameter.models import ERSTBESTAND
    from plattform_core.regelwerk import verzeichnis
    from plattform_core.rollen import GRUPPEN, alle_rollen

    texte: list[tuple[str, str]] = []
    for r in alle_rollen(GRUPPEN):
        texte += [(f"rollen.py · {r.schluessel}", t) for t in (r.name, r.was_sie_ist, r.wie_hinein, r.hinweis)]
        for f in r.faehigkeiten:
            texte += [
                (f"rollen.py · {r.schluessel}", t) for t in (f.titel, f.ort, f.einschraenkung, f.bauschritt)
            ]
    for g in GRUPPEN:
        texte += [(f"rollen.py · Gruppe {g.schluessel}", t) for t in (g.name, g.erklaerung)]
    for regel in verzeichnis():
        texte += [
            (f"regelwerk.py · {regel.modul}", t)
            for t in (regel.titel, regel.zweck, regel.grund, regel.nachrechenbar, regel.luecke)
        ]
    for e in ERSTBESTAND:
        texte += [(f"ERSTBESTAND · {e['schluessel']}", e.get(k, "")) for k in ("beschreibung", "quelle", "einheit")]
    return [(wo, t) for wo, t in texte if t]


#: Ersatzschreibungen (ue/ae/oe statt ü/ä/ö) als Wortliste — ein Silbenmuster träfe „neue",
#: „aktuell" oder „Duell". Erweiterbar; jedes Wort steht für eine Fundstelle, die es gab.
ERSATZSCHREIBUNGEN = re.compile(
    r"\b(fuer|ueber\w*|koenn\w*|muess\w*|waehl\w*|oeffentlich\w*|aenderung\w*|uebersicht\w*|"
    r"praesident\w*|zurueck\w*|gruende\w*|beraet|prueft|pruef\w*|unterstuetz\w*|moeglich\w*|"
    r"wuensch\w*|zustaendig\w*|hoechst\w*|groesse\w*|laeuft|traegt|waehrend|spaeter|naechst\w*|"
    r"erklaer\w*|zaehl\w*|loesch\w*|buerger\w*|fuehr\w*|betraegt|antraege|vorschlaege|"
    r"beschluesse|entwuerfe|raete|integritaet\w*|verfuegbar\w*)\b",
    re.I,
)


def test_keine_ersatzschreibungen_in_nutzer_texten():
    """CLAUDE.md: keine Ersatzschreibungen (ue/ae/oe) in Nutzer-Texten — weder im Katalog noch in
    den Datentabellen, aus denen /rollen/, /regeln/ und /parameter/ entstehen."""
    fehler = []
    for text in msgids():
        if (m := ERSATZSCHREIBUNGEN.search(text)):
            fehler.append(f"Katalog: „{m.group(0)}“ in {text[:70]!r}")
    for wo, text in datentexte():
        if (m := ERSATZSCHREIBUNGEN.search(text)):
            fehler.append(f"{wo}: „{m.group(0)}“ in {text[:70]!r}")
    assert not fehler, "Ersatzschreibung im Nutzer-Text:\n  " + "\n  ".join(fehler)


def test_nutzer_texte_halten_die_sprachregeln():
    """Die Namen sind entschieden (CLAUDE.md): Alpha-Phase statt Prototyp, Vorschlag statt
    Vorlage, keine „Regierungsform", „Betroffene und Fachkundige" statt „Minderheiten".

    Geprüft wird der Katalog — dort stehen genau die Texte, die Nutzer zu lesen bekommen.
    Kommentare und Bezeichner im Code sind nicht gemeint."""
    fehler = []
    for text in msgids() + [t for _, t in datentexte()]:
        if any(a in text for a in AUSNAHMEN):
            continue
        for wort, ersatz in VERBOTEN.items():
            if wort in text:
                fehler.append(f'{wort} statt {ersatz}: {text[:90]}')
    assert not fehler, "Sprachregel verletzt:\n  " + "\n  ".join(fehler)


#: Kürzel interner Dokumente — im Quelltext hilfreich, in Nutzer-Texten Rauschen.
KENNUNGSMUSTER = re.compile(r"\b(F-\d+|FB-[A-Z]\d+|A0-\d+|ADR-\d+|Ring 0[ab]|L\d)\b")


def test_keine_internen_kennungen_in_nutzer_texten():
    """Entscheidung des Gründers (4.9.2026): Lastenheft-, Fahrtenbuch-, ADR- und
    Ring-Kennungen verschwinden aus allem, was Nutzer lesen — teils verweisen sie auf
    Dokumente, die gar nicht öffentlich sind. In Kommentaren und Docstrings bleiben sie."""
    fehler = [
        f"{m.group(1)}: {text[:80]}"
        for text in msgids()
        if (m := KENNUNGSMUSTER.search(text))
    ]
    assert not fehler, "interne Kennung im Nutzer-Text:\n  " + "\n  ".join(fehler)


def test_quellen_des_registers_nennen_nur_nachlesbares():
    """Die Quellenangabe im Parameterregister ist öffentlich (§ 2 Abs 6) — sie darf auf die
    Satzung verweisen und auf Anweisungen im Wortlaut, nicht auf interne Dokumentkennungen."""
    from parameter.models import ERSTBESTAND

    fehler = [
        f"{e['schluessel']}: {e['quelle']}"
        for e in ERSTBESTAND
        if KENNUNGSMUSTER.search(e.get("quelle", ""))
    ]
    assert not fehler, "interne Kennung in einer Registerquelle:\n  " + "\n  ".join(fehler)
