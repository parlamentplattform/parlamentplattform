"""Kennungsnachlese bestätigt keine juristische Deutung und lädt keine Quellen nach."""

import copy
import json
from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils import timezone

from faktenbasis.models import Norm
from faktenbasis.test_volltext import norm  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from gremien.models import Gremium, Rolle
from ki.anbieter import Antwort, AttrappenAnbieter
from ki.kennungsabgleich import fuer_lauf
from ki.models import KILauf, Zweck
from ki.nachlese import antrag_export
from ki.test_kontext_auftrag import a as antragsfall  # noqa: F401
from ki.warteschlange import auftrag_ausfuehren, einreihen
from verfahren.models import Beanstandung
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]


@pytest.fixture
def fall(antragsfall, norm, settings, monkeypatch):  # noqa: F811
    a = antragsfall
    settings.DDOE_KI_ANBIETER = "attrappe"
    a.titel = norm.kurztitel
    a.save(update_fields=["titel"])
    roh = json.dumps({"normen": [{"titel": "Vom Modell behaupteter Titel", "ebene": "Bund", "kennung": norm.ris_id,
        "aenderung": "beruehrt", "begruendung": "Ungeprüfte Modellbegründung"}], "hinweis": "Belege bleiben zu prüfen", "unsicherheit": "hoch"})
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: Antwort(roh, "test-kennung", 10, 20))
    j = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    assert j.quellenkontext["quellen"][0]["norm_id"] == norm.pk
    assert auftrag_ausfuehren(j.pk) == "erledigt"
    j.refresh_from_db()
    return a, norm, j


def kopie(lauf, **aenderung):
    return SimpleNamespace(**{**{f.attname: copy.deepcopy(getattr(lauf, f.attname)) for f in KILauf._meta.concrete_fields}, **aenderung})


def test_tatsaechliche_eingabe_und_quellenidentitaet_ohne_lesezugriff(fall, django_assert_num_queries):
    a, n, j = fall
    lauf = j.lauf
    roh = lauf.antwort
    with django_assert_num_queries(0):
        d = fuer_lauf(lauf)
    assert d["zustand"] == "geprueft" and d["regel_fassung"] == 1
    assert d["zuordnungen"][0]["quelle"]["norm_id"] == n.pk
    assert d["zuordnungen"][0]["quelle"]["kurztitel"] == n.kurztitel
    assert not d["rechtlich_verifiziert"] and lauf.antwort == roh


@pytest.mark.parametrize("art", ["kein_quellenkontext", "kein_textkontext", "hash", "fremder_text", "eingabe", "fremder_prompt", "form", "fehlerlauf"])
def test_kein_link_aus_unsicherem_rahmen_oder_fehlerantwort(fall, art):
    a, n, j = fall
    k = kopie(j.lauf)
    if art == "kein_quellenkontext":
        k.kontext.pop("quellen")
    elif art == "kein_textkontext":
        k.kontext.pop("text")
    elif art == "hash":
        k.kontext["quellen"]["sha256"] = "0"*64
    elif art == "fremder_text":
        k.antrag_id += 1
    elif art == "eingabe":
        k.eingabe = "Die Quelle wurde nie mitgesendet."
    elif art == "fremder_prompt":
        k.auftrag_version = "rechtsbezug-v99"
    elif art == "form":
        k.antwort = '{"normen":[]}'
    else:
        k.erfolgreich = False
    assert fuer_lauf(k)["zuordnungen"] == []


def test_interne_einschaetzung_ist_nicht_oeffentlicher_kennungsabgleich(fall):
    with pytest.raises(ValueError, match="öffentlich"):
        fuer_lauf(kopie(fall[2].lauf, zweck=Zweck.EINSCHAETZUNG))


@pytest.mark.parametrize("kennung", [" NOR12006105", "nor12006105", "https://ris.bka.gv.at/NOR12006105", "NOR99999999"])
def test_rohe_modellkennung_wird_nicht_zum_treffer_normalisiert(fall, kennung):
    k = kopie(fall[2].lauf)
    d = json.loads(k.antwort)
    d["normen"][0]["kennung"] = kennung
    k.antwort = json.dumps(d)
    assert fuer_lauf(k)["zuordnungen"][0]["quelle"] is None


def test_gueltige_pruefsumme_allein_belegt_keine_tatsaechlich_gesendete_quelle(fall):
    from faktenbasis.kontext import _hash

    k = kopie(fall[2].lauf)
    q = k.kontext["quellen"]
    q["text_sha256"] = "0"*64
    q["sha256"] = _hash({x: y for x, y in q.items() if x != "sha256"})
    assert fuer_lauf(k)["zustand"] == "fehler"


def test_spaetere_quelle_aendert_nicht_den_damaligen_link(fall):
    a, n, j = fall
    alt = fuer_lauf(j.lauf)
    daten = copy.deepcopy(n.rohdaten)
    daten["neuer_Stand"] = True
    from faktenbasis.kontext import _hash
    Norm.objects.create(ris_id=n.ris_id, gesetzesnummer=n.gesetzesnummer, kurztitel="Späterer Titel",
        titel="", abschnitt=n.abschnitt, stand=n.stand, quelle=n.quelle, rohdaten=daten,
        inhalt_hash=_hash(daten), importlauf=n.importlauf)
    assert fuer_lauf(j.lauf) == alt


def test_anzeige_linkt_amtlichen_titel_separat_und_exportiert_gleiche_regel(fall, client):
    a, n, j = fall
    html = client.get(reverse("verfahren:antrag", args=[a.pk])).content.decode()
    assert "Kennung im damaligen Quellenstand:" in html and "nicht verifiziert" in html
    assert f'href="{reverse("faktenbasis:norm", args=[n.pk])}"' in html
    assert "rechtliche Betroffenheit und Änderungsbedarf sind damit nicht bestätigt" in html
    daten = antrag_export(a)
    assert daten["laeufe"][0]["kennungsabgleich"] == fuer_lauf(j.lauf)
    assert daten["laeufe"][0]["antwort"] == j.lauf.antwort


def test_korrekturantwort_verwendet_denselben_urspruenglichen_quellenrahmen(fall):
    from ki.korrekturen import anfordern, export, stand

    a, n, j = fall
    m = a.eingebracht_von
    Rolle.objects.create(mitglied=m, gremium=Gremium.EXPERTENRAT_1, antrag=a, bestaetigt=True,
        endet_am=timezone.localdate()+timedelta(days=30))
    b = Beanstandung.objects.create(antrag=a, mitglied=m, lauf=j.lauf, text="Zuordnung ist unbelegt")
    k = anfordern(b, m)
    assert auftrag_ausfuehren(k.pk) == "erledigt"
    k.refresh_from_db()
    assert fuer_lauf(k.lauf)["zuordnungen"][0]["quelle"]["norm_id"] == n.pk
    assert stand(k)["ergebnis"]["normen"][0]["verifiziert"] is False
    assert export(a)[0]["lauf"]["kennungsabgleich"] == fuer_lauf(k.lauf)
    kop = kopie(k.lauf, eingabe="Falscher Korrekturwortlaut")
    assert fuer_lauf(kop)["zustand"] == "fehler"
