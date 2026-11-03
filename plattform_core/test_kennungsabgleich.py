import copy

import pytest

from plattform_core.kennungsabgleich import VERSION, abgleichen

Q = {"norm_id": 17, "ris_id": "NOR12006105", "kurztitel": "Amtlicher Testtitel", "abschnitt": "Art. 1", "stand": "2026-11-03"}
N = {"kennung": Q["ris_id"], "titel": "Ungeprüfter Modelltitel", "ebene": "Bund", "aenderung": "beruehrt"}


def test_nur_exakte_kennung_keine_titelbestaetigung_und_keine_mutation():
    n, q = copy.deepcopy(N), copy.deepcopy(Q)
    r, = abgleichen([n], [q])
    assert VERSION == 2 and r["zustand"] == "gleich" and r["quelle"] == Q
    assert r["rechtlich_verifiziert"] is False and n == N and q == Q
    r["quelle"]["kurztitel"] = "Nachträglich anders"
    assert q == Q


@pytest.mark.parametrize("kennung", ["", "nor12006105", "NOR120061050", "NOR12006105/", " NOR12006105", "NOR１２006105", "https://example.org/NOR12006105", "BGBl. I Nr. 1/2000", None])
def test_keine_heuristik_oder_teilkennung(kennung):
    r, = abgleichen([{**N, "kennung": kennung}], [Q])
    assert r["zustand"] == "keine" and r["quelle"] is None


@pytest.mark.parametrize("ebene,aenderung", [("EU", "beruehrt"), ("Land", "beruehrt"), ("Bund", "neu"), ("Bund", "falsch")])
def test_nicht_auf_andere_ebene_oder_neues_recht_uebertragen(ebene, aenderung):
    assert abgleichen([{**N, "ebene": ebene, "aenderung": aenderung}], [Q])[0]["quelle"] is None


def test_mehrdeutige_standsammlung_waehlt_nicht_still_eine_quelle():
    assert abgleichen([N], [Q, {**Q, "norm_id": 18}])[0]["zustand"] == "mehrdeutig"
    r = abgleichen([N, {**N, "kennung": "NOR99999999"}], [])
    assert [x["position"] for x in r] == [0, 1] and all(x["quelle"] is None for x in r)


@pytest.mark.parametrize("normen,quellen", [(None, []), ([N]*9, []), ([], None), ([], [Q]*21), ([None], [])])
def test_form_und_technische_grenzen(normen, quellen):
    with pytest.raises(ValueError):
        abgleichen(normen, quellen)


@pytest.mark.parametrize("feld,wert", [("ris_id", None), ("ris_id", "falsch"), ("norm_id", True), ("norm_id", 0), ("kurztitel", ""), ("kurztitel", None), ("abschnitt", None), ("abschnitt", "x"*101), ("stand", None), ("stand", "20261103"), ("stand", "kaputt")])
def test_beschaedigte_quelle_wird_nicht_tolerant_aufgeloest(feld, wert):
    with pytest.raises(ValueError):
        abgleichen([N], [{**Q, feld: wert}])


def test_quellenmuessen_objekte_sein():
    with pytest.raises(ValueError):
        abgleichen([], [None])


def test_landeskennung_braucht_ausdrueckliche_herkunft_ohne_geografische_deutung():
    q = {**Q, "ris_id": "LOO00000001", "ebene": "Land", "bundesland": "Oberösterreich"}
    n = {**N, "kennung": q["ris_id"], "ebene": "Land"}
    r, = abgleichen([n], [q])
    assert r["quelle"] == q and not r["rechtlich_verifiziert"]
    assert abgleichen([{**n, "ebene": "Bund"}], [q])[0]["quelle"] is None
    assert abgleichen([{**n, "aenderung": "neu"}], [q])[0]["quelle"] is None
    # Unterschiedliche damalige Herkunft ist mehrdeutig, keine stille Auswahl nach Antragstitel.
    assert abgleichen([n], [q, {**q, "bundesland": "Wien", "norm_id": 18}])[0]["zustand"] == "mehrdeutig"


@pytest.mark.parametrize("felder", [
    {"ebene": "Land"}, {"bundesland": "Oberösterreich"},
    {"ebene": "Land", "bundesland": ""}, {"ebene": "Land", "bundesland": "Oberoesterreich"},
    {"ebene": "Bund", "bundesland": "Oberösterreich"}, {"ebene": None, "bundesland": "Wien"},
])
def test_fehlerhafte_ausdrueckliche_herkunft_bekommt_keinen_bund_standard(felder):
    with pytest.raises(ValueError):
        abgleichen([N], [{**Q, **felder}])
