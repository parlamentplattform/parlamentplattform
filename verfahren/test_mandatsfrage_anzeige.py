"""S10, Cluster R — die Mandatsfrage (§ 7 Abs 9) in der Anzeige: Antragsseite, Kachel,
Feed-Zeile, Übersicht, Archiv. Überall abstimmbar wie ein Sachantrag (Ja/Nein/Enthaltung),
nirgends eine Personenwahl, und ohne die Spuren der Phasen, die sie nie hatte."""

import json
from datetime import timedelta

import pytest
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from verfahren import archiv as archivkern
from verfahren.models import Antrag, Antragsart, stimme_abgeben
from verfahren.test_mandatsfrage import FRAGE, eroeffnen, mandat_mit_report
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401
from verfahren.views import _regeln_lesbar

pytestmark = pytest.mark.django_db


def _mandatsfrage(ordnung, n=2):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(n)]
    mandat, aufgabe = mandat_mit_report(leute[0])
    return eroeffnen(mandat, aufgabe, ordnung), mandat, aufgabe, leute


def _beenden(antrag):
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - timedelta(days=8))
    antrag.refresh_from_db()
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase in ("angenommen", "abgelehnt")
    return antrag


# --- Antragsseite --------------------------------------------------------------------------


def test_antragsseite_zeigt_kopfzeile_band_chip_und_ja_nein_handlung(client, ordnung):  # noqa: F811
    antrag, mandat, aufgabe, leute = _mandatsfrage(ordnung)
    client.force_login(leute[1])
    inhalt = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()

    kopf = inhalt.split('class="a-kopf"')[1].split("</header>")[0]
    assert "Mandatsfrage von" in kopf and f'href="/mandatare/{mandat.pk}/"' in kopf
    assert f"Sitzungstag {timezone.localtime(aufgabe.frist):%d.%m.%Y %H:%M}" in kopf
    assert "Unterstützung" not in kopf.split("band-gold")[0], "kein „n Unterstützungen“ — es gab keine"
    assert 'class="band-gold mandatsfrage-band"' in kopf
    assert "Mandatsfrage nach § 7 Abs 9 — ohne Unterstützungs- und Beratungsphase" in kopf
    chips = kopf.split('class="a-chips"')[1].split("</div>")[0]
    assert ">Mandatsfrage</span>" in chips and "Mandats-Kandidatur" not in chips

    # Abstimmbar wie ein Sachantrag — nie eine Personenwahl
    assert 'id="abstimmen"' in inhalt and f'action="/antrag/{antrag.pk}/abstimmen/"' in inhalt
    assert 'name="stimme" value="ja"' in inhalt and 'name="stimme" value="enthaltung"' in inhalt
    assert "Bewerbung" not in inhalt and "Zur Wahl" not in inhalt
    # Zone 2 bleibt möglich (KI-Einschätzung ohne Zwang) — nur Personenwahlen haben keine
    assert 'id="zone-einschaetzung"' in inhalt


def test_regeln_der_mandatsfrage_nennen_keine_uebersprungenen_phasen(client, ordnung):  # noqa: F811
    antrag, *_ = _mandatsfrage(ordnung, n=1)
    namen = [n for n, _w in _regeln_lesbar(antrag.policy(), antrag.art)]
    assert namen == ["Unterstützung und Beratung", "Abstimmung", "Mindestbeteiligung", "Mehrheit", "Verfahrensordnung"]
    werte = dict(_regeln_lesbar(antrag.policy(), antrag.art))
    assert werte["Unterstützung und Beratung"] == "keine Unterstützungs- und Beratungsphase (§ 7 Abs 9)"
    assert werte["Abstimmung"].startswith("7 Tage · ") and "§ 7 Abs 9" in werte["Abstimmung"]
    assert werte["Verfahrensordnung"] == "test-ordnung v1"
    # Der Sachantrag behält seine volle Liste
    assert [n for n, _w in _regeln_lesbar(antrag.policy())][:3] == ["Unterstützungsschwelle", "Frist zum Unterstützen", "Beratung"]

    inhalt = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    regeln = inhalt.split("Eingefrorene Regeln")[1].split("</dl>")[0]
    assert "keine Unterstützungs- und Beratungsphase (§ 7 Abs 9)" in regeln
    assert "Unterstützungsschwelle" not in regeln and "Frist zum Unterstützen" not in regeln
    assert "Sperre für Wiedereinbringung" not in regeln


def test_beendete_mandatsfrage_zeigt_ja_nein_ergebnis(client, ordnung):  # noqa: F811
    antrag, _mandat, _aufgabe, leute = _mandatsfrage(ordnung, n=3)
    stimme_abgeben(antrag, leute[1], "ja")
    stimme_abgeben(antrag, leute[2], "ja")
    _beenden(antrag)
    inhalt = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert antrag.phase == "angenommen"
    assert "Ja 2 · Nein 0 · Enthaltung 0 · Stimmberechtigte 3" in inhalt
    assert "Stimmliste exportieren" in inhalt and "gewählt" not in inhalt


