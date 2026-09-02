"""Tests für den App-Rahmen (Bauschritt S1): Leiste, Konto-Menü, Bänder, Raster, Tableiste, Anstoß, Alpine.

Jeder Test prüft serverseitig gerendertes Markup — die Grundschicht, die ohne JavaScript gilt.
Layout und Bewegung prüfen die Bildschirmtests unter tests/e2e/.
"""

import re

import pytest
from django.urls import reverse

from gremien.test_werkstatt import rolle_geben
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

HAUPTPUNKTE = ["/parlament/", "/mandatare/", "/gremien/", "/umsetzung/", "/zukunftswerkstatt/", "/uebersicht/"]


def _feld(html: str, feld_id: str) -> str:
    return html.split(f'id="{feld_id}"', 1)[1].split("</section>", 1)[0]


def _leiste(html: str) -> str:
    return html.split('<header class="leiste">', 1)[1].split("</header>", 1)[0]


def _hauptnav(html: str) -> str:
    return _leiste(html).split('<nav class="haupt"', 1)[1].split("</nav>", 1)[0]


def _konto(html: str) -> str:
    # bis zum Burger-Menü: das Konto-Popover enthält ein verschachteltes <details> („Mehr“)
    return _leiste(html).split('<details class="konto"', 1)[1].split('<details class="menue"', 1)[0]


# ── App-Leiste (FB-A1, FB-N3, FB-N8, D-N8) ─────────────────────────────────────────


def test_eine_leiste_mit_menuereihenfolge_d_n8(client):
    html = client.get(reverse("verfahren:parlament")).content.decode()
    assert html.count('<header class="leiste">') == 1
    assert html.count('<nav class="haupt"') == 1
    assert re.findall(r'href="(/[a-z]+/)"', _hauptnav(html)) == HAUPTPUNKTE
    assert "menue-schalter" not in html and 'class="wer"' not in html and "nav-cta" not in html
    assert 'class="an" aria-current="page">Parlament</a>' in _hauptnav(html)


def test_aktiver_menuepunkt_auch_auf_unterseiten(client):
    for pfad, erwartet in [
        ("/mandatare/", "Mandatare"),
        ("/gremien/", "Gremien"),
        ("/umsetzung/", "Umsetzungsregister"),
        ("/zukunftswerkstatt/", "Zukunftswerkstatt"),
        ("/uebersicht/", "Übersicht"),
    ]:
        nav = _hauptnav(client.get(pfad).content.decode())
        aktive = re.findall(r'class="an" aria-current="page">([^<]+)</a>', nav)
        assert aktive == [erwartet], pfad
    assert 'class="an"' not in _hauptnav(client.get("/").content.decode())


def test_antrag_knopf_gefuellt_nur_fuer_mitglieder(client):
    gast = _leiste(client.get(reverse("verfahren:parlament")).content.decode())
    assert 'href="/einbringen/"' not in gast  # FB-N8: Gäste sehen Anmelden · Mitglied werden · EN
    client.force_login(mitglied_anlegen())
    leiste = _leiste(client.get(reverse("verfahren:parlament")).content.decode())
    knopf = leiste.split('<a class="cta" href="/einbringen/">', 1)[1].split("</a>", 1)[0]
    assert "＋" in knopf and "Antrag einbringen" in knopf


def test_leiste_gast(client):
    leiste = _leiste(client.get(reverse("verfahren:parlament")).content.decode())
    assert 'class="avatar' not in leiste and "Abmelden" not in leiste and "Mein Gremium" not in leiste
    assert '<a class="anmelden" href="/anmelden/">' in leiste
    assert '<a class="btn klein" href="/mitgliedschaft/">' in leiste
    assert '<details class="mehr"' in leiste and 'href="/partner/"' in leiste
    assert 'class="thema" role="group" aria-label="Erscheinungsbild" hidden x-data="thema"' in leiste
    assert 'class="sprache" lang="en">EN</button>' in leiste


