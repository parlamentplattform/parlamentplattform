"""Der vorbereitete Folgeninput enthält nur den damals festgehaltenen öffentlichen Stand."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

import copy
import json

import pytest

from faktenbasis.test_personalrahmen import daten as personaldaten
from gremien.models import Entwurf
from ki.folgenkontext import antwortangebot, eingabe, festhalten, pruefen
from ki.kontext import _hash
from ki.models import KIAuftrag, KILauf
from ki.test_kontext import antrag, vorschlag  # noqa: F401
from verfahren.models import AntragsFassung, AuditEintrag
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def neu_hashen(r):
    r.pop("sha256", None)
    return {**r, "sha256": _hash(r)}


def test_oeffentlicher_text_und_personal_werden_getrennt_mit_einmaligem_zeitpunkt_gebunden(antrag):
    personaldaten()
    jobs, audit = KIAuftrag.objects.count(), AuditEintrag.objects.count()
    r = festhalten(antrag, hoechstzeichen=50000)
    d = json.loads(eingabe(r))
    assert r["auftrag_version"] == "rechtsfolgen-v1"
    assert r["text"]["sha256"] == r["quellen"]["text_sha256"] == r["personal"]["text_sha256"]
    assert r["text"]["erfasst_am"] == r["personal"]["erfasst_am"] == r["erfasst_am"]
    assert "Textquelle: Antrag" in d["oeffentlicher_text"]
    assert d["personal_bestandsgrundlage"]["aggregat"]["gesamt"] == 138100
    assert len(d["angebotene_quellen"]) == 2 and len(d["angebotene_personalbereiche"]) == 15
    assert antwortangebot(r)["quellen"] == d["angebotene_quellen"]
    assert KIAuftrag.objects.count() == jobs and AuditEintrag.objects.count() == audit and not KILauf.objects.exists()
    assert antrag.eingebracht_von.email not in eingabe(r)


def test_historischer_input_bleibt_ohne_aktuelle_lesezugriffe_gleich(antrag, django_assert_num_queries):
    r = festhalten(antrag, hoechstzeichen=50000)
    alt = eingabe(r)
    antrag.titel = "Später geänderter öffentlicher Titel"
    antrag.save(update_fields=["titel"])
    AntragsFassung.objects.create(antrag=antrag, nummer=2, wortlaut="Späterer Text")
    personaldaten()
    with django_assert_num_queries(0):
        assert eingabe(r) == alt and antwortangebot(r) == {"quellen": [], "personalbereiche": []}
    neu = festhalten(antrag, hoechstzeichen=50000)
    assert neu["text"]["fassung_nummer"] == 2 and neu["personal"]["zustand"] == "vorhanden"
    assert r["personal"]["zustand"] == "leer"


def test_interner_vorschlag_wird_nicht_als_oeffentliche_folgenquelle_angefordert(antrag):
    v = vorschlag(antrag)
    Entwurf.objects.filter(pk=v.entwurf_id).update(eingereichte_fassung=None)
    with pytest.raises(ValueError, match="öffentliche Vorschlagsfassung"):
        festhalten(antrag, hoechstzeichen=50000, vorschlagsfassung=v)
    assert not KILauf.objects.exists()


def test_eingereichte_vorschlagsfassung_bleibt_getrennt_von_antrag1(antrag):
    v = vorschlag(antrag)
    r = festhalten(antrag, hoechstzeichen=50000, vorschlagsfassung=v)
    assert r["text"]["quellenart"] == "vorschlag"
    assert r["text"]["fassung_id"] == v.pk
    assert "Textquelle: Vorschlag des Expertenrats, Fassung 1" in json.loads(eingabe(r))["oeffentlicher_text"]


@pytest.mark.parametrize("art", ["mandat", "vertrauensfrage"])
def test_ueber_personen_entsteht_kein_folgenkontext(antrag, art):
    antrag.art = art
    antrag.save(update_fields=["art"])
    with pytest.raises(ValueError, match="Sachfrage"):
        festhalten(antrag, hoechstzeichen=50000)


def test_kleiner_rahmen_kuerzt_weder_text_noch_quellen(antrag):
    with pytest.raises(ValueError, match="nicht gekürzt"):
        festhalten(antrag, hoechstzeichen=1)
    assert not KILauf.objects.exists()


@pytest.mark.parametrize("teil", ["text", "quellen", "personal", "eingabe_sha256", "auftrag_version", "hoechstzeichen"])
def test_austausch_eines_teils_zerstoert_die_gesamtbindung(antrag, teil):
    r = festhalten(antrag, hoechstzeichen=50000)
    r[teil] = None
    with pytest.raises(ValueError):
        eingabe(r)


def test_neu_gehashter_anderer_personal_textbezug_wird_abgewiesen(antrag):
    r = festhalten(antrag, hoechstzeichen=50000)
    p = copy.deepcopy(r["personal"])
    p["text_sha256"] = "b" * 64
    r["personal"] = neu_hashen(p)
    with pytest.raises(ValueError):
        pruefen(neu_hashen(r))


def test_kein_kontometadatenfeld_im_neu_gehashten_textstand(antrag):
    r = festhalten(antrag, hoechstzeichen=50000)
    t = copy.deepcopy(r["text"])
    t["email"] = "nicht-uebertragen@example.org"
    r["text"] = neu_hashen(t)
    with pytest.raises(ValueError):
        eingabe(neu_hashen(r))


@pytest.mark.parametrize("feld,wert", [("quellenart", []), ("version", True), ("titel", 123)])
def test_beschaedigter_untervertrag_wird_nicht_als_input_weitergegeben(antrag, feld, wert):
    r = festhalten(antrag, hoechstzeichen=50000)
    t = copy.deepcopy(r["text"])
    t[feld] = wert
    r["text"] = neu_hashen(t)
    with pytest.raises(ValueError):
        eingabe(neu_hashen(r))
