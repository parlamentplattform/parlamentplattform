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