def test_konto_menue_mitglied_ohne_rolle(client):
    client.force_login(mitglied_anlegen())
    html = client.get(reverse("verfahren:parlament")).content.decode()
    konto = _konto(html)
    assert 'class="avatar" x-ref="ausloeser"' in konto and ">A</summary>" in konto
    assert 'href="/beitrag/"' in konto and 'action="/i18n/setlang/"' in konto
    assert '<form method="post" action="/abmelden/"' in konto
    assert 'x-data="thema"' in konto and 'href="/partner/"' in konto
    assert "Mein Gremium" not in html and 'href="/verwaltung/"' not in html
    assert 'class="cta"' in _leiste(html) and '<details class="mehr"' not in _leiste(html)


def test_konto_menue_mit_gremienrolle(client):
    m = mitglied_anlegen()
    client.force_login(m)
    assert "Mein Gremium" not in client.get("/").content.decode()
    rolle_geben(m)
    konto = _konto(client.get("/").content.decode())
    assert 'class="avatar ring"' in konto and 'href="/gremien/mein/">Mein Gremium</a>' in konto


def test_konto_menue_admin(client):
    m = mitglied_anlegen("admina")
    m.ist_admin = True
    m.save(update_fields=["ist_admin"])
    client.force_login(m)
    assert 'href="/verwaltung/">Verwaltung</a>' in _konto(client.get("/").content.decode())


def test_sprachumschalter_bleibt_formular(client):
    client.post(reverse("set_language"), {"language": "en", "next": "/parlament/"})
    html = client.get(reverse("verfahren:parlament")).content.decode()
    assert 'lang="en"' in html and ">Parliament</a>" in html
    assert 'class="sprache" lang="de">DE</button>' in _leiste(html)
    client.post(reverse("set_language"), {"language": "de", "next": "/parlament/"})
    assert ">Parlament</a>" in client.get(reverse("verfahren:parlament")).content.decode()


def test_burger_menue_ist_details_ohne_checkbox(client):
    leiste = _leiste(client.get("/").content.decode())
    assert 'type="checkbox"' not in leiste
    menue = leiste.split('<details class="menue"', 1)[1]
    assert 'aria-label="Menü"' in menue and '<div class="panel">' in menue
    assert re.findall(r'href="(/[a-z]+/)"', menue.split('<nav class="panel-nav"', 1)[1].split("</nav>", 1)[0]) == HAUPTPUNKTE


# ── Anstoß (FB-K3, Position) ───────────────────────────────────────────────────────


def test_anstoss_im_parlament_in_der_leiste_sonst_schwebend(client):
    html = client.get(reverse("verfahren:parlament")).content.decode()
    assert 'class="anstoss-leiste"' in _leiste(html) and 'class="anstoss-ecke"' not in html
    assert html.count('class="anstoss-fleck"') == 1 and 'title="Anstoß geben"' in html
    for pfad in ["/", reverse("mitglieder:mitgliedschaft"), reverse("verfahren:umsetzung")]:
        html = client.get(pfad).content.decode()
        assert 'class="anstoss-leiste"' not in html and html.count('class="anstoss-fleck"') == 1, pfad
        assert html.index("</main>") < html.index('class="anstoss-ecke"'), pfad

# ── Bänder, Fußzeile, Meldungen (FB-A6, FB-A1, FB-A2) ──────────────────────────


def test_parlament_ohne_fusszeile_andere_seiten_mit(client):
    assert "<footer" not in client.get(reverse("verfahren:parlament")).content.decode()
    client.force_login(mitglied_anlegen())
    assert "<footer" not in client.get(reverse("verfahren:parlament")).content.decode()
    for pfad in ["/", reverse("verfahren:umsetzung"), reverse("mitglieder:mitgliedschaft")]:
        assert "<footer" in client.get(pfad).content.decode(), pfad


def test_gastband_unter_der_leiste(client):
    html = client.get(reverse("verfahren:parlament")).content.decode()
    zwischen = html.split("</header>", 1)[1].split("<main", 1)[0]
    assert 'class="band gast"' in zwischen and "als Gast" in zwischen
    assert 'href="/anmelden/"' in zwischen and 'href="/mitgliedschaft/"' in zwischen
    assert '<body class="voll mit-band"' in html
    assert 'class="meldung info"' not in html.split("<main", 1)[1]
    client.force_login(mitglied_anlegen())
    html = client.get(reverse("verfahren:parlament")).content.decode()
    assert 'class="band' not in html and '<body class="voll"' in html
    assert 'class="band' not in client.get("/").content.decode()


