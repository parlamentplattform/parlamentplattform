"""Eindeutige gespeicherte Quellen; noch keine automatische Beauftragung."""

import copy
import json

import pytest
from django.utils import translation

from gremien.models import Entwurf, EntwurfsFassung
from ki.kontext import eingabe, festhalten, pruefen
from verfahren.models import AntragsFassung, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def antrag(ordnung):  # noqa: F811
    m = mitglied_anlegen("kontext")
    return antrag_einbringen(m, ANTRAG["titel"], ANTRAG["wortlaut"], "Erster Grund", ordnung)


def vorschlag(antrag):
    entwurf, _ = Entwurf.objects.get_or_create(antrag=antrag)
    fassung = EntwurfsFassung.objects.create(
        entwurf=entwurf, nummer=1, wortlaut="Wortlaut des Expertenrats",
        begruendung="Begründung des Vorschlags", verfasst_von=antrag.eingebracht_von,
    )
    entwurf.eingereichte_fassung = fassung.nummer
    entwurf.save(update_fields=["eingereichte_fassung"])
    return fassung


def test_gleichlautende_nummern_bleiben_unterschiedliche_quellen(antrag):
    original = festhalten(antrag, fassung_nummer=1)
    v = festhalten(antrag, vorschlagsfassung=vorschlag(antrag))
    assert original["fassung_nummer"] == v["fassung_nummer"] == 1
    assert original["quellenart"] == "antrag" and v["quellenart"] == "vorschlag"
    assert original["sha256"] != v["sha256"]
    assert "Textquelle: Antrag, Fassung 1" in eingabe(original)
    assert "Textquelle: Vorschlag des Expertenrats, Fassung 1" in eingabe(v)
    assert "Wortlaut des Expertenrats" not in eingabe(original)


def test_inhalt_bleibt_nach_titel_und_neuer_fassung_stabil(antrag, django_assert_num_queries):
    alt = json.loads(json.dumps(festhalten(antrag, fassung_nummer=1)))
    vorher = eingabe(alt)
    antrag.titel = "Später geänderter Titel"
    antrag.save(update_fields=["titel"])
    AntragsFassung.objects.create(antrag=antrag, nummer=2, wortlaut="Zweiter Wortlaut")
    with django_assert_num_queries(0):
        assert eingabe(alt) == vorher
    neu = festhalten(antrag)
    assert neu["fassung_nummer"] == 2 and neu["titel"] == antrag.titel
    assert neu["wortlaut"] == "Zweiter Wortlaut"
    assert "Später geänderter Titel" not in vorher


def test_fehlende_fassung_weicht_nie_auf_neueren_text_aus(antrag):
    with pytest.raises(ValueError, match="fehlt"):
        festhalten(antrag, fassung_nummer=9999)


def test_fremder_vorschlag_und_gemischte_quellen_werden_abgewiesen(antrag, ordnung):  # noqa: F811
    fremd = antrag_einbringen(mitglied_anlegen("anderer"), "Anderer Antrag", ANTRAG["wortlaut"], "", ordnung)
    fassung = vorschlag(fremd)
    with pytest.raises(ValueError, match="gehört nicht"):
        festhalten(antrag, vorschlagsfassung=fassung)
    with pytest.raises(ValueError, match="Nur eine"):
        festhalten(antrag, vorschlagsfassung=fassung, fassung_nummer=1)


def test_pruefsumme_erkennt_aenderungen_und_der_kontext_enthaelt_keine_kontodaten(antrag):
    original = festhalten(antrag)
    daten = pruefen(original)
    assert "sha256" not in daten and "sha256" in original
    assert not {"mitglied", "email", "username", "adresse", "sperrcode"} & set(daten)
    kaputt = copy.deepcopy(original)
    kaputt["wortlaut"] += " Änderung"
    with pytest.raises(ValueError, match="Prüfsumme"):
        eingabe(kaputt)


@pytest.mark.parametrize("kaputt", [None, {}, {"version": 1, "quellenart": "antrag", "sha256": "ä"}])
def test_fehlender_oder_ungueltiger_kontext_wird_nicht_als_eingabe_genutzt(kaputt):
    with pytest.raises(ValueError):
        eingabe(kaputt)


def test_deutsche_eingabe_bleibt_unabhaengig_von_der_oberflaechensprache(antrag):
    with translation.override("en"):
        d = festhalten(antrag)
        assert translation.get_language() == "en"
    assert "Ebene: Bund" in eingabe(d)
