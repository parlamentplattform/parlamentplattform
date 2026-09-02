"""P2 — der Favoriten-Fächer (F-46, FB-C1–C4): Layout-Mathematik (Regel v2) und Einbau im Parlament.
Die Abnahme über den echten Kategorienbaum (312 Anker, keine Überlappung) liegt in tests/test_faecher_layout.py."""

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
    assert lage["version"] == 2 and lage["modus"] == "boden"
    (anker,) = [k for k in lage["knoten"] if k["rolle"] == "anker"]
    assert anker["slug"] == "wurzel" and anker["groesse"] == 24
    kinder = [k for k in lage["knoten"] if k["rolle"] == "kind"]
    assert {k["slug"] for k in kinder} == {"umwelt", "bildung"}
    assert all(k["groesse"] == 22 and k["y"] < anker["y"] for k in kinder)  # 2-Punkt-Schritt, darüber
    enkel = [k for k in lage["knoten"] if k["rolle"] == "enkel"]
    assert {k["slug"] for k in enkel} == {"energie", "wasser", "schule"}
    assert all(k["groesse"] == 20 for k in enkel)
    urenkel = [k for k in lage["knoten"] if k["rolle"] == "urenkel"]
    assert {k["slug"] for k in urenkel} == {"solar", "wind"} and all(k["groesse"] == 18 for k in urenkel)
    assert all(0 <= k["x_prozent"] <= 100 and 0 <= k["y_prozent"] <= 100 for k in lage["knoten"])
    assert len(lage["faeden"]) == len(lage["knoten"]) - 1, "jeder Knoten hängt an seiner Überkategorie"
    assert lage["aeste"] == [] and lage["ast_standard"] == ""  # alles passt vollständig hinein


def test_ab_der_dritten_ebene_sitzt_der_anker_in_der_mitte():
    lage = faecher_layout(BAUM, "energie")  # Tiefe 3
    assert lage["modus"] == "mitte"
    (anker,) = [k for k in lage["knoten"] if k["rolle"] == "anker"]
    weg = [k for k in lage["knoten"] if k["rolle"] == "weg"]
    assert [k["slug"] for k in weg] == ["umwelt", "wurzel"]  # Weg zurück nach oben, vollständig
    assert all(k["y"] > anker["y"] for k in weg)  # liegt unter dem Anker
    kinder = [k for k in lage["knoten"] if k["rolle"] == "kind"]
    assert {k["slug"] for k in kinder} == {"solar", "wind"}
    assert all(k["y"] < anker["y"] for k in kinder)  # Unterebenen öffnen sich darüber
    assert [b["slug"] for b in lage["brotkrume"]] == ["wurzel", "umwelt", "energie"]


def test_zweite_ebene_bleibt_am_boden():
    assert faecher_layout(BAUM, "umwelt")["modus"] == "boden"


def test_zu_grosse_ebene_wird_nur_im_entfalteten_ast_gezeigt():
    """FB-C3: über zwölf Knoten wird eine Ebene nur für den entfalteten Ast gezeichnet —
    drei Kinder nebeneinander, ab dem vierten „+n"; alle Äste sind vorab gerechnet."""
    breit = _zeilen(
        (1, "w", None),
        *[(10 + i, f"k{i}", 1) for i in range(4)],
        *[(100 + i, f"e{i}", 10 + (i % 4)) for i in range(16)],  # 16 Enkel > 12
    )
    lage = faecher_layout(breit)
    assert [a["slug"] for a in lage["aeste"]] == ["k0", "k1", "k2", "k3"]
    assert lage["ast_standard"] == "k0"
    enkel = [k for k in lage["knoten"] if k["rolle"] == "enkel"]
    assert len(enkel) == 12 and all(k["ast"] for k in enkel)  # je Ast drei von vier Kindern
    sichtbar = [k for k in enkel if k["sichtbar"]]
    assert {k["ast"] for k in sichtbar} == {"k0"} and len(sichtbar) == 3
    assert [k["mehr"] for k in sichtbar] == [0, 0, 1]  # das vierte Kind steht als +1
    assert all(k["eltern"] == "k0" for k in sichtbar)
    lage = faecher_layout(breit, abos={"e2"})  # e2 hängt an k2 → dessen Ast ist im Ruhezustand offen
    assert lage["ast_standard"] == "k2"
    assert [k["abonniert"] for k in lage["knoten"] if k["slug"] == "e2"] == [True]


def test_unbekannter_fokus_faellt_auf_die_wurzel():
    assert faecher_layout(BAUM, "gibts-nicht")["fokus"]["slug"] == "wurzel"
    assert faecher_layout([], "x")["knoten"] == []


def test_pillen_kennen_hoechstbreite_und_kurznamen():
    zeilen = _zeilen((1, "nutztiere-und-landwirtschaftliche-tierhaltung-und-mehr", None), (2, "a", 1), (3, "b", 1))
    lage = faecher_layout(zeilen)
    assert all(0 < k["breite_prozent"] <= 92 for k in lage["knoten"])
    (anker,) = [k for k in lage["knoten"] if k["rolle"] == "anker"]
    assert anker["kurz"].endswith("…") and len(anker["kurz"]) < len(anker["name"])


