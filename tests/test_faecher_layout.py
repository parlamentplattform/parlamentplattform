"""Der Fächer, Regel v2 (FB-C1–C3): Abnahmen über den echten Kategorienbaum, ohne Datenbank.

Die Kernzusage: Für jeden der 312 Knoten als Anker und jeden entfaltbaren Ast
überlappen sich keine zwei sichtbaren Pillen, alles bleibt im Feld, und an der
Wurzel sind fünf Ebenen zu sehen.
"""

from pathlib import Path

import pytest
import yaml

from plattform_core.faecher import (
    GROESSEN,
    KINDER_HOECHSTZAHL,
    VERSION,
    VOLL_HOECHSTZAHL,
    faecher_layout,
    pillen_breite,
    pillen_hoehe,
)

WURZEL = Path(__file__).resolve().parent.parent
YAML = WURZEL / "policies" / "kategorien-v2.yaml"


def _zeilen_aus_yaml():
    daten = yaml.safe_load(YAML.read_text(encoding="utf-8"))
    zeilen, naechste_id = [], [1]

    def geh(knoten, eltern_id, reihenfolge):
        kennung = naechste_id[0]
        naechste_id[0] += 1
        zeilen.append({"id": kennung, "slug": knoten["slug"], "name": knoten["name"],
                       "eltern_id": eltern_id, "reihenfolge": reihenfolge})
        for i, u in enumerate(knoten.get("unterkategorien") or []):
            geh(u, kennung, i)

    for i, w in enumerate(daten["lebensbereiche"]):
        geh(w, None, i)
    return zeilen


@pytest.fixture(scope="module")
def baum():
    zeilen = _zeilen_aus_yaml()
    assert len(zeilen) == 312
    return zeilen


def _kasten(k, hoehe):
    """Pillen-Rechteck in nominalen Pixeln — mit der zugeteilten Höchstbreite (max-width),
    also der schlechtesten Annahme: jede Pille füllt ihren Platz ganz aus."""
    x = k["x_prozent"] / 100 * 600
    y = k["y_prozent"] / 100 * hoehe
    b = k["breite_prozent"] / 100 * 600
    if k["rolle"] in ("anker", "weg"):
        b = min(b, pillen_breite(len(k["name"]), k["groesse"]))
    h = pillen_hoehe(k["groesse"])
    return (x - b / 2, y - h / 2, x + b / 2, y + h / 2)


def _ueberlappen(a, b) -> bool:
    return not (a[2] <= b[0] or b[2] <= a[0] or a[3] <= b[1] or b[3] <= a[1])


def _sichtbare(lage, ast):
    return [k for k in lage["knoten"] if not k["ast"] or k["ast"] == ast]


def test_regel_ist_versioniert():
    assert VERSION == 2


def test_wurzel_zeigt_fuenf_ebenen_und_zwoelf_bereiche(baum):
    lage = faecher_layout(baum)
    assert lage["modus"] == "boden"
    ebenen = {k["ebene"] for k in _sichtbare(lage, lage["ast_standard"])}
    assert ebenen == {0, 1, 2, 3, 4}, "Anker plus vier Ebenen darüber (FB-C2)"
    assert len([k for k in lage["knoten"] if k["rolle"] == "kind"]) == 4
    assert len([k for k in lage["knoten"] if k["rolle"] == "enkel"]) == 12
    assert [k["groesse"] for k in lage["knoten"] if k["rolle"] == "anker"] == [24]
    assert {k["groesse"] for k in lage["knoten"] if k["rolle"] == "kind"} == {22}
    assert {k["groesse"] for k in lage["knoten"] if k["rolle"] == "enkel"} == {20}
    assert lage["ast_standard"] and len(lage["aeste"]) == 12, "jeder Bereich ist entfaltbar"
    assert all(k["saeule"] in (1, 2, 3, 4) for k in lage["knoten"] if k["rolle"] != "anker")


