"""Eigener eingefrorener Folgenauftrag; keine automatische Aktivierung oder echten Kosten."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

import copy
import json

import pytest
from django.core.exceptions import ValidationError
from django.db import transaction

from faktenbasis.test_personalrahmen import daten as personaldaten
from gremien.models import Entwurf
from ki import folgenkontext
from ki.anbieter import AnbieterFehler, Antwort, AttrappenAnbieter
from ki.folgenauftraege import antwort_pruefen, rahmen_pruefen
from ki.models import Auftragsstatus, KIAuftrag, KILauf, Zweck
from ki.test_kontext import antrag, vorschlag  # noqa: F401
from ki.warteschlange import abarbeiten, auftrag_ausfuehren, einreihen, heute_gestartet
from parameter.models import Parameter
from verfahren.models import AntragsFassung
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db
ANTWORT = json.dumps({"normen": [], "judikatur": {"text": "Ohne vollständigen Rechtsbestand offen."},
    "exekutive": {"text": "Zuständigkeit und Vollzugsbedarf sind offen."},
    "personal": [{"bereich": "unbestimmt", "beamte_delta_min": None, "beamte_delta_max": None,
                  "vb_delta_min": None, "vb_delta_max": None, "grund": "Bestände belegen keinen Stellenbedarf."}],
    "unsicherheit": "hoch", "quellen": []})


def neu(antrag, **kw):
    return einreihen(Zweck.RECHTSFOLGEN, antrag, antrag.eingebracht_von, hoechstzeichen=50000, **kw)


@pytest.fixture
def attrappe(settings, monkeypatch):
    settings.DDOE_KI_ANBIETER = "attrappe"
    aufrufe = []

    def frage(self, prompt, eingabe):
        aufrufe.append((prompt, eingabe))
        return Antwort(ANTWORT, "folgen-test", 10, 20)

    monkeypatch.setattr(AttrappenAnbieter, "frage", frage)
    return aufrufe


def test_neue_factory_wird_noch_nicht_durch_einbringen_oder_alten_zweck_aktiviert(antrag):
    assert not KIAuftrag.objects.filter(zweck=Zweck.RECHTSFOLGEN).exists()
    alt = einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    assert not alt.folgenkontext
    assert not KIAuftrag.objects.filter(zweck=Zweck.RECHTSFOLGEN).exists()
    with pytest.raises(ValueError, match="ausdrücklichen"):
        einreihen(Zweck.RECHTSFOLGEN, antrag, antrag.eingebracht_von)


def test_einmalige_factory_laesst_alten_auftrag_und_fehlen_spaeterer_belege_unveraendert(antrag, monkeypatch):
    alt = einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    altstand = copy.deepcopy((alt.kontext, alt.quellenkontext))
    job = neu(antrag)
    vorher = copy.deepcopy(job.folgenkontext)
    personaldaten()
    monkeypatch.setattr(folgenkontext, "mit_grundlagen", lambda *a, **k: pytest.fail("Kein erneuter Faktencapture"))
    nochmals = neu(antrag)
    assert nochmals.pk == job.pk and nochmals.folgenkontext == vorher
    assert vorher["personal"]["zustand"] == "leer"
    alt.refresh_from_db()
    assert (alt.kontext, alt.quellenkontext) == altstand and not alt.folgenkontext
    AntragsFassung.objects.create(antrag=antrag, nummer=2, wortlaut="Zweite öffentliche Fassung")
    # Die neue Fassung muss eine eigene Identität erhalten; Erfassungsfehler bleibt ehrlich.
    monkeypatch.setattr(folgenkontext, "mit_grundlagen", lambda *a, **k: (_ for _ in ()).throw(ValueError("Test")))
    j2 = neu(antrag)
    assert j2.pk != job.pk and j2.fassung_nummer == 2 and j2.status == Auftragsstatus.GESCHEITERT


def test_vorschlag_bleibt_idempotent_und_interner_entwurf_ist_keine_neue_quelle(antrag):
    v = vorschlag(antrag)
    job = neu(antrag, vorschlagsfassung=v)
    Entwurf.objects.filter(pk=v.entwurf_id).update(eingereichte_fassung=None)
    assert neu(antrag, vorschlagsfassung=v).pk == job.pk
    # Andere Antragsidentität darf den historischen öffentlichen Auftrag nicht übernehmen.
    fremd = copy.copy(antrag)
    fremd.pk = 999999
    with pytest.raises(ValueError):
        neu(fremd, vorschlagsfassung=v)


@pytest.mark.parametrize("weg", ["save", "update", "bulk_update", "upsert"])
def test_folgenrahmen_ist_ueber_alle_ueblichen_schreibwege_fest(antrag, weg):
    job = neu(antrag)
    vorher = copy.deepcopy(job.folgenkontext)
    job.folgenkontext = {}
    with pytest.raises(ValidationError):
        if weg == "save":
            job.save(update_fields=["folgenkontext"])
        elif weg == "update":
            KIAuftrag.objects.filter(pk=job.pk).update(folgenkontext={})
        elif weg == "bulk_update":
            KIAuftrag.objects.bulk_update([job], ["folgenkontext"])
        else:
            KIAuftrag.objects.bulk_create([job], update_conflicts=True, update_fields=["folgenkontext"], unique_fields=["pk"])
    job.refresh_from_db()
    assert job.folgenkontext == vorher


@pytest.mark.parametrize("art", ["mandat", "vertrauensfrage"])
def test_personenfragen_und_interne_vorschlaege_sind_ausgeschlossen(antrag, art):
    antrag.art = art
    antrag.save(update_fields=["art"])
    with pytest.raises(ValueError):
        neu(antrag)


def test_interne_vorschlagsfassung_wird_ohne_auftrag_abgewiesen(antrag):
    v = vorschlag(antrag)
    Entwurf.objects.filter(pk=v.entwurf_id).update(eingereichte_fassung=None)
    with pytest.raises(ValueError):
        neu(antrag, vorschlagsfassung=v)
    assert not KIAuftrag.objects.filter(zweck=Zweck.RECHTSFOLGEN).exists()


def test_worker_verwendet_exakte_alte_grundlagen_einmal_ueber_den_steckplatz(antrag, attrappe, monkeypatch):
    job = neu(antrag)
    erwartet = folgenkontext.eingabe(job.folgenkontext)
    personaldaten()
    antrag.titel = "Späterer Titel ist nicht die Modelleingabe"
    antrag.save(update_fields=["titel"])
    monkeypatch.setattr(folgenkontext, "mit_grundlagen", lambda *a, **k: pytest.fail("Kein Nachladen"))
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    job.refresh_from_db()
    lauf = job.lauf
    assert len(attrappe) == 1 and attrappe[0][1] == erwartet == lauf.eingabe
    assert lauf.auftrag_version == "rechtsfolgen-v1" and lauf.kontext["folgen"] == job.folgenkontext
    assert lauf.kontext["auftrag"] == job.pk and lauf.kontext["versuch"] == 1
    assert antwort_pruefen(lauf)["gueltig"] and not antwort_pruefen(lauf)["inhaltlich_geprueft"]
    assert KILauf.monatsverbrauch() == 30 and heute_gestartet() == 1
    assert auftrag_ausfuehren(job.pk) == "uebersprungen" and len(attrappe) == 1
    assert not job.antrag.ki_auftraege.filter(zweck=Zweck.KORREKTUR).exists()


def test_falsche_form_bleibt_archiviert_ohne_teilfreigabe_oder_automatische_neurechnung(antrag, attrappe, monkeypatch):
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *a: Antwort('{"normen":[]}', "test", 3, 2))
    job = neu(antrag)
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    job.refresh_from_db()
    r = antwort_pruefen(job.lauf)
    assert not r["gueltig"] and r["daten"] is None and job.lauf.antwort == '{"normen":[]}'
    assert auftrag_ausfuehren(job.pk) == "uebersprungen"


@pytest.mark.parametrize("feld", ["zweck", "antrag_id", "quellenart", "fassung_nummer", "kontext", "quellenkontext", "vorschlagsfassung_id"])
def test_worker_erkennt_fremde_auftragsteile_vor_modellstart(antrag, attrappe, feld):
    job = neu(antrag)
    setattr(job, feld, {"fremd": True} if feld.endswith("kontext") else 9999)
    with pytest.raises(ValueError):
        rahmen_pruefen(job)
    assert not attrappe and not KILauf.objects.exists()


@pytest.mark.parametrize("feld", ["eingabe", "auftrag_version", "antrag_id", "zweck", "kontext", "erfolgreich"])
def test_fremder_lauf_wird_nicht_als_gepruefter_folgenbericht_angenommen(antrag, attrappe, feld):
    job = neu(antrag)
    auftrag_ausfuehren(job.pk)
    job.refresh_from_db()
    k = job.lauf
    setattr(k, feld, {} if feld == "kontext" else False if feld == "erfolgreich" else 9999)
    with pytest.raises(ValueError):
        antwort_pruefen(k)


def test_erfassungsfehler_vergiftet_kein_verfahren_und_wird_nicht_als_leere_quelle_verwendet(antrag, attrappe, monkeypatch):
    def kaputt(*a, **k):
        KILauf.objects.raw("SELECT * FROM tabelle_die_es_nicht_gibt").__iter__().__next__()
    monkeypatch.setattr(folgenkontext, "mit_grundlagen", kaputt)
    with transaction.atomic():
        job = neu(antrag)
        assert KIAuftrag.objects.filter(pk=job.pk).exists()
    assert job.status == Auftragsstatus.GESCHEITERT and job.fehler == "folgenkontext_erfassung"
    assert not job.folgenkontext and job.kontext["antrag"] == antrag.pk
    assert auftrag_ausfuehren(job.pk) == "uebersprungen" and not attrappe


def test_zu_langer_vollstaendiger_input_wird_nicht_gekuerzt_oder_gerechnet(antrag, attrappe):
    job = einreihen(Zweck.RECHTSFOLGEN, antrag, antrag.eingebracht_von, hoechstzeichen=1)
    assert job.status == Auftragsstatus.GESCHEITERT and job.kontext["wortlaut"]
    assert not job.folgenkontext and not attrappe


def test_monats_und_tagesgrenze_gelten_gemeinsam_ohne_zusaetzliche_versuche(antrag, attrappe):
    job = neu(antrag)
    Parameter.objects.update_or_create(schluessel="ki-tageslaeufe", defaults={"wert": "0"})
    assert abarbeiten()["kontingent_erschoepft"]
    Parameter.objects.filter(schluessel="ki-tageslaeufe").update(wert="20")
    Parameter.objects.update_or_create(schluessel="ki-monatstokens", defaults={"wert": "0"})
    assert abarbeiten()["budget_erschoepft"]
    job.refresh_from_db()
    assert not attrappe and job.versuche == 0 and job.status == Auftragsstatus.GEPLANT


def test_anbieterfehler_bleibt_im_eigenen_archiv_und_zaehlt_im_tagesrahmen(antrag, attrappe, monkeypatch):
    def fehler(*a, **k):
        raise AnbieterFehler("Testfehler")
    monkeypatch.setattr(AttrappenAnbieter, "frage", fehler)
    job = neu(antrag)
    assert auftrag_ausfuehren(job.pk) == "verschoben"
    job.refresh_from_db()
    assert job.lauf and not job.lauf.erfolgreich and job.lauf.kontext["folgen"] == job.folgenkontext
    assert heute_gestartet() == 1 and job.naechster_versuch and job.versuche == 1


def test_eigener_export_enthaelt_nur_eigene_folgenauftragsdaten(antrag):
    from mitglieder.profil import daten_export

    job = neu(antrag)
    m = mitglied_anlegen("anderer-export")
    fremd = KIAuftrag.objects.create(zweck=Zweck.RECHTSBEZUG, antrag=antrag, angefordert_von=m, kontext={})
    d = daten_export(antrag.eingebracht_von)
    assert d["ki_auftraege"][0]["folgenkontext"] == job.folgenkontext
    assert len(d["ki_auftraege"]) == 1
    assert daten_export(m)["ki_auftraege"][0]["zweck"] == fremd.zweck
