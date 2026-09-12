"""S10, Cluster R — der Nebenwohnsitz (FB-J6, E10) an seinen zwei Wirkstellen: „Meine Region“
und das Einbringen. Nur bei Stellgröße `region-nebenwohnsitz-zaehlt` = 1, nur zusätzlich, und
nie am Stimmrecht (§ 5 Abs 6, Grundregel 4)."""

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse

from mitglieder.models import Gemeinde
from parameter.models import Parameter
from verfahren.models import Antrag, antrag_einbringen, stimme_abgeben
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db

HAUPT = "St. Marienkirchen an der Polsenz"
NEBEN = "Wels"


def _schalter(wert):
    Parameter.objects.update_or_create(
        schluessel="region-nebenwohnsitz-zaehlt",
        defaults={"wert": str(wert), "einheit": "0 oder 1", "beschreibung": "Test", "quelle": "§ 14 Abs 3"},
    )


def _anna(neben=True, neben_land="oberoesterreich"):
    """Anna wohnt in St. Marienkirchen (Bezirk Eferding) und — wenn gewünscht — daneben in Wels."""
    g1 = Gemeinde.objects.create(kennziffer="40501", name=HAUPT, bezirk="Eferding", bundesland="oberoesterreich")
    anna = mitglied_anlegen("anna")
    anna.wohnsitz = g1
    if neben:
        anna.nebenwohnsitz = Gemeinde.objects.create(
            kennziffer="40301", name=NEBEN, bezirk="Wels(Stadt)", bundesland=neben_land
        )
    anna.save(update_fields=["wohnsitz", "nebenwohnsitz"])
    return anna


def _regionale(ordnung):  # noqa: F811
    autor = mitglied_anlegen("autor", gemeinde="Linz", bundesland="oberoesterreich")
    for titel, ebene, gebiet in (
        ("Radweg Marienkirchen", "gemeinde", HAUPT),
        ("Welser Stadtpark", "gemeinde", NEBEN),
        ("Linzer Hafen", "gemeinde", "Linz"),
        ("Bezirk Eferding: Bus", "bezirk", "Eferding"),
        ("Bezirk Wels: Bahnhof", "bezirk", "Wels(Stadt)"),
        ("Land Salzburg: Seilbahn", "land", "Salzburg"),
    ):
        antrag_einbringen(autor, titel, "W.", "", ordnung, ebene=ebene, gebiet=gebiet)


def _region(client):
    return client.get("/parlament/").content.decode().split('id="feld-region"')[1].split("</section>")[0]


def _band(feld, ebene):
    return feld.split(f'id="rk-{ebene}"')[1].split('class="rband')[0]


# --- Meine Region ------------------------------------------------------------------------


def test_bei_schalter_0_zaehlt_nur_der_wohnsitz(client, ordnung):  # noqa: F811
    """Ohne Registereintrag (Start 0) bleibt alles wie vor S10 — der Nebenwohnsitz ist unsichtbar."""
    anna = _anna()
    _regionale(ordnung)
    client.force_login(anna)
    feld = _region(client)
    assert f'>Gemeinde · {HAUPT}</p>' in feld and NEBEN not in feld.split('id="rk-gemeinde"')[1].split("</p>")[0]
    gemeinde = _band(feld, "gemeinde")
    assert "Radweg Marienkirchen" in gemeinde and "Welser Stadtpark" not in gemeinde and "Linzer Hafen" not in gemeinde
    bezirk = _band(feld, "bezirk")
    assert ">Bezirk · Eferding</p>" in feld and "Bezirk Eferding: Bus" in bezirk and "Bezirk Wels: Bahnhof" not in bezirk
    assert ">Land · Oberösterreich</p>" in feld and "Land Salzburg: Seilbahn" not in feld
    # Bei genau einem Ort schweigt die Kachel über ihren Ort — der Zeilenkopf sagt ihn schon
    assert 'class="rest ort"' not in gemeinde


@pytest.mark.parametrize("wert", ["0", "2", "-1", "x"])
def test_nur_der_wert_1_schaltet_ein(client, ordnung, wert):  # noqa: F811
    _schalter(wert)
    client.force_login(_anna())
    _regionale(ordnung)
    feld = _region(client)
    assert f'>Gemeinde · {HAUPT}</p>' in feld and "Welser Stadtpark" not in feld


