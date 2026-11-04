"""Quellenstand ist ein unveränderter Ausschnitt, keine rechtliche Antragszuordnung."""

import copy
import hashlib
import json
from datetime import UTC, datetime, timedelta

import pytest
from django.utils import timezone

from faktenbasis import importieren as meta
from faktenbasis import volltext
from faktenbasis.kontext import QuellenkontextFehler, eingabe, festhalten, pruefen
from faktenbasis.models import Norm, NormText
from faktenbasis.ris import antwort_parsen
from faktenbasis.test_ris import NUMMER, STAND, beispiel
from faktenbasis.test_volltext import norm, xml  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from verfahren.models import AuditEintrag

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]


def test_metadaten_ohne_dokumenttext_werden_nicht_zum_volltext(norm):  # noqa: F811
    stand = festhalten([norm.pk], hoechstzahl=3, textzeichen=80)
    q, = stand["quellen"]
    assert q["norm_id"] == norm.pk and q["ris_id"] == norm.ris_id
    assert q["metadaten_sha256"] == norm.inhalt_hash and q["dokumenttext"] is None
    assert pruefen(stand)["quellen"] == stand["quellen"]
    assert "rohdaten" not in q and "verifiziert" not in q


def test_gekürzter_wortlaut_traegt_originalbezug_und_hash_des_tatsaechlichen_ausschnitts(norm, xml):  # noqa: F811
    volltext.importieren(norm)
    original = NormText.objects.get()
    auditanzahl = AuditEintrag.objects.count()
    daten = festhalten([norm.pk], hoechstzahl=3, textzeichen=40)
    d = daten["quellen"][0]["dokumenttext"]
    assert d["id"] == original.pk and d["xml_sha256"] == original.xml_hash
    assert d["auszug"] == original.text[:40] and d["gekuerzt"] is True
    assert d["zeichen_gesamt"] == len(original.text)
    assert d["auszug_sha256"] == hashlib.sha256(d["auszug"].encode()).hexdigest()
    assert AuditEintrag.objects.count() == auditanzahl and NormText.objects.count() == 1


def test_null_textzeichen_sind_ausdruecklich_nur_metadaten(norm, xml):  # noqa: F811
    volltext.importieren(norm)
    d = festhalten([norm.pk], hoechstzahl=1, textzeichen=0)["quellen"][0]["dokumenttext"]
    assert d["auszug"] == "" and d["gekuerzt"]
    assert d["zeichen_gesamt"] > 0


def test_spaeterer_dokumenttext_ersetzt_keinen_festgehaltenen_stand(norm, xml):  # noqa: F811
    volltext.importieren(norm)
    jetzt = timezone.now()
    gespeichert = festhalten([norm.pk], hoechstzahl=3, textzeichen=200, jetzt=jetzt)
    unveraendert = copy.deepcopy(gespeichert)
    xml[0] = xml[0].replace(b'ct="text" halign="c">', b'ct="text" halign="c">Testaenderung ', 1)
    volltext.importieren(norm)
    assert pruefen(gespeichert) == pruefen(unveraendert)
    assert festhalten([norm.pk], hoechstzahl=3, textzeichen=200, jetzt=jetzt) == gespeichert
    neu = festhalten([norm.pk], hoechstzahl=3, textzeichen=200)
    assert neu["quellen"][0]["dokumenttext"]["id"] != gespeichert["quellen"][0]["dokumenttext"]["id"]


def test_leere_neue_erfassung_ist_nicht_ein_angeblich_alter_quellennachweis():
    stand = festhalten([], hoechstzahl=3, textzeichen=50)
    assert stand["quellen"] == [] and stand["version"] == 2 and stand["erfasst_am"]
    with pytest.raises(QuellenkontextFehler):
        pruefen({})


def test_ungueltige_oder_fremde_auswahl_wird_nicht_ersetzt(norm):  # noqa: F811
    for ids in ([norm.pk, norm.pk], [norm.pk + 99], [True], [-1], ["1"]):
        with pytest.raises(QuellenkontextFehler):
            festhalten(ids, hoechstzahl=3, textzeichen=50)
    with pytest.raises(QuellenkontextFehler):
        festhalten([norm.pk], hoechstzahl=0, textzeichen=50)
    with pytest.raises(QuellenkontextFehler):
        festhalten([norm.pk], hoechstzahl=3, textzeichen=50, jetzt=norm.importlauf.begonnen_am - timedelta(seconds=1))


