"""Heutige Nachlese liest gebündelt und lässt damalige Kontexte vollständig unverändert."""

import copy
import json
from datetime import timedelta

import pytest
from django.utils import timezone

from faktenbasis import importieren as metadaten
from faktenbasis import volltext
from faktenbasis.kontext import festhalten
from faktenbasis.models import Norm, NormText, RisImport
from faktenbasis.nachlese import abgleichen
from faktenbasis.ris import antwort_parsen
from faktenbasis.test_ris import NUMMER, STAND, beispiel
from faktenbasis.test_volltext import norm, xml  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from ki.models import KILauf, Zweck
from ki.nachlese import antrag_export
from ki.rechtsbezug import rechtsbezug_lage
from ki.test_kontext_auftrag import a  # noqa: F401
from ki.warteschlange import auftrag_ausfuehren, einreihen
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]


def weiterer_stand(basis, **werte):
    felder = {f.attname: getattr(basis, f.attname) for f in Norm._meta.concrete_fields if not f.primary_key}
    stand = werte.get("stand", basis.stand + timedelta(days=1))
    vorher = basis.importlauf
    importfelder = {f.attname: getattr(vorher, f.attname) for f in RisImport._meta.concrete_fields if not f.primary_key}
    importlauf = RisImport.objects.create(**{**importfelder, "stand": stand,
                                             "begonnen_am": timezone.now(), "beendet_am": timezone.now()})
    return Norm.objects.create(**{**felder, "stand": stand, "importlauf_id": importlauf.pk, **werte})


def test_unveraenderter_bestand_liest_zweimal_und_schreibt_nichts(norm, django_assert_num_queries):  # noqa: F811
    rahmen = festhalten([norm.pk], hoechstzahl=3, textzeichen=50)
    vorher, anzahl = copy.deepcopy(rahmen), AuditEintrag.objects.count()
    with django_assert_num_queries(2):
        ergebnis = abgleichen(rahmen)
    assert ergebnis["zustand"] == "verglichen" and ergebnis["vollstaendig_vergleichbar"]
    assert not ergebnis["spaetere_staende"] and rahmen == vorher
    assert AuditEintrag.objects.count() == anzahl


def test_mehrere_quellen_bleiben_zwei_gebuendelte_abfragen(norm, monkeypatch, django_assert_num_queries):  # noqa: F811
    daten = beispiel()
    ergebnisse = daten["OgdSearchResult"]["OgdDocumentResults"]
    ergebnisse["Hits"]["#text"] = "3"
    ergebnisse["OgdDocumentReference"] = [
        {"Data": json.loads(json.dumps(norm.rohdaten).replace(norm.ris_id, f"NOR8800000{i}"))}
        for i in range(1, 4)
    ]
    monkeypatch.setattr(metadaten, "abrufen", lambda *args: antwort_parsen(daten, NUMMER))
    metadaten.importieren(NUMMER, STAND)
    ids = list(Norm.objects.filter(ris_id__startswith="NOR88").values_list("pk", flat=True))
    rahmen = festhalten(ids, hoechstzahl=3, textzeichen=50)
    with django_assert_num_queries(2):
        ergebnis = abgleichen(rahmen)
    assert len(ergebnis["quellen"]) == 3 and ergebnis["vollstaendig_vergleichbar"]
    assert [q["kennung"] for q in ergebnis["gegenuebergestellte_quellen"]] == sorted(q["kennung"] for q in ergebnis["quellen"])


def test_spaeterer_text_bleibt_sichtbar_obwohl_weitere_metadaten_existieren(norm, xml):  # noqa: F811
    weiterer_stand(norm)  # Schon vor der Aufnahme vorhanden; die gewählte historische Quelle bleibt ausdrücklich alt.
    rahmen = festhalten([norm.pk], hoechstzahl=3, textzeichen=50)
    lauf = volltext.importieren(norm)  # Text zum ursprünglichen Metadatenstand, nicht zum anderen.
    ergebnis = abgleichen(rahmen)
    b, = ergebnis["quellen"]
    assert not b["metadaten_spaeter"] and b["dokument_spaeter"]
    assert b["spaeterer_text"] == lauf.inhalt_id and rahmen["quellen"][0]["dokumenttext"] is None
    angaben, = ergebnis["gegenuebergestellte_quellen"]
    assert angaben["text_norm_id"] == norm.pk and angaben["text_parser"] == 1
    assert angaben["text_hash"] == lauf.inhalt.xml_hash and angaben["text_erfasst"]