def test_bei_schalter_1_kommt_der_nebenwohnsitz_dazu(client, ordnung):  # noqa: F811
    _schalter(1)
    anna = _anna()
    _regionale(ordnung)
    client.force_login(anna)
    feld = _region(client)
    # Zeilenkopf „Gemeinde · Ort1 · Ort2“ — Wohnsitz zuerst, Nebenwohnsitz danach
    assert f">Gemeinde · {HAUPT} · {NEBEN}</p>" in feld
    assert ">Bezirk · Eferding · Wels(Stadt)</p>" in feld
    assert ">Land · Oberösterreich</p>" in feld  # dasselbe Land steht nur einmal
    gemeinde = _band(feld, "gemeinde")
    assert "Radweg Marienkirchen" in gemeinde and "Welser Stadtpark" in gemeinde
    assert "Linzer Hafen" not in gemeinde  # zusätzlich zuordnen heißt nicht: alles zeigen
    assert gemeinde.count('class="rest ort"') == 2  # bei zwei Orten sagt jede Kachel ihren
    bezirk = _band(feld, "bezirk")
    assert "Bezirk Eferding: Bus" in bezirk and "Bezirk Wels: Bahnhof" in bezirk
    assert "Land Salzburg: Seilbahn" not in feld
    assert feld.count('class="rband ') == 3  # weiter drei Bänder, keine vierte Zeile


def test_nebenwohnsitz_in_anderem_bundesland_erweitert_die_landeszeile(client, ordnung):  # noqa: F811
    _schalter(1)
    client.force_login(_anna(neben_land="salzburg"))
    _regionale(ordnung)
    feld = _region(client)
    assert ">Land · Oberösterreich · Salzburg</p>" in feld
    assert "Land Salzburg: Seilbahn" in _band(feld, "land")


def test_schalter_1_ohne_nebenwohnsitz_aendert_nichts(client, ordnung):  # noqa: F811
    _schalter(1)
    client.force_login(_anna(neben=False))
    _regionale(ordnung)
    feld = _region(client)
    assert f">Gemeinde · {HAUPT}</p>" in feld and "Welser Stadtpark" not in feld


def test_gaeste_und_leere_profile_sehen_weiter_alles(client, ordnung):  # noqa: F811
    _schalter(1)
    _regionale(ordnung)
    feld = _region(client)
    assert "Radweg Marienkirchen" in feld and "Welser Stadtpark" in feld and "Linzer Hafen" in feld
    client.force_login(mitglied_anlegen("leer", gemeinde="", bundesland=""))
    antwort = client.get("/parlament/")
    assert antwort.context["region_gefiltert"] is False
    assert "Linzer Hafen" in antwort.content.decode().split('id="feld-region"')[1]
    # Die Leerzeile „Wohnsitz hinterlegen ›“ verlinkt die Profilseite — erst, wenn es sie gibt
    assert "profil_url" in antwort.context
    assert ("Wohnsitz hinterlegen ›" in antwort.content.decode()) is (antwort.context["profil_url"] is not None)


def test_nebenwohnsitz_aendert_nichts_am_stimmrecht(client, ordnung):  # noqa: F811
    """§ 5 Abs 6: keine regionale Stimmberechtigung — mit oder ohne Schalter stimmt Anna über
    einen Antrag aus einer dritten Region genauso ab wie über einen aus ihrer eigenen."""
    anna = _anna()
    leute = [mitglied_anlegen(f"m{i}", gemeinde="Linz") for i in range(2)]
    linz = in_abstimmung_bringen(
        antrag_einbringen(leute[0], "Linzer Hafen", "W.", "", ordnung, ebene="gemeinde", gebiet="Linz"), leute
    )
    for wert in ("0", "1"):
        _schalter(wert)
        assert linz.stimme_zulaessig() and stimme_abgeben(linz, anna, "ja").stimme == "ja"
        client.force_login(anna)
        assert client.post(reverse("verfahren:abstimmen", args=[linz.pk]), {"stimme": "nein"}).status_code == 302
    assert linz.stimmabgaben.count() == 1  # dieselbe Person, dieselbe (geänderte) Stimme


# --- Einbringen ---------------------------------------------------------------------------


