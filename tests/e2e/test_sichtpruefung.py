"""Erzeugt die Bilder für die Sichtprüfung des Gründers (FB-P5, Definition of Done 5).

Lauf mit Ablage unter docs/sichtpruefung/<version>/:

    DDOE_SICHTPRUEFUNG=1 python -m pytest tests/e2e/test_sichtpruefung.py -q

Ohne die Umgebungsvariable landen die Bilder in einem flüchtigen Ordner; der Test prüft
dann nur, dass sie entstehen.
"""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {"width": 390, "height": 844}


def _mitglied():
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username="demo1")


def _ruhe(p, js: bool = True) -> None:
    if js:
        p.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")
    else:
        p.wait_for_timeout(800)


def test_screenshots_fuer_die_sichtpruefung(seite, live_server, demo, sichtpruefung):
    bilder = []

    def halte_fest(p, name, js=True):
        _ruhe(p, js)
        ziel = sichtpruefung / f"{name}.png"
        p.screenshot(path=str(ziel))
        bilder.append(ziel)

    # Desktop 1440×900 — hell und dunkel, als Gast und als Mitglied
    p = seite()
    p.goto(f"{live_server.url}/parlament/")
    halte_fest(p, "parlament-desktop-hell-gast")

    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    halte_fest(p, "parlament-desktop-hell-mitglied")

    p = seite(dunkel=True, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    halte_fest(p, "parlament-desktop-dunkel-mitglied")

    # Der Favoriten-Fächer (FB-C1–C4): Wurzel mit fünf Ebenen, entfalteter Ast beim Hover,
    # Mitte-Modus mit Rückweg und Brotkrume, Handy-Variante
    def halte_feld(p, name, feld="#feld-favoriten"):
        _ruhe(p)
        ziel = sichtpruefung / f"{name}.png"
        p.locator(feld).screenshot(path=str(ziel))
        bilder.append(ziel)

    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    halte_feld(p, "faecher-wurzel")
    p.locator("#feld-favoriten .fknoten.enkel").nth(6).hover()
    p.wait_for_timeout(300)
    halte_feld(p, "faecher-hover-ast")
    p.locator("#feld-favoriten .fknoten.kind a[href^='?fach=']").first.click()
    p.wait_for_timeout(900)
    p.locator("#feld-favoriten .fknoten.kind a[href^='?fach=']").first.click()
    p.wait_for_timeout(900)
    halte_feld(p, "faecher-mitte")

    p = seite(viewport=HANDY, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/#feld-favoriten")
    p.wait_for_timeout(500)
    halte_feld(p, "faecher-handy")

    # Der WeicherFilter (FB-B1–B5): Overlay von rechts, Live-Vorschau mit „Warum hier?", eingefahrene Leiste
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    p.locator("#feld-filter .regler-klappe > summary").click()
    p.wait_for_timeout(450)
    halte_feld(p, "filter-overlay", "#feld-filter")
    p.locator('#feld-filter input[name="r_unterstuetzungsphase"]').focus()
    p.keyboard.press("End")
    p.wait_for_function("() => document.querySelector('#filter-liste .warum') !== null")
    p.keyboard.press("Escape")
    p.wait_for_timeout(250)
    p.locator("#filter-liste .warum > summary").first.click()
    p.wait_for_timeout(300)
    halte_feld(p, "filter-vorschau-warum", "#feld-filter")
    p.locator("#feld-filter .pfeil").click()
    p.wait_for_timeout(450)
    halte_feld(p, "filter-leiste-zu", "#feld-filter")

    # Konto-Menü und Anstoß-Popover geöffnet
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    p.locator(".konto > summary").click()
    halte_fest(p, "konto-menue")
    p.keyboard.press("Escape")
    p.locator(".anstoss-leiste .anstoss-fleck > summary").click()
    halte_fest(p, "anstoss-popover")

    # Handy 390×844 — hell und dunkel, dazu das Burger-Panel
    p = seite(viewport=HANDY, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    halte_fest(p, "parlament-handy-hell")
    p.locator(".menue > summary").click()
    p.wait_for_timeout(500)
    halte_fest(p, "handy-menue")

    p = seite(viewport=HANDY, dunkel=True, als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    halte_fest(p, "parlament-handy-dunkel")

    # Ohne JavaScript (Grundschicht) und eine Seite mit Fußzeile zum Vergleich
    p = seite(js=False)
    p.goto(f"{live_server.url}/parlament/")
    halte_fest(p, "parlament-ohne-javascript", js=False)

    from verfahren.models import Antrag

    antrag = Antrag.objects.filter(hervorgehoben=True).first().pk
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/antrag/{antrag}/")
    halte_fest(p, "antragsseite-mit-fusszeile")

    # Die Antragsseite in drei Zonen (S5, FB-F1/F2)
    beratung = (Antrag.objects.filter(phase="beratung").first() or Antrag.objects.first()).pk
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/antrag/{beratung}/")
    halte_fest(p, "antragsseite-drei-zonen")
    p.keyboard.press("End")
    p.wait_for_timeout(500)
    halte_fest(p, "antragsseite-chat-unten")

    p = seite(viewport=HANDY, als=_mitglied())
    p.goto(f"{live_server.url}/antrag/{beratung}/")
    halte_fest(p, "antragsseite-handy-text")
    p.locator('.zreiter[href="#zone-einschaetzung"]').click()
    p.wait_for_timeout(400)
    halte_fest(p, "antragsseite-handy-einschaetzung")

    # Die Partner-Seite (S14a): Vision und Schaubild, der Einstieg mit dem Paket
    p = seite()
    p.goto(f"{live_server.url}/partner/")
    _ruhe(p)
    p.locator("#modell").scroll_into_view_if_needed()
    p.wait_for_timeout(400)
    halte_fest(p, "partner-schaubild")
    p.locator("#einstieg").scroll_into_view_if_needed()
    p.wait_for_timeout(400)
    halte_fest(p, "partner-einstieg")

    p = seite(dunkel=True)
    p.goto(f"{live_server.url}/partner/")
    _ruhe(p)
    p.locator("#modell").scroll_into_view_if_needed()
    p.wait_for_timeout(400)
    halte_fest(p, "partner-schaubild-dunkel")

    # Das Parameterregister in zweiter Fassung (FB-J2): Gruppenkarten, Status, Historie —
    # und die Verwaltung mit dem Abgleich Register/Verfahrensordnung (FB-J1)
    p = seite()
    p.goto(f"{live_server.url}/parameter/")
    halte_fest(p, "parameterregister-gruppen")

    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/verwaltung/parameter/")
    halte_fest(p, "parameterregister-verwaltung")

    # Der Integritätsrat (FB-I6), die öffentliche Beschlussliste (FB-I4) und die
    # Rollenübersicht (FB-K6)
    from gremien.models import Gremium, Rolle, standard_ende

    ir = _mitglied()
    Rolle.objects.get_or_create(
        mitglied=ir, gremium=Gremium.INTEGRITAETSRAT,
        defaults={"endet_am": standard_ende(), "bestaetigt": True},
    )
    p = seite(als=ir)
    p.goto(f"{live_server.url}/gremien/integritaet/")
    halte_fest(p, "integritaetsrat")

    p = seite()
    p.goto(f"{live_server.url}/gremien/beschluesse/")
    halte_fest(p, "beschluesse-oeffentlich")

    p = seite()
    p.goto(f"{live_server.url}/rollen/")
    halte_fest(p, "rollen-uebersicht")

    p = seite()
    p.goto(f"{live_server.url}/regeln/")
    halte_fest(p, "regelverzeichnis")

    p = seite()
    p.goto(f"{live_server.url}/gremien/fachliste/")
    halte_fest(p, "fachliste")

    # S9: der Koordinationsrat mit vier Karten (FB-I5), das Entwurfsfenster als
    # Drei-Spalten-Arbeitsplatz (FB-I2), die Seite eines Parameters mit Tests (FB-J3)
    from verfahren.models import Antrag

    kr = _mitglied()
    Rolle.objects.get_or_create(
        mitglied=kr, gremium=Gremium.KOORDINATIONSRAT,
        defaults={"endet_am": standard_ende(), "bestaetigt": True},
    )
    p = seite(als=kr)
    p.goto(f"{live_server.url}/gremien/koordination/")
    halte_fest(p, "koordinationsrat")

    in_beratung = Antrag.objects.filter(phase="beratung", art="sache").order_by("pk").first()
    if in_beratung is not None:
        Rolle.objects.get_or_create(
            mitglied=kr, gremium=Gremium.EXPERTENRAT_1,
            defaults={"endet_am": standard_ende(), "bestaetigt": True},
        )
        p = seite(als=kr)
        p.goto(f"{live_server.url}/gremien/expertenrat/{in_beratung.pk}/")
        halte_fest(p, "entwurfsfenster-drei-spalten")
        p = seite(als=kr, viewport=HANDY)
        p.goto(f"{live_server.url}/gremien/expertenrat/{in_beratung.pk}/")
        halte_fest(p, "entwurfsfenster-handy")

    p = seite()
    p.goto(f"{live_server.url}/parameter/gremien-beschluss-tage/")
    halte_fest(p, "parameter-seite")

    # S10: der Bereich des Mandatars (FB-L2) mit Instant-Report, Mandatsfrage, Rechenschaft
    # (§ 7 Abs 5) und Berichten (§ 7 Abs 3 lit b); die Profilseite und der Austritt (FB-K5)
    from datetime import timedelta

    from django.utils import timezone

    from mandatare.models import Aufgabe, Mandat, Rechenschaft, Stimmverhalten
    from verfahren.models import Verfahrensordnung, mandatsfrage_eroeffnen

    mandatarin = _mitglied()
    mandat, _ = Mandat.objects.get_or_create(
        mitglied=mandatarin, bezeichnung="Gemeinderätin",
        defaults={"ebene": "gemeinde", "gebiet": mandatarin.gemeinde or "Eferding"},
    )
    jetzt = timezone.now()
    vergangen, _ = Aufgabe.objects.get_or_create(
        mandat=mandat, titel="Budgetsitzung des Gemeinderats",
        defaults={"beschreibung": "Beschluss über den Voranschlag.", "frist": jetzt - timedelta(days=10),
                  "sitzungstag": True},
    )
    Rechenschaft.objects.get_or_create(
        mandat=mandat, aufgabe=vergangen,
        defaults={"gegenstand": "Voranschlag 2027", "sitzung_am": (jetzt - timedelta(days=10)).date(),
                  "stimme": Stimmverhalten.DAFUER, "begruendung": "Der Voranschlag setzt den Beschluss der Mitglieder um."},
    )
    Aufgabe.objects.get_or_create(
        mandat=mandat, titel="Sitzung zum Radwegenetz",
        defaults={"beschreibung": "Antrag auf Ausbau der Radwege.", "frist": jetzt - timedelta(days=3),
                  "sitzungstag": True},
    )
    kommend, _ = Aufgabe.objects.get_or_create(
        mandat=mandat, titel="Soll die Gemeinde dem Klimabündnis beitreten?",
        defaults={"beschreibung": "Der Gemeinderat entscheidet am Sitzungstag über den Beitritt.",
                  "frist": jetzt + timedelta(days=21), "sitzungstag": True},
    )
    ordnung = Verfahrensordnung.objects.filter(aktiv=True).order_by("-version").first()
    if kommend.antrag_id is None and ordnung is not None:
        mandatsfrage_eroeffnen(mandat, kommend, kommend.titel, kommend.beschreibung, ordnung)
        kommend.refresh_from_db()

    p = seite(als=mandatarin)
    p.goto(f"{live_server.url}/mandatare/mein/")
    halte_fest(p, "mandatar-bereich")
    p = seite(als=mandatarin, viewport=HANDY)
    p.goto(f"{live_server.url}/mandatare/mein/")
    halte_fest(p, "mandatar-bereich-handy")

    p = seite()
    p.goto(f"{live_server.url}/mandatare/{mandat.pk}/")
    halte_fest(p, "mandatar-seite-oeffentlich")

    p = seite()
    p.goto(f"{live_server.url}/rechenschaft/")
    halte_fest(p, "rechenschaftsregister")

    if kommend.antrag_id is not None:
        p = seite(als=mandatarin)
        p.goto(f"{live_server.url}/antrag/{kommend.antrag_id}/")
        halte_fest(p, "mandatsfrage-antragsseite")

    # 0.49 (FB-K8): geprüfte Identität — dann zeigt das Profil den Mitgliedsausweis (Vorschau + PDF).
    # Mit Klarname, damit das Bild die Karte zeigt, wie sie ein Mitglied bekommt (die Demo-Pseudonyme
    # heißen „Mitglied n“ — das sähe aus wie der Platzhalter, den die Karte gerade nicht trägt).
    type(mandatarin).objects.filter(pk=mandatarin.pk).update(
        identitaetsstufe="geprueft", first_name="Maria", last_name="Musterfrau-Öhlinger"
    )
    mandatarin.refresh_from_db()
    p = seite(als=mandatarin)
    p.goto(f"{live_server.url}/profil/")
    halte_fest(p, "profil")
    karte = p.locator("#ausweis")
    karte.scroll_into_view_if_needed()
    _ruhe(p)
    ziel = sichtpruefung / "profil-mitgliedsausweis.png"
    karte.screenshot(path=str(ziel))
    bilder.append(ziel)
    p = seite(als=mandatarin, dunkel=True, viewport=HANDY)
    p.goto(f"{live_server.url}/profil/")
    halte_fest(p, "profil-handy-dunkel")

    p = seite(als=mandatarin, js=False)
    p.goto(f"{live_server.url}/profil/austritt/")
    halte_fest(p, "profil-austritt-ohne-javascript", js=False)

    # 0.47: Registrierung mit der Einwilligung zum Klarnamen (§ 5 Abs 3 lit a)
    p = seite()
    p.goto(f"{live_server.url}/mitglied-werden/")
    halte_fest(p, "registrierung-einwilligung")

    # 0.48 (S10c): die Vertrauensfrage (§ 7 Abs 10) — Formular mit Anlässen, Antragsseite mit
    # Anlässen, Bändern, Legende und Stellungnahme, öffentliche Übersicht, Abschnitt „Vertrauen“,
    # Karte des Integritätsrats mit Sperrhinweis (Mandat in der Schonfrist)
    from mandatare.models import Beschluss
    from mitglieder.models import Mitglied
    from verfahren.models import vertrauensfrage_einbringen

    if ordnung is not None:
        Mandat.objects.filter(pk=mandat.pk).update(angetreten=timezone.localdate() - timedelta(days=200))
        mandat.refresh_from_db()
        anlass, _ = Rechenschaft.objects.get_or_create(
            mandat=mandat, gegenstand="Tempo 30 im Ortsgebiet",
            defaults={"sitzung_am": timezone.localdate() - timedelta(days=20), "beschluss_plattform": Beschluss.ANGENOMMEN,
                      "stimme": Stimmverhalten.DAGEGEN, "begruendung": "Die Gemeinde hat andere Prioritäten gesetzt."},
        )
        stellerin = Mitglied.objects.get(username="demo2")
        p = seite(als=stellerin)
        p.goto(f"{live_server.url}/mandatare/{mandat.pk}/vertrauensfrage/")
        halte_fest(p, "vertrauensfrage-stellen")

        vertrauensfrage = vertrauensfrage_einbringen(
            stellerin, mandat, "Die Abweichung vom Beschluss der Mitglieder wurde im Register nicht erklärt.",
            [anlass], [], ordnung,
        )
        p = seite(als=stellerin)
        p.goto(f"{live_server.url}/antrag/{vertrauensfrage.pk}/")
        halte_fest(p, "vertrauensfrage-antragsseite")
        p = seite(als=mandatarin, dunkel=True)
        p.goto(f"{live_server.url}/antrag/{vertrauensfrage.pk}/#stellungnahme")
        halte_fest(p, "vertrauensfrage-antragsseite-dunkel-mandatar")
        p = seite(als=mandatarin, js=False, viewport=HANDY)
        p.goto(f"{live_server.url}/antrag/{vertrauensfrage.pk}/")
        halte_fest(p, "vertrauensfrage-antragsseite-handy-ohne-javascript", js=False)

        p = seite()
        p.goto(f"{live_server.url}/vertrauensfragen/")
        halte_fest(p, "vertrauensfragen-uebersicht")
        p = seite()
        p.goto(f"{live_server.url}/mandatare/{mandat.pk}/#vertrauen")
        halte_fest(p, "mandatar-seite-vertrauen")

        # Sperrhinweis: ein frisches Mandat (Schonfrist 90 Tage, lit g erster Fall) — die Software weist
        # nicht ab, der Integritätsrat sieht die Karte mit Frist und vorbefülltem Beschluss
        frisch, _ = Mandat.objects.get_or_create(
            mitglied=stellerin, bezeichnung="Gemeinderat", defaults={"ebene": "gemeinde", "gebiet": "Eferding"},
        )
        vertrauensfrage_einbringen(
            mandatarin, frisch, "Der Bericht zur ersten Sitzung fehlt.",
            [Rechenschaft.objects.create(
                mandat=frisch, gegenstand="Voranschlag 2027", sitzung_am=timezone.localdate() - timedelta(days=5),
                beschluss_plattform=Beschluss.ANGENOMMEN, stimme=Stimmverhalten.DAGEGEN, begruendung="Dagegen.",
            )], [], ordnung,
        )
        p = seite(als=Mitglied.objects.get(username="demo3"))
        p.goto(f"{live_server.url}/gremien/integritaet/")
        karte = p.locator(".karte", has_text="Vertrauensfragen · Sperre feststellen")
        karte.scroll_into_view_if_needed()
        _ruhe(p)
        ziel = sichtpruefung / "integritaetsrat-sperrhinweis.png"
        karte.screenshot(path=str(ziel))
        bilder.append(ziel)

    erwartet = (
        35 + 8 + 1 + (1 if kommend.antrag_id is not None else 0) - (0 if in_beratung is not None else 2)
        + (7 if ordnung is not None else 0)
    )
    assert len(bilder) == erwartet, (len(bilder), erwartet)
    for bild in bilder:
        assert bild.exists() and bild.stat().st_size > 5000, bild


# ── 0.50.0 (Bauwelle 28./29.9.2026) ─────────────────────────────────────────────────────────────

JSON_RECHTSBEZUG = (
    '{"normen": ['
    '{"titel": "Straßenverkehrsordnung 1960", "ebene": "Bund", "kennung": "BGBl. Nr. 159/1960", '
    '"aenderung": "aendern", "begruendung": "Regelt die zulässige Höchstgeschwindigkeit im Ortsgebiet."}, '
    '{"titel": "Oberösterreichisches Straßengesetz 1991", "ebene": "Land", "aenderung": "beruehrt", '
    '"begruendung": "Gemeindestraßen und ihre Widmung."}], '
    '"hinweis": "Die Verordnung einer Geschwindigkeitsbeschränkung ist Sache der Behörde nach § 43 StVO.", '
    '"unsicherheit": "mittel"}'
)


def _sammelnd(ausser=()):
    from verfahren.models import Antrag

    return Antrag.objects.filter(phase="unterstuetzung", art="sache").exclude(pk__in=ausser).order_by("pk").first()


def test_screenshots_fuer_die_sichtpruefung_050(seite, live_server, demo, sichtpruefung, settings, monkeypatch):
    """Bilder für die Sichtprüfung der Fassung 0.50.0: Direkt-Handlung mit Hinweis im Feld, Fokus-Modus,
    Fächer nach dem Wechsel (mit Bildfolge der Bewegung), Einbringen mit Wortvergleich und
    Bedeutung, Zone-2-Karte „Betroffene Gesetze“ (eingereiht und erledigt), Band nach dem Einbringen,
    Warteschlange der Zukunftswerkstatt, Datenschutzerklärung, Profil-Karte „Nachrichten“,
    Registrierung mit Einwilligung, Willkommensseite mit Stimmrechtssatz, Rollenformular mit Namen und
    die Regelzeile der Prozent-Schwelle auf der Antragsseite — je Desktop 1440×900 und Handy 390×844,
    hell und dunkel, wo es die Seite betrifft; Direkt-Handlung und Fokus-Modus auch ohne JavaScript."""
    from ki.anbieter import Antwort, AttrappenAnbieter
    from mitglieder.models import Mitglied

    bilder = []

    def halte_fest(p, name, js=True):
        _ruhe(p, js)
        ziel = sichtpruefung / f"{name}.png"
        p.screenshot(path=str(ziel))
        bilder.append(ziel)

    def halte_element(p, name, selektor, js=True):
        _ruhe(p, js)
        ziel = sichtpruefung / f"{name}.png"
        p.locator(selektor).first.screenshot(path=str(ziel))
        bilder.append(ziel)

    def konto(name):
        return Mitglied.objects.get(username=name)

    # Direkt-Handlung (Teil 2): Unterstützen in der Feed-Zeile — das Feld bleibt, der Hinweis steht im Feldkopf
    genutzt = []
    for name, dunkel, viewport, suffix in (
        ("demo2", False, None, "desktop-hell"),
        ("demo3", True, None, "desktop-dunkel"),
        ("demo4", False, HANDY, "handy"),
    ):
        antrag = _sammelnd()
        p = seite(als=konto(name), dunkel=dunkel, viewport=viewport)
        p.goto(f"{live_server.url}/parlament/#feld-filter")
        _ruhe(p)
        p.locator(f"#u-filter-{antrag.pk}").click()
        p.wait_for_selector(f"#u-filter-{antrag.pk}.gewaehlt")
        p.wait_for_selector("#feld-filter .feld-hinweis")
        p.locator(f"#u-filter-{antrag.pk}").scroll_into_view_if_needed()
        halte_fest(p, f"parlament-hinweis-im-feld-{suffix}")
        # Zurückziehen: Die dritte Unterstützung erreichte die Schwelle, der Antrag ginge in die Beratung
        p.locator(f"#u-filter-{antrag.pk}").click()
        p.wait_for_selector(f"#u-filter-{antrag.pk}:not(.gewaehlt)")
        genutzt.append(antrag.pk)
    antrag = _sammelnd()
    p = seite(js=False, als=konto("demo5"))
    p.goto(f"{live_server.url}/parlament/")
    p.wait_for_timeout(800)
    p.locator(f"#u-filter-{antrag.pk}").click()
    p.wait_for_load_state()
    halte_fest(p, "parlament-hinweis-im-feld-ohne-javascript", js=False)

    # Fokus-Modus (Teil 7): ein Feld füllt das Raster — Knopf ⤢, ohne JavaScript über ?fokus=
    for dunkel, suffix in ((False, "desktop-hell"), (True, "desktop-dunkel")):
        p = seite(als=_mitglied(), dunkel=dunkel)
        p.goto(f"{live_server.url}/parlament/")
        _ruhe(p)
        p.locator("#feld-favoriten .fokus-knopf").click()
        halte_fest(p, f"parlament-fokus-favoriten-{suffix}")
    p = seite(js=False)
    p.goto(f"{live_server.url}/parlament/?fokus=favoriten")
    halte_fest(p, "parlament-fokus-favoriten-ohne-javascript", js=False)

    # Fächer nach dem Wechsel (Teil 7, FLIP) — und die Bewegung als Bildfolge und GIF
    for dunkel, viewport, suffix in ((False, None, "desktop-hell"), (True, None, "desktop-dunkel"), (False, HANDY, "handy")):
        p = seite(als=_mitglied(), dunkel=dunkel, viewport=viewport)
        p.goto(f"{live_server.url}/parlament/#feld-favoriten")
        _ruhe(p)
        link = p.locator("#feld-favoriten .fknoten.kind a[href^='?fach=']").first
        titel = link.get_attribute("title")
        link.click()
        p.wait_for_function(
            "(t) => (document.querySelector('#feld-favoriten .fknoten.anker .fname') || {}).textContent?.trim() === t",
            arg=titel,
        )
        if viewport is None:
            _ruhe(p)
            ziel = sichtpruefung / f"faecher-nach-flip-{suffix}.png"
            p.locator("#feld-favoriten").screenshot(path=str(ziel))
            bilder.append(ziel)
        else:
            halte_fest(p, f"faecher-nach-flip-{suffix}")

    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/parlament/")
    _ruhe(p)
    p.locator("#feld-favoriten .fknoten.kind a[href^='?fach=']").first.click()
    p.wait_for_function("() => document.getAnimations().some(a => a.id === 'faecher-flip')")
    # Die Bewegung anhalten und an vier Stellen festhalten — deterministisch, unabhängig vom Rechner
    dauer = p.evaluate(
        "() => { const a = document.getAnimations().filter(x => x.id === 'faecher-flip');"
        " a.forEach(x => x.pause()); return Math.max(...a.map(x => x.effect.getComputedTiming().endTime)); }"
    )
    rahmen = []
    for i, anteil in enumerate((0.0, 0.33, 0.66, 1.0), start=1):
        p.evaluate(
            "(t) => document.getAnimations().filter(x => x.id === 'faecher-flip').forEach(x => { x.currentTime = t; })",
            dauer * anteil,
        )
        p.wait_for_timeout(50)
        ziel = sichtpruefung / f"faecher-flip-{i}.png"
        p.locator("#feld-favoriten").screenshot(path=str(ziel))
        bilder.append(ziel)
        rahmen.append(ziel)
    p.evaluate("() => document.getAnimations().filter(x => x.id === 'faecher-flip').forEach(x => x.finish())")
    from PIL import Image  # Pillow kommt mit reportlab (ADR-010), keine eigene Abhängigkeit

    folge = [Image.open(r).convert("P", palette=Image.Palette.ADAPTIVE) for r in rahmen]
    gif = sichtpruefung / "faecher-flip.gif"
    folge[0].save(gif, save_all=True, append_images=folge[1:], duration=[400, 140, 140, 900], loop=0)
    bilder.append(gif)

    # Einbringen mit Wortvergleich · Bedeutung (Teil 4) — Attrappe statt Anbieter, Textvektoren ohne Netz
    settings.DDOE_KI_ANBIETER = "attrappe"
    monkeypatch.setattr(
        AttrappenAnbieter, "frage", lambda self, auftrag, eingabe: Antwort(JSON_RECHTSBEZUG, "attrappe-1", 120, 80)
    )
    vorbild = _sammelnd(ausser=genutzt + [antrag.pk])
    vorbild_text = vorbild.aktueller_text()
    stellerin = _mitglied()
    type(stellerin).objects.filter(pk=stellerin.pk).update(post_einwilligung=True)
    stellerin.refresh_from_db()
    for dunkel, viewport, suffix in ((False, None, "desktop-hell"), (True, None, "desktop-dunkel"), (False, HANDY, "handy")):
        p = seite(als=stellerin, dunkel=dunkel, viewport=viewport)
        p.goto(f"{live_server.url}/einbringen/")
        p.locator('input[name="titel"]').fill(vorbild.titel + " — auch in Nachbargemeinden")
        p.locator('textarea[name="wortlaut"]').fill(vorbild_text.wortlaut)
        with p.expect_navigation():
            p.get_by_role("button", name="Antrag einbringen").click()
        p.locator(".kommentar .kopf").first.wait_for()
        p.locator(".kommentar .kopf").first.scroll_into_view_if_needed()
        halte_fest(p, f"einbringen-aehnlichkeit-{suffix}")

    # „Trotzdem einbringen“ → Antragsseite mit Band und der Karte „Betroffene Gesetze“ in der Warteschlange
    with p.expect_navigation():
        p.locator('button[name="trotzdem"]').click()
    neu_pk = int(p.url.split("/antrag/")[1].split("/")[0])
    p = seite(als=stellerin)
    p.goto(f"{live_server.url}/antrag/{neu_pk}/?neu=1")
    halte_fest(p, "antrag-neu-band-desktop")
    p = seite(als=stellerin, viewport=HANDY)
    p.goto(f"{live_server.url}/antrag/{neu_pk}/?neu=1")
    halte_fest(p, "antrag-neu-band-handy")
    for dunkel, suffix in ((False, "desktop-hell"), (True, "desktop-dunkel")):
        p = seite(als=stellerin, dunkel=dunkel)
        p.goto(f"{live_server.url}/antrag/{neu_pk}/#rechtsbezug")
        halte_element(p, f"antrag-rechtsbezug-eingereiht-{suffix}", "#rechtsbezug")

    # Die öffentliche Warteschlange, solange der Auftrag wartet
    for dunkel, viewport, suffix in ((False, None, "desktop-hell"), (True, None, "desktop-dunkel"), (False, HANDY, "handy")):
        p = seite(dunkel=dunkel, viewport=viewport)
        p.goto(f"{live_server.url}/zukunftswerkstatt/#steckplatz")
        p.locator("#steckplatz").scroll_into_view_if_needed()
        halte_fest(p, f"zukunftswerkstatt-warteschlange-{suffix}")

    # Der Hintergrundlauf rechnet den Auftrag — die Karte zeigt das Ergebnis mit Kennzeichnung
    from ki.warteschlange import abarbeiten

    abarbeiten()
    for dunkel, viewport, suffix in ((False, None, "desktop-hell"), (True, None, "desktop-dunkel"), (False, HANDY, "handy")):
        p = seite(als=stellerin, dunkel=dunkel, viewport=viewport)
        p.goto(f"{live_server.url}/antrag/{neu_pk}/#rechtsbezug")
        if viewport is not None:
            p.locator('.zreiter[href="#zone-einschaetzung"]').click()
            p.wait_for_timeout(400)
            p.locator("#rechtsbezug").scroll_into_view_if_needed()
            halte_fest(p, f"antrag-rechtsbezug-erledigt-{suffix}")
        else:
            halte_element(p, f"antrag-rechtsbezug-erledigt-{suffix}", "#rechtsbezug")
    settings.DDOE_KI_ANBIETER = "mistral"

    # Datenschutzerklärung (Teil 5, freigegeben 29.9.2026) — öffentlich, ohne Anmeldung
    for dunkel, viewport, suffix in ((False, None, "desktop-hell"), (True, None, "desktop-dunkel"), (False, HANDY, "handy")):
        p = seite(dunkel=dunkel, viewport=viewport)
        p.goto(f"{live_server.url}/datenschutz/")
        halte_fest(p, f"datenschutz-{suffix}")

    # Profil: Karte „Nachrichten“ mit dem Haken der E-Mail-Einwilligung (Teil 3)
    p = seite(als=stellerin)
    p.goto(f"{live_server.url}/profil/#nachrichten")
    p.locator("#nachrichten").scroll_into_view_if_needed()
    halte_element(p, "profil-nachrichten-desktop", "#nachrichten")
    p = seite(als=stellerin, dunkel=True, viewport=HANDY)
    p.goto(f"{live_server.url}/profil/#nachrichten")
    p.locator("#nachrichten").scroll_into_view_if_needed()
    halte_fest(p, "profil-nachrichten-handy-dunkel")

    # Registrierung mit dem Haken der E-Mail-Einwilligung (Voreinstellung: nein)
    for viewport, suffix in ((None, "desktop"), (HANDY, "handy")):
        p = seite(viewport=viewport)
        p.goto(f"{live_server.url}/mitglied-werden/")
        p.locator('input[name="post_einwilligung"]').scroll_into_view_if_needed()
        halte_fest(p, f"registrieren-einwilligung-{suffix}")

    # Willkommensseite mit dem Stimmrechtssatz statt fester Monatsfristen (Teil 5)
    for viewport, suffix in ((None, "desktop"), (HANDY, "handy")):
        p = seite(als=stellerin, viewport=viewport)
        p.goto(f"{live_server.url}/willkommen/")
        halte_fest(p, f"willkommen-stimmrechtssatz-{suffix}")

    # Verwaltung: Rollen auf Zeit — die Auswahl nennt Name und Mitgliedsnummer, keine Anmeldeadresse
    verwaltung = Mitglied.objects.get(username="demo5")
    Mitglied.objects.filter(pk=verwaltung.pk).update(ist_admin=True)  # die Seite ist nur für die Verwaltung
    verwaltung.refresh_from_db()
    p = seite(als=verwaltung)
    p.goto(f"{live_server.url}/verwaltung/rollen/")
    auswahl = p.locator('select[name="mitglied"]')
    auswahl.scroll_into_view_if_needed()
    halte_fest(p, "rollen-formular-namen")

    # Die Prozent-Schwelle (Teil 8) — eine Ordnung der Fassung 4, ein neuer Antrag, die Regelzeile
    from verfahren.models import Verfahrensordnung, antrag_einbringen

    alt = Verfahrensordnung.objects.filter(aktiv=True).order_by("-version").first()
    regeln = {**alt.regeln, "version": alt.version + 1, "unterstuetzung_anteil": 0.05}  # Erstbestand fünf Prozent
    vierte = Verfahrensordnung.objects.create(
        policy_id=alt.policy_id, version=alt.version + 1, regeln=regeln, aktiv=True
    )
    prozent = antrag_einbringen(
        stellerin, "Radwege entlang aller Landesstraßen", "Entlang jeder Landesstraße entsteht ein Radweg.",
        "Sicherer Schulweg.", vierte,
    )
    for viewport, suffix in ((None, "desktop"), (HANDY, "handy")):
        p = seite(viewport=viewport)
        p.goto(f"{live_server.url}/antrag/{prozent.pk}/")
        p.locator("details.klappe summary", has_text="Eingefrorene Regeln").click()
        p.locator("dl.regelliste").scroll_into_view_if_needed()
        halte_fest(p, f"parameter-prozentschwelle-{suffix}")

    assert len(bilder) == 40, len(bilder)
    for bild in bilder:
        assert bild.exists() and bild.stat().st_size > 5000, bild