def test_wahlvorschlag_link_nur_wenn_es_den_export_gibt(client, ordnung):  # noqa: F811
    """E7: Den Markdown-Export der Reihung baut der Mandatare-Teil; die Antragsseite verlinkt ihn,
    sobald `mandatare:wahlvorschlag` auflösbar ist — vorher steht da kein toter Link."""
    from verfahren.models import bewerbung_einreichen, bewerbung_zustimmen
    from verfahren.test_kandidatur import _in_abstimmung, _kandidatur

    autor, anna, bernd = mitglied_anlegen("autor"), mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    antrag = _kandidatur(ordnung, autor)
    b = bewerbung_einreichen(antrag, anna, "Ich trete an.")
    _in_abstimmung(antrag, [anna, bernd])
    bewerbung_zustimmen(antrag, bernd, b)
    _beenden(antrag)
    try:
        ziel = reverse("mandatare:wahlvorschlag", args=[antrag.pk])
    except NoReverseMatch:
        ziel = None
    antwort = client.get(reverse("verfahren:antrag", args=[antrag.pk]))
    inhalt = antwort.content.decode()
    assert antwort.context["wahlvorschlag_url"] == ziel
    assert ("Reihung als Wahlvorschlag (Markdown)" in inhalt) is (ziel is not None)
    if ziel:
        assert f'href="{ziel}"' in inhalt


# --- Kachel, Feed-Zeile, Übersicht ----------------------------------------------------------


def test_kachel_und_feedzeile_tragen_badge_und_ja_nein_handlung(client, ordnung):  # noqa: F811
    antrag, _mandat, _aufgabe, leute = _mandatsfrage(ordnung)
    client.force_login(leute[1])  # wohnt in der Gemeinde des Mandats → Regionsband
    html = client.get(reverse("verfahren:parlament")).content.decode()

    region = html.split('id="feld-region"')[1].split("</section>")[0]
    kachel = region.split('<article class="kachel"')[1].split("</article>")[0]
    assert FRAGE["titel"] in kachel
    assert '<span class="badge badge--hell">Mandatsfrage</span>' in kachel
    assert "Personenwahl" not in kachel and "Zur Wahl der Bewerbungen" not in kachel
    assert f'action="/antrag/{antrag.pk}/abstimmen/"' in kachel and 'name="stimme" value="nein"' in kachel

    feld = html.split('id="feld-filter"')[1].split("</section>")[0]
    zeile = feld.split('class="fz')[1].split('class="k-erfasst"')[0]
    assert '<span class="chip klein">Mandatsfrage</span>' in zeile
    assert "Personenwahl" not in zeile and "Zur Wahl" not in zeile
    assert '<details class="abstimmen">' in zeile and f'action="/antrag/{antrag.pk}/abstimmen/"' in zeile

    # Und die Handlung wirkt: eine Stimme aus der Kachel landet als Ja/Nein-Stimme
    antwort = client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "ja", "weiter": "/parlament/"})
    assert antwort.status_code == 302 and antrag.stimmabgaben.count() == 1


def test_uebersicht_kennzeichnet_die_mandatsfrage_und_zaehlt_ja_nein(client, ordnung):  # noqa: F811
    antrag, _mandat, _aufgabe, leute = _mandatsfrage(ordnung, n=3)
    inhalt = client.get(reverse("uebersicht:index")).content.decode()
    karte = inhalt.split(FRAGE["titel"])[1].split("</div>")[0]
    assert '<span class="badge badge--hell">Mandatsfrage</span>' in karte and "Personenwahl" not in karte
    assert "Tendenz verdeckt bis Fristende" in inhalt

    stimme_abgeben(antrag, leute[1], "ja")
    stimme_abgeben(antrag, leute[2], "nein")
    _beenden(antrag)
    antwort = client.get(reverse("uebersicht:index"))
    inhalt = antwort.content.decode()
    zeile = next(z for z in antwort.context["abstimmungen"] if z["antrag"].pk == antrag.pk)
    assert zeile["mandatsfrage"] is True and zeile["personenwahl"] is False
    assert zeile["ja"] == 1 and zeile["nein"] == 1 and zeile["gewaehlt"] is None
    assert "Gewählt" not in inhalt and "Keine Bewerbung" not in inhalt


# --- Archiv ---------------------------------------------------------------------------------


def test_archiv_ohne_leeren_unterstuetzungsblock(ordnung):  # noqa: F811
    antrag, *_ = _mandatsfrage(ordnung, n=1)
    phasen = [b["phase"] for b in archivkern.zeitleiste(antrag)]
    assert phasen == ["abstimmung"], phasen
    assert [b["laufend"] for b in archivkern.zeitleiste(antrag)] == [True]

    daten = json.loads(archivkern.als_json(antrag))
    assert daten["antrag"]["art"] == "Mandatsfrage"
    assert [b["phase"] for b in daten["zeitleiste"]] == ["abstimmung"]
    assert [e["typ"] for e in daten["audit"]] == ["kategorien_zugeordnet", "mandatsfrage_eroeffnet", "phasenwechsel"]

    text = archivkern.als_markdown(antrag)
    assert " · Mandatsfrage · " in text
    assert "Eröffnet:" in text and "ohne Unterstützungs- und Beratungsphase (§ 7 Abs 9)" in text
    assert "## Unterstützungsphase" not in text and "Unterstützungen" not in text.split("##")[0]
    assert "## Abstimmung" in text


def test_sachantrag_behaelt_seinen_unterstuetzungsblock(ordnung):  # noqa: F811
    """Die Regel gilt nur für die Mandatsfrage — ein Sachantrag beginnt weiter mit der Unterstützung."""
    from verfahren.models import antrag_einbringen
    from verfahren.test_views_aktionen import ANTRAG

    antrag = antrag_einbringen(mitglied_anlegen(), **ANTRAG, ordnung=ordnung)
    assert [b["phase"] for b in archivkern.zeitleiste(antrag)] == ["unterstuetzung"]
    assert antrag.art == Antragsart.SACHE