def test_einbringen_bietet_nebenwohnsitz_nur_bei_schalter_1(client, ordnung):  # noqa: F811
    anna = _anna()
    client.force_login(anna)
    inhalt = client.get(reverse("verfahren:einbringen")).content.decode()
    assert "Nebenwohnsitz" not in inhalt
    # Wer die Option trotzdem schickt, bekommt das Formular zurück — kein Antrag
    antwort = client.post(reverse("verfahren:einbringen"), {**ANTRAG, "ebene": "gemeinde_neben"})
    assert antwort.status_code == 200 and Antrag.objects.count() == 0

    _schalter(1)
    inhalt = client.get(reverse("verfahren:einbringen")).content.decode()
    assert f"Meine Nebenwohnsitz-Gemeinde ({NEBEN})" in inhalt
    assert "Mein Nebenwohnsitz-Bezirk (Wels(Stadt))" in inhalt
    assert "Mein Nebenwohnsitz-Bundesland (Oberösterreich)" in inhalt
    assert 'value="gemeinde_neben"' in inhalt and 'value="bezirk_neben"' in inhalt and 'value="land_neben"' in inhalt
    assert f"Meine Gemeinde ({HAUPT})" in inhalt and "Mein Bezirk (Eferding)" in inhalt  # der Wohnsitz bleibt


def test_einbringen_ueber_den_nebenwohnsitz_schreibt_ebene_und_gebiet(client, ordnung):  # noqa: F811
    _schalter(1)
    client.force_login(_anna(neben_land="salzburg"))
    for titel, ebene, erwartet_ebene, erwartet_gebiet in (
        ("Eins", "gemeinde_neben", "gemeinde", NEBEN),
        ("Zwei", "bezirk_neben", "bezirk", "Wels(Stadt)"),
        ("Drei", "land_neben", "land", "Salzburg"),
        ("Vier", "gemeinde", "gemeinde", HAUPT),
        ("Fünf", "land", "land", "Oberösterreich"),
    ):
        antwort = client.post(
            reverse("verfahren:einbringen"), {**ANTRAG, "titel": titel, "ebene": ebene, "trotzdem": "1"}
        )
        assert antwort.status_code == 302, titel
        antrag = Antrag.objects.get(titel=titel)
        assert (antrag.ebene, antrag.gebiet) == (erwartet_ebene, erwartet_gebiet), titel
    # Der Antrag kennt nur die Ebene — kein Nebenwohnsitz-Wert landet in der Datenbank
    assert not Antrag.objects.filter(ebene__endswith="_neben").exists()
    # Und er erscheint im eigenen Regionsband unter dem Nebenwohnsitz
    feld = _region(client)
    assert "Eins" in _band(feld, "gemeinde") and "Zwei" in _band(feld, "bezirk") and "Drei" in _band(feld, "land")


def test_einbringen_ohne_nebenwohnsitz_kennt_die_optionen_nicht(client, ordnung):  # noqa: F811
    _schalter(1)
    client.force_login(_anna(neben=False))
    inhalt = client.get(reverse("verfahren:einbringen")).content.decode()
    assert "Nebenwohnsitz" not in inhalt
    antwort = client.post(reverse("verfahren:einbringen"), {**ANTRAG, "ebene": "land_neben"})
    assert antwort.status_code == 200 and Antrag.objects.count() == 0


# --- Abfragen -----------------------------------------------------------------------------


def _abfragen(client):
    with CaptureQueriesContext(connection) as ctx:
        assert client.get("/parlament/").status_code == 200
    return len(ctx.captured_queries)


def test_parlament_fragt_nicht_mehr_als_vorher(client, ordnung):  # noqa: F811
    """Ohne Nebenwohnsitz keine einzige Abfrage mehr — Schalter hin oder her; mit Nebenwohnsitz
    höchstens zwei (Register, Gemeinde), unabhängig von der Zahl der Anträge."""
    _regionale(ordnung)
    anna = _anna(neben=False)
    client.force_login(anna)
    vorher = _abfragen(client)
    _schalter(1)
    assert _abfragen(client) == vorher  # der Schalter wird gar nicht erst gelesen

    anna.nebenwohnsitz = Gemeinde.objects.create(
        kennziffer="40301", name=NEBEN, bezirk="Wels(Stadt)", bundesland="oberoesterreich"
    )
    anna.save(update_fields=["nebenwohnsitz"])
    _schalter(0)
    assert _abfragen(client) <= vorher + 1  # Register lesen, mehr nicht
    _schalter(1)
    wenig = _abfragen(client)
    assert wenig <= vorher + 2  # Register und Nebenwohnsitz
    for i in range(20):
        antrag_einbringen(anna, f"Noch einer {i}", "W.", "", ordnung, ebene="gemeinde", gebiet=NEBEN if i % 2 else HAUPT)
    assert _abfragen(client) == wenig  # unabhängig von der Zahl der Anträge

    client.logout()
    assert _abfragen(client) <= vorher  # Gäste lesen weder Register noch Wohnsitze