@pytest.mark.parametrize("zahl", [-1, True, 1.5, "5", 20001])
def test_technisch_ungueltige_textgrenze_wird_abgewiesen(zahl):
    with pytest.raises(QuellenkontextFehler):
        festhalten([], hoechstzahl=3, textzeichen=zahl)


def test_nachtraegliche_aenderung_ist_keine_gueltige_quellenherkunft(norm):  # noqa: F811
    gespeichert = festhalten([norm.pk], hoechstzahl=3, textzeichen=50)
    gespeichert["quellen"][0]["kurztitel"] = "Anderer Text"
    with pytest.raises(QuellenkontextFehler):
        pruefen(gespeichert)


def test_pruefen_laedt_keine_neueren_quellen_nach(norm, django_assert_num_queries):  # noqa: F811
    gespeichert = festhalten([norm.pk], hoechstzahl=3, textzeichen=50)
    with django_assert_num_queries(0):
        kopie = pruefen(gespeichert)
    kopie["quellen"][0]["kurztitel"] = "Nur die Rückgabekopie"
    assert gespeichert["quellen"][0]["kurztitel"] == norm.kurztitel


def test_leseaufwand_waechst_nicht_pro_quelle_und_eingabereihenfolge_ist_keine_reihung(
    norm, monkeypatch, django_assert_num_queries,  # noqa: F811
):
    daten = beispiel()
    ergebnisse = daten["OgdSearchResult"]["OgdDocumentResults"]
    ergebnisse["Hits"]["#text"] = "8"
    ergebnisse["OgdDocumentReference"] = [
        {"Data": json.loads(json.dumps(norm.rohdaten).replace(norm.ris_id, f"NOR120061{i:02d}"))}
        for i in range(5, 13)
    ]
    monkeypatch.setattr(meta, "abrufen", lambda *args: antwort_parsen(daten, NUMMER))
    meta.importieren(NUMMER, STAND)
    ids = list(Norm.objects.values_list("pk", flat=True))
    assert len(ids) == 8
    jetzt = timezone.now()
    with django_assert_num_queries(2):
        stand = festhalten(ids, hoechstzahl=10, textzeichen=50, jetzt=jetzt)
    assert [q["ris_id"] for q in stand["quellen"]] == sorted(q["ris_id"] for q in stand["quellen"])
    assert festhalten(ids[::-1], hoechstzahl=10, textzeichen=50, jetzt=jetzt) == stand


def test_fremde_tiefe_struktur_wird_ohne_rekursion_als_quellenfehler_behandelt():
    stand = festhalten([], hoechstzahl=3, textzeichen=50)
    fremd = []
    for _ in range(2000):
        fremd = [fremd]
    stand["quellen"] = [fremd]
    with pytest.raises(QuellenkontextFehler, match="quellenkontext"):
        pruefen(stand)


def test_quellenstichtag_folgt_instanzkalender_statt_aktiver_betrachterzeitzone(settings):
    settings.TIME_ZONE = "Europe/Vienna"
    with timezone.override("America/Los_Angeles"):
        stand = festhalten([], hoechstzahl=3, textzeichen=50, jetzt=datetime(2026, 11, 2, 23, 30, tzinfo=UTC))
    assert stand["stichtag"] == "2026-11-03" and stand["erfasst_am"].startswith("2026-11-02T23:30:")


def test_jsonb_schluesselreihenfolge_aendert_die_tatsaechliche_anbietereingabe_nicht(norm):  # noqa: F811
    original = festhalten([norm.pk], hoechstzahl=3, textzeichen=50)
    # PostgreSQL JSONB kann Objektschlüssel anders ausgeben als die Erfassung;
    # ein Wiederholungsaufruf muss trotzdem dieselbe Zeichenfolge übergeben.
    anders_geordnet = json.loads(json.dumps(original, sort_keys=True, ensure_ascii=False))
    assert original == anders_geordnet
    assert eingabe(original) == eingabe(anders_geordnet)