# --- Einbau im Parlament ----------------------------------------------------------


def _kategorien():
    w = Kategorie.objects.create(slug="leben", name="Leben")
    u = Kategorie.objects.create(slug="umwelt", name="Umwelt", eltern=w)
    e = Kategorie.objects.create(slug="energie", name="Energie", eltern=u)
    s = Kategorie.objects.create(slug="solar", name="Solarstrom", eltern=e)
    return w, u, e, s


def _breiter_baum():
    w = Kategorie.objects.create(slug="leben", name="Leben")
    kinder = [Kategorie.objects.create(slug=f"k{i}", name=f"Kind {i}", eltern=w, reihenfolge=i) for i in range(3)]
    for i in range(15):  # 15 Enkel > 12: die dritte Ebene erscheint nur im entfalteten Ast
        Kategorie.objects.create(slug=f"e{i}", name=f"Enkel {i}", eltern=kinder[i % 3], reihenfolge=i)
    return w, kinder


def test_faecher_im_parlament_auch_fuer_gaeste(client):
    _kategorien()
    inhalt = client.get("/parlament/?fach=").content.decode()
    assert 'class="faecher"' in inhalt and "Leben" in inhalt
    assert 'href="?fach=umwelt#feld-favoriten"' in inhalt  # echte Links, kein JavaScript nötig
    assert "abonnieren/" not in inhalt  # Gäste sehen keine Stern-Formulare …
    assert 'class="stern aus gast"' in inhalt  # … aber den Stern als Weg zur Anmeldung (FB-C4)
    assert 'class="parlament"' in inhalt  # die übrigen Felder bleiben
    assert 'class="fknoten kind f22 p1"' in inhalt  # Säulenfarbe der ersten Säule
    assert 'class="brot"' not in inhalt  # an der Wurzel keine Brotkrume


def test_ruhe_ast_ohne_javascript_und_alle_aeste_vorab(client):
    w, kinder = _breiter_baum()
    inhalt = client.get("/parlament/").content.decode()
    assert 'data-ast="k0"' in inhalt and 'data-ast="k2"' in inhalt  # alle Äste im HTML
    assert 'data-ast="k0" x-show="ast === \'k0\'" x-cloak' not in inhalt  # Ruhe-Ast sichtbar
    assert 'data-ast="k1" x-show="ast === \'k1\'" x-cloak' in inhalt  # andere Äste versteckt
    assert "x-data=\"faecher('k0')\"" in inhalt
    assert 'href="?fach=k0#feld-favoriten"' in inhalt and ">+2<" in inhalt  # drei Kinder + „+2"


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
    assert "&#9733;" in inhalt and 'aria-pressed="true"' in inhalt  # der Anker trägt jetzt den vollen Stern


def test_mit_htmx_wechselt_nur_der_stern(client):
    """FB-C4: kein Feldtausch, keine Flash-Meldung — die Antwort ist der Stern selbst."""
    w, u, e, s = _kategorien()
    anna = mitglied_anlegen()
    client.force_login(anna)
    antwort = client.post(
        reverse("verfahren:kategorie_abonnieren", args=["energie"]),
        {"weiter": "/parlament/?fach=energie"},
        HTTP_HX_REQUEST="true",
    )
    assert antwort.status_code == 200
    inhalt = antwort.content.decode()
    assert inhalt.lstrip().startswith("<form") and 'aria-pressed="true"' in inhalt and "&#9733;" in inhalt
    assert 'id="feld-favoriten"' not in inhalt and "ist jetzt Favorit" not in inhalt
    assert anna.kategorie_abos.filter(kategorie=e).exists()
    antwort = client.post(reverse("verfahren:kategorie_abonnieren", args=["energie"]), HTTP_HX_REQUEST="true")
    assert 'aria-pressed="false"' in antwort.content.decode()
    assert not anna.kategorie_abos.filter(kategorie=e).exists()
    seite = client.get("/parlament/").content.decode()
    assert "Favorit „Energie“ entfernt" not in seite  # keine nachträgliche Flash-Meldung


def test_brotkrume_ab_der_zweiten_ebene(client):
    _kategorien()
    feld = client.get("/parlament/?fach=energie").content.decode().split('id="feld-favoriten"')[1].split("</section>")[0]
    assert 'class="brot"' in feld and "<b>Energie</b>" in feld
    assert 'href="?fach=leben#feld-favoriten"' in feld and 'href="?fach=umwelt#feld-favoriten"' in feld
    assert 'class="faecher mitte"' in feld  # Tiefe 3: Anker in der Mitte, Rückweg darunter
    assert 'class="fknoten weg' in feld


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
    assert 'class="treffer-link"' in feld  # der Treffer öffnet den Fächer und hebt den Anker hervor
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
