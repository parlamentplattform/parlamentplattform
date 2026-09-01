"""P2 — der Favoriten-Fächer (F-46): Layout-Mathematik und Einbau im Parlament."""

import pytest
from django.urls import reverse

from plattform_core.faecher import faecher_layout
from verfahren.models import Kategorie
from verfahren.test_views_aktionen import mitglied_anlegen  # noqa: F401

pytestmark = pytest.mark.django_db


def _zeilen(*tripel):
    return [{"id": i, "slug": s, "name": s.replace("-", " ").title(), "eltern_id": e} for i, s, e in tripel]


BAUM = _zeilen(
    (1, "wurzel", None),
    (2, "umwelt", 1),
    (3, "bildung", 1),
    (4, "energie", 2),
    (5, "wasser", 2),
    (6, "schule", 3),
    (7, "solar", 4),
    (8, "wind", 4),
)


# --- Layout (rein, ohne Datenbank) ------------------------------------------------


def test_wurzelfaecher_steht_am_boden():
    lage = faecher_layout(BAUM)
    assert lage["modus"] == "boden"
    (anker,) = [k for k in lage["knoten"] if k["rolle"] == "anker"]
    assert anker["slug"] == "wurzel" and anker["groesse"] == 24
    kinder = [k for k in lage["knoten"] if k["rolle"] == "kind"]
    assert {k["slug"] for k in kinder} == {"umwelt", "bildung"}
    assert all(k["groesse"] == 22 and k["y"] < anker["y"] for k in kinder)  # 2-Punkt-Schritt, darüber
    enkel = [k for k in lage["knoten"] if k["rolle"] == "enkel"]
    assert {k["slug"] for k in enkel} == {"energie", "wasser", "schule"}
    assert all(k["groesse"] == 20 for k in enkel)
    assert all(0 <= k["x"] <= 1000 and 0 <= k["y"] <= lage["hoehe"] for k in lage["knoten"])
    assert lage["faeden"], "Fäden verbinden die Ebenen"


def test_ab_der_dritten_ebene_sitzt_der_anker_in_der_mitte():
    lage = faecher_layout(BAUM, "energie")  # Tiefe 3
    assert lage["modus"] == "mitte"
    (anker,) = [k for k in lage["knoten"] if k["rolle"] == "anker"]
    weg = [k for k in lage["knoten"] if k["rolle"] == "weg"]
    assert [k["slug"] for k in weg] == ["umwelt", "wurzel"]  # Weg zurück nach oben
    assert all(k["y"] > anker["y"] for k in weg)  # liegt unter dem Anker
    kinder = [k for k in lage["knoten"] if k["rolle"] == "kind"]
    assert {k["slug"] for k in kinder} == {"solar", "wind"}
    assert all(k["y"] < anker["y"] for k in kinder)  # Unterebenen öffnen sich darüber


def test_zweite_ebene_bleibt_am_boden():
    assert faecher_layout(BAUM, "umwelt")["modus"] == "boden"


def test_zu_viele_enkel_werden_zur_zahl():
    breit = _zeilen(
        (1, "w", None),
        *[(10 + i, f"k{i}", 1) for i in range(4)],
        *[(100 + i, f"e{i}", 10 + (i % 4)) for i in range(16)],
    )
    lage = faecher_layout(breit)
    assert not [k for k in lage["knoten"] if k["rolle"] == "enkel"]
    assert sum(k["mehr"] for k in lage["knoten"] if k["rolle"] == "kind") == 16


def test_unbekannter_fokus_faellt_auf_die_wurzel():
    assert faecher_layout(BAUM, "gibts-nicht")["fokus"]["slug"] == "wurzel"
    assert faecher_layout([], "x")["knoten"] == []


def test_lange_namen_werden_gekuerzt():
    zeilen = _zeilen((1, "nutztiere-und-landwirtschaftliche-tierhaltung", None))
    (anker,) = faecher_layout(zeilen)["knoten"]
    assert anker["kurz"].endswith("…") and len(anker["kurz"]) <= 30


# --- Einbau im Parlament ----------------------------------------------------------


def _kategorien():
    w = Kategorie.objects.create(slug="leben", name="Leben")
    u = Kategorie.objects.create(slug="umwelt", name="Umwelt", eltern=w)
    e = Kategorie.objects.create(slug="energie", name="Energie", eltern=u)
    s = Kategorie.objects.create(slug="solar", name="Solarstrom", eltern=e)
    return w, u, e, s


def test_faecher_im_parlament_auch_fuer_gaeste(client):
    _kategorien()
    inhalt = client.get("/parlament/?fach=").content.decode()
    assert 'class="faecher"' in inhalt and "Leben" in inhalt
    assert 'href="?fach=umwelt#feld-favoriten"' in inhalt  # echte Links, kein JavaScript nötig
    assert "abonnieren" not in inhalt  # Gäste sehen keine Stern-Formulare
    assert 'class="parlament"' in inhalt  # die übrigen Felder bleiben


def test_stern_im_faecher_schaltet_das_abo(client):
    w, u, e, s = _kategorien()
    anna = mitglied_anlegen()
    client.force_login(anna)
    inhalt = client.get("/parlament/?fach=energie").content.decode()
    assert "abonnieren" in inhalt and "&#9734;" in inhalt  # leere Sterne an den Knoten
    antwort = client.post(
        reverse("verfahren:kategorie_abonnieren", args=["energie"]),
        {"weiter": "/parlament/?fach=energie"},
    )
    assert antwort.url == "/parlament/?fach=energie"
    assert anna.kategorie_abos.filter(kategorie=e).exists()
    inhalt = client.get("/parlament/?fach=energie").content.decode()
    assert "&#9733;" in inhalt  # der Anker trägt jetzt den vollen Stern


def test_faecher_erscheint_direkt_mit_suche_im_kopf(client):
    """Vorgabe 1.9. abends: kein Liste/Fächer-Umschalter mehr — der Fächer
    ist das Feld, oben sitzt die Suche als Tiefen-Ansicht."""
    _kategorien()
    inhalt = client.get("/parlament/").content.decode()
    assert 'class="faecher"' in inhalt  # direkt sichtbar, ohne ?fach=
    feld = inhalt.split('id="feld-favoriten"')[1].split("</section>")[0]
    assert 'name="suche"' in feld  # die Suche im Feldkopf
    assert "Fächer entdecken" not in inhalt and "Tiefen-Ansicht" not in inhalt


def test_feldsuche_findet_und_verlinkt_in_den_faecher(client):
    w, u, e, s = _kategorien()
    anna = mitglied_anlegen()
    client.force_login(anna)
    feld = (
        client.get("/parlament/?suche=solar").content.decode()
        .split('id="feld-favoriten"')[1].split("</section>")[0]
    )
    assert "Solarstrom" in feld and 'href="?fach=solar#feld-favoriten"' in feld
    assert "abonnieren" in feld  # der Stern direkt am Treffer
    assert "Zurück zum Fächer" in feld
    leer = (
        client.get("/parlament/?suche=zzz-gibts-nicht").content.decode()
        .split('id="feld-favoriten"')[1].split("</section>")[0]
    )
    assert "Nichts gefunden" in leer


def test_alte_lebensbereiche_adressen_landen_im_faecher(client):
    _kategorien()
    antwort = client.get("/kategorien/")
    assert antwort.status_code == 302 and antwort.url.endswith("#feld-favoriten")
    antwort = client.get("/kategorien/energie/")
    assert antwort.url.endswith("?fach=energie#feld-favoriten")