def test_neuer_stichtag_nach_aufnahme_ist_keine_nachtraegliche_modelleingabe(norm):  # noqa: F811
    rahmen = festhalten([norm.pk], hoechstzahl=3, textzeichen=50)
    neu = weiterer_stand(norm)
    b, = abgleichen(rahmen)["quellen"]
    assert b["metadaten_spaeter"] and b["gegenuebergestellt"] == neu.pk
    assert rahmen["quellen"][0]["norm_id"] == norm.pk and rahmen["sha256"]


def test_aelterer_historischer_import_und_fremde_norm_sind_keine_spaetere_quelle(norm):  # noqa: F811
    rahmen = festhalten([norm.pk], hoechstzahl=3, textzeichen=50)
    weiterer_stand(norm, stand=norm.stand - timedelta(days=1))
    weiterer_stand(norm, ris_id="NOR00000099")
    assert not abgleichen(rahmen)["spaetere_staende"]


def test_alter_leerer_oder_kaputter_rahmen_braucht_keinen_datenbankabgleich(django_assert_num_queries):
    leer = festhalten([], hoechstzahl=3, textzeichen=50)
    kaputt = {**leer, "sha256": "f" * 64}
    with django_assert_num_queries(0):
        assert abgleichen({})["zustand"] == "alt"
        assert abgleichen(leer)["zustand"] == "leer"
        assert abgleichen(kaputt)["zustand"] == "fehler"
        assert abgleichen(leer, text_sha256="f" * 64)["zustand"] == "fehler"


def test_unterschiedliche_parserverarbeitung_zum_selben_xml_wird_erkannt(norm, xml):  # noqa: F811
    original = volltext.importieren(norm).inhalt
    rahmen = festhalten([norm.pk], hoechstzahl=3, textzeichen=50)
    neu = NormText.objects.create(norm=norm, quelle=original.quelle, xml=original.xml, text="Andere Aufbereitung",
                                  xml_hash=original.xml_hash, parser_fassung=2)
    b, = abgleichen(rahmen)["quellen"]
    assert b["dokument_spaeter"] and b["spaeterer_text"] == neu.pk


def test_kuenftig_erfasster_text_wird_nicht_vorzeitig_gezeigt(norm, xml):  # noqa: F811
    rahmen = festhalten([norm.pk], hoechstzahl=3, textzeichen=50)
    zeit = timezone.now()
    NormText.objects.create(norm=norm, quelle="https://ris.bka.gv.at/", xml=b"Test",
                            text="Zukünftige Testdaten", xml_hash="a" * 64, erfasst_am=zeit + timedelta(days=1))
    assert not abgleichen(rahmen, jetzt=zeit)["spaetere_staende"]


def test_anzeige_und_export_nennen_denselben_rahmen_originale_bleiben_gleich(a, norm, xml, client):  # noqa: F811
    a.titel = norm.kurztitel
    a.save(update_fields=["titel"])
    job = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    job.refresh_from_db()
    vorher = copy.deepcopy(job.lauf.kontext)
    volltext.importieren(norm)
    lage, export = rechtsbezug_lage(a), antrag_export(a)
    assert lage["quellenabgleich"]["quellen"] == export["quellenabgleich"]["quellen"]
    assert export["quellenabgleich"]["ausgangs_sha256"] == job.quellenkontext["sha256"]
    assert export["quellenabgleich"]["lauf"] == job.lauf_id
    assert export["quellenabgleich"]["gegenuebergestellte_quellen"][0]["text_parser"] == 1
    assert export["laeufe"][0]["kontext"] == vorher
    assert KILauf.objects.get(pk=job.lauf_id).kontext == vorher
    html = client.get(f"/antrag/{a.pk}/").content.decode()
    assert "Spätere lokale Quellenstände" in html and "Späterer Dokumenttextstand" in html
    assert "dieser Vergleich löst keinen Modelllauf aus" in html