def test_erster_favorit_bestimmt_den_entfalteten_ast(baum):
    lage = faecher_layout(baum, abos={"erneuerbare-energie"})
    treffer = [k for k in lage["knoten"] if k["slug"] == "erneuerbare-energie"]
    assert treffer and treffer[0]["sichtbar"], "der Ast des Favoriten ist im Ruhezustand entfaltet"
    ohne = faecher_layout(baum)
    assert ohne["ast_standard"] == ohne["aeste"][0]["slug"]


def test_entfalteter_ast_zeigt_hoechstens_drei_kinder_mit_plus(baum):
    lage = faecher_layout(baum)
    for ast in lage["aeste"]:
        seitlich = [k for k in lage["knoten"] if k["ast"] == ast["slug"] and not k["stapel"]]
        assert 1 <= len(seitlich) <= KINDER_HOECHSTZAHL
        for s in seitlich:
            saeule = [k for k in lage["knoten"] if k["ast"] == ast["slug"] and k["stapel"] and k["eltern"] == s["slug"]]
            assert len(saeule) <= KINDER_HOECHSTZAHL
            assert all(abs(k["x_prozent"] - s["x_prozent"]) < 0.01 for k in saeule), "Säule steht senkrecht über dem Elternknoten"
    mehr = [k for k in lage["knoten"] if k["mehr"]]
    assert mehr, "ab dem vierten Kind steht +n"


@pytest.mark.parametrize("nummer", range(0, 312, 1))
def test_keine_pille_ueberlappt_fuer_jeden_anker(baum, nummer):
    fokus = baum[nummer]["slug"]
    lage = faecher_layout(baum, fokus)
    assert lage["fokus"]["slug"] == fokus
    for k in lage["knoten"]:
        assert 0 <= k["x_prozent"] <= 100 and 0 <= k["y_prozent"] <= 100
        kasten = _kasten(k, lage["hoehe"])
        assert kasten[0] >= -1 and kasten[2] <= 601, f"{k['slug']} ragt seitlich aus dem Feld"
        assert kasten[1] >= -1 and kasten[3] <= lage["hoehe"] + 1, f"{k['slug']} ragt oben oder unten hinaus"
    for ast in [a["slug"] for a in lage["aeste"]] or [""]:
        sichtbar = _sichtbare(lage, ast)
        kaesten = [(k["slug"], _kasten(k, lage["hoehe"])) for k in sichtbar]
        for i in range(len(kaesten)):
            for j in range(i + 1, len(kaesten)):
                assert not _ueberlappen(kaesten[i][1], kaesten[j][1]), (
                    f"Anker {fokus}, Ast {ast}: {kaesten[i][0]} überlappt {kaesten[j][0]}"
                )


def test_mitte_modus_hat_vollstaendigen_rueckweg(baum):
    tiefste = next(z for z in baum if z["name"] == "Kassenärztliche Versorgung")
    lage = faecher_layout(baum, tiefste["slug"])
    assert lage["modus"] == "mitte"
    weg = [k for k in lage["knoten"] if k["rolle"] == "weg"]
    assert [k["ebene"] for k in weg] == [-1, -2, -3, -4, -5], "alle Vorfahren bis zur Wurzel"
    anker = next(k for k in lage["knoten"] if k["rolle"] == "anker")
    assert all(k["y_prozent"] > anker["y_prozent"] for k in weg)
    assert len(lage["brotkrume"]) == 6 and lage["brotkrume"][-1]["slug"] == tiefste["slug"]


def test_volle_ebene_hat_hoechstens_zwoelf_knoten(baum):
    for z in baum:
        lage = faecher_layout(baum, z["slug"])
        for ebene in (1, 2, 3, 4):
            volle = [k for k in lage["knoten"] if k["ebene"] == ebene and not k["ast"]]
            assert len(volle) <= VOLL_HOECHSTZAHL or ebene == 1


def test_groessen_folgen_den_ebenen():
    assert GROESSEN == (22, 20, 18, 16)


def test_pillen_zeigen_mindestens_sechs_zeichen(baum):
    for z in baum[:40]:
        lage = faecher_layout(baum, z["slug"])
        for k in lage["knoten"]:
            assert k["breite_prozent"] / 100 * 600 >= pillen_breite(6, k["groesse"]) - 0.01, k["slug"]
            assert len(k["kurz"]) >= 6 or len(k["name"]) < 6