def test_pausiert_band_unter_der_leiste(client):
    m = mitglied_anlegen()
    m.status = "pausiert"
    m.save(update_fields=["status"])
    client.force_login(m)
    for pfad in ["/", reverse("verfahren:parlament")]:
        html = client.get(pfad).content.decode()
        zwischen = html.split("</header>", 1)[1].split("<main", 1)[0]
        assert 'class="band pausiert"' in zwischen and 'href="/willkommen/"' in zwischen, pfad
        assert "mit-band" in html.split("<body", 1)[1].split(">", 1)[0], pfad


def test_flash_im_parlament_im_stapel_nicht_im_raster(client):
    client.force_login(mitglied_anlegen())
    antwort = client.post(
        reverse("verfahren:filter_anwenden"), {"weiter": "/parlament/", "r_chronologisch": "40"}, follow=True
    )
    html = antwort.content.decode()
    stapel = html.split('<div class="meldungen">', 1)[1].split('class="parlament"', 1)[0]
    assert 'class="meldung ' in stapel and 'x-data="meldung"' in stapel and 'class="meldung-x"' in stapel


# ── Raster, Landmarken, Tableiste, Skelette (FB-A1, FB-A3) ──────────────────────


def test_felder_sind_landmarken_mit_tastatur_scroll(client):
    html = client.get(reverse("verfahren:parlament")).content.decode()
    for feld in ("filter", "favoriten", "wichtig", "region"):
        assert html.count(f'id="feld-{feld}"') == 1
        assert f'<section class="feld" id="feld-{feld}" aria-labelledby="h-{feld}">' in html
        assert f'<h2 id="h-{feld}">' in html
    assert html.count('<div class="feld-korpus" tabindex="0">') == 4
    assert '<body class="voll mit-band"' in html


def test_tableiste_nur_im_parlament(client):
    html = client.get(reverse("verfahren:parlament")).content.decode()
    tabs = html.split('<nav class="tabs"', 1)[1].split("</nav>", 1)[0]
    assert re.findall(r'href="([^"]+)"', tabs) == [
        "#feld-filter", "#feld-favoriten", "/einbringen/", "#feld-wichtig", "#feld-region",
    ]
    assert 'class="plus"' in tabs and 'aria-label="Bereiche"' in html
    assert html.index('class="parlament"') < html.index('<nav class="tabs"')
    assert '<nav class="tabs"' not in client.get("/").content.decode()


def test_skelette_und_feldtausch_mit_uebergang(client):
    client.force_login(mitglied_anlegen())
    html = client.get(reverse("verfahren:parlament")).content.decode()
    assert _feld(html, "feld-filter").count('class="skelett b70"') == 5
    assert _feld(html, "feld-favoriten").count('class="skelett b70"') == 4
    assert _feld(html, "feld-wichtig").count("kachel-form") == 4
    assert _feld(html, "feld-region").count("kachel-form") == 3
    for feld in ("filter", "favoriten"):
        treffer = re.findall(rf'hx-select="#feld-{feld}"[^>]*', html)
        assert treffer, feld
        for tag in treffer:
            assert 'hx-swap="outerHTML transition:true"' in tag and f'hx-indicator="#feld-{feld}"' in tag
    assert 'hx-swap="outerHTML"' not in html.split('class="parlament"', 1)[1]


def test_regler_ohne_inline_handler_mit_alpine(client):
    client.force_login(mitglied_anlegen())
    feld = _feld(client.get(reverse("verfahren:parlament")).content.decode(), "feld-filter")
    assert "oninput" not in feld
    assert feld.count('type="range"') >= 8
    assert feld.count('x-model.number="wert"') == feld.count('type="range"')
    assert '<output x-text="wert">' in feld


def test_thema_skript_vor_dem_stil_und_html_ohne_serverseitiges_thema(client):
    html = client.get("/").content.decode()
    kopf = html.split("</head>", 1)[0]
    assert kopf.index("verfahren/js/thema.js") < kopf.index("<style>")
    assert "data-theme" not in html.split("<head>", 1)[0]
