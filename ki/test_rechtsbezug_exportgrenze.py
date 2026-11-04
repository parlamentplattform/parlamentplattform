"""Bekannte Altverträge bleiben lesbar, unbekannte Kontextbeifänge bleiben intern."""
# ruff: noqa: F811 -- importierte pytest-Fixture

import copy
import json
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from faktenbasis.kontext import festhalten as quellen_festhalten
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from gremien.models import Gremium, Rolle
from ki.anbieter import Antwort, AttrappenAnbieter
from ki.eingabevertrag import rechtsbezug
from ki.kontext import festhalten
from ki.korrekturen import anfordern, stand
from ki.korrekturen import export as korrektur_export
from ki.models import KIAuftrag, KILauf, Zweck
from ki.nachlese import antrag_export, lauf_export
from ki.rechtsbezug import rechtsbezug_lage
from ki.rechtsbezugvertrag import auftrag_pruefen, lauf_pruefen
from ki.test_kontext import vorschlag
from ki.test_kontext_auftrag import a  # noqa: F401
from ki.test_korrektur_exportgrenze import lauf_kopie, neu_hashen
from ki.test_warteschlange import JSON_ANTWORT
from ki.warteschlange import auftrag_ausfuehren
from mitglieder.profil import daten_export
from verfahren.archiv import als_json, als_markdown
from verfahren.models import AntragsFassung, Beanstandung
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]
PRIVAT = "NUR_SYNTHETISCHER_ZUSATZBEZUG_772"


def altfall_erzeugen(a, quellenfassung, monkeypatch, *, vorschlagsfassung=None):
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: Antwort(JSON_ANTWORT, "lokaler-test", 1, 2))
    text = festhalten(a, vorschlagsfassung=vorschlagsfassung)
    q = quellen_festhalten([], hoechstzahl=3, textzeichen=30, text_sha256=text["sha256"],
                          fassung=quellenfassung) if quellenfassung else {}
    job = KIAuftrag.objects.create(zweck=Zweck.RECHTSBEZUG, antrag=a, angefordert_von=a.eingebracht_von,
        fassung_nummer=1, quellenart=text["quellenart"], vorschlagsfassung=vorschlagsfassung,
        kontext=text, quellenkontext=q)
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    job.refresh_from_db()
    return a, job


@pytest.fixture(params=[0, 1, 2], ids=["rechtsbezug1", "rechtsbezug2", "rechtsbezug3"])
def altfall(a, request, monkeypatch):
    return altfall_erzeugen(a, request.param, monkeypatch)


def test_alle_bekannten_vertraege_bleiben_bytegleich_ohne_heutiges_nachladen(altfall, django_assert_num_queries):
    a, job = altfall
    k = job.lauf
    vorher = KILauf.objects.values().get(pk=k.pk)
    a.titel = "Späterer öffentlicher Titel"
    a.save(update_fields=["titel"])
    AntragsFassung.objects.create(antrag=a, nummer=2, wortlaut="Späterer Wortlaut")
    with django_assert_num_queries(0):
        lauf_pruefen(k)
        auftrag_pruefen(job)
        e = lauf_export(k)
    assert e["eingabe"] == k.eingabe and e["kontext"] == k.kontext
    assert KILauf.objects.values().get(pk=k.pk) == vorher


@pytest.mark.parametrize("fehler", ["wurzel", "text", "quellen", "eingabe", "prompt", "auftragstyp", "versuch", "zeit", "wortlauttyp"])
def test_fremder_lauf_wird_weder_als_antwort_noch_im_archiv_ausgegeben(altfall, fehler, client):
    a, job = altfall
    original = job.lauf
    k = copy.deepcopy(original.kontext)
    if fehler == "wurzel":
        k["intern"] = PRIVAT
    elif fehler == "text":
        k["text"] = neu_hashen({**k["text"], "intern": PRIVAT})
    elif fehler == "quellen":
        k["quellen"] = {**k.get("quellen", {}), "intern": PRIVAT}
    elif fehler == "auftragstyp":
        k["auftrag"] = float(job.pk)
    elif fehler == "versuch":
        k["versuch"] = True
    elif fehler == "zeit":
        k["text"] = neu_hashen({**k["text"], "erfasst_am": "2026-11-04T01:00:00"})
    elif fehler == "wortlauttyp":
        k["text"] = neu_hashen({**k["text"], "wortlaut": {"intern": PRIVAT}})
    fremd = lauf_kopie(original, k)
    # Für abweichende Eingabe/Prompt einen neuen unveränderlichen Datensatz erzeugen.
    if fehler in {"eingabe", "prompt"}:
        d = {f.attname: copy.deepcopy(getattr(original, f.attname)) for f in KILauf._meta.concrete_fields if f.name != "id"}
        d["eingabe" if fehler == "eingabe" else "auftrag_version"] = PRIVAT
        fremd = KILauf.objects.create(**d)
    KIAuftrag.objects.filter(pk=job.pk).update(lauf=fremd)
    assert lauf_export(fremd) == {"id": fremd.pk, "zweck": "rechtsbezug", "kontextstatus": "fehler"}
    assert rechtsbezug_lage(a)["zustand"] == "nicht_pruefbar"
    html = client.get(reverse("verfahren:antrag", args=[a.pk])).content.decode()
    assert "nicht eindeutig an den öffentlichen Auftrag gebunden" in html
    assert PRIVAT not in html + als_json(a) + als_markdown(a)
    response = client.get(reverse("verfahren:archiv_export", kwargs={"pk": a.pk, "art": "md"}))
    assert response.status_code == 200 and PRIVAT not in response.content.decode()
    assert KILauf.objects.get(pk=original.pk).eingabe == original.eingabe
    assert KILauf.objects.get(pk=fremd.pk).kontext == k


@pytest.mark.parametrize("fehler", ["textbeifang", "quellenbeifang", "fremde_fassung", "fremder_antrag"])
def test_wartende_auftraege_geben_keine_ungeprueften_rohfelder_aus(a, fehler):
    text = festhalten(a)
    q = {}
    if fehler == "textbeifang":
        text = neu_hashen({**text, "intern": PRIVAT})
    elif fehler == "quellenbeifang":
        q["intern"] = PRIVAT
    elif fehler == "fremde_fassung":
        text = neu_hashen({**text, "fassung_nummer": 999})
    else:
        text = neu_hashen({**text, "antrag": a.pk + 999})
    job = KIAuftrag.objects.create(antrag=a, zweck=Zweck.RECHTSBEZUG,
        angefordert_von=a.eingebracht_von, fassung_nummer=1, kontext=text, quellenkontext=q)
    vorher = KIAuftrag.objects.values().get(pk=job.pk)
    d = antrag_export(a)
    zeile = next(e for e in d["auftraege"] if e["id"] == job.pk)
    assert zeile["kontextstatus"] == "fehler" and "kontext" not in zeile
    assert PRIVAT not in json.dumps(d)
    assert KIAuftrag.objects.values().get(pk=job.pk) == vorher


def test_unveraenderte_legacy_archive_und_leere_altauftraege_bleiben_erhalten(a):
    alt = KILauf.objects.create(antrag=a, zweck=Zweck.RECHTSBEZUG, angefordert_von=a.eingebracht_von,
        eingabe="Alter öffentlicher Wortlaut", antwort="Alte öffentliche Antwort", anbieter="synthetisch", modell="m")
    job = KIAuftrag.objects.create(antrag=a, angefordert_von=a.eingebracht_von,
        zweck=Zweck.RECHTSBEZUG, fassung_nummer=1, kontext={}, quellenkontext={})
    vorher = KILauf.objects.values().get(pk=alt.pk)
    lauf_pruefen(alt)
    auftrag_pruefen(job)
    e = lauf_export(alt)
    assert e["eingabe"] == alt.eingabe and e["kontext"] == {}
    assert alt.antwort in als_markdown(a)
    assert KILauf.objects.values().get(pk=alt.pk) == vorher


def test_eingereichter_vorschlag_bleibt_nach_spaeterer_fassung_oeffentlich(a, monkeypatch):
    _, job = altfall_erzeugen(a, 2, monkeypatch, vorschlagsfassung=vorschlag(a))
    job.vorschlagsfassung.entwurf.eingereichte_fassung = 999
    job.vorschlagsfassung.entwurf.save(update_fields=["eingereichte_fassung"])
    auftrag_pruefen(job)
    assert lauf_export(job.lauf)["kontext"] == job.lauf.kontext


def test_der_persoenliche_export_bleibt_der_vollstaendige_eigene_export(altfall):
    a, job = altfall
    fremd = lauf_kopie(job.lauf, {**job.lauf.kontext, "intern": PRIVAT})
    assert PRIVAT not in json.dumps(antrag_export(a))
    e = daten_export(a.eingebracht_von)
    assert any(lauf["kontext"].get("intern") == PRIVAT for lauf in e["ki_laeufe"])
    assert KILauf.objects.get(pk=fremd.pk).kontext["intern"] == PRIVAT


def test_eine_neue_korrektur_ist_kein_umweg_um_den_ursprungsfilter(altfall):
    a, job = altfall
    Rolle.objects.create(mitglied=a.eingebracht_von, gremium=Gremium.EXPERTENRAT_1, antrag=a,
                         bestaetigt=True, endet_am=timezone.localdate() + timedelta(days=30))
    fremd = lauf_kopie(job.lauf, {**job.lauf.kontext, "intern": PRIVAT})
    b = Beanstandung.objects.create(antrag=a, lauf=fremd, mitglied=a.eingebracht_von, text="Synthetische Frage")
    with pytest.raises(ValidationError, match="eindeutig festgehaltener öffentlicher Rechtsbezug"):
        anfordern(b, a.eingebracht_von)
    assert not KIAuftrag.objects.filter(beanstandung=b).exists()


def test_leere_bekannte_quellenangabe_ist_kein_unbekannter_beifang(a, monkeypatch):
    _, job = altfall_erzeugen(a, 0, monkeypatch)
    k = {**job.lauf.kontext, "quellen": {}}
    kopie = lauf_kopie(job.lauf, k)
    assert rechtsbezug(k["text"], {})[1] == kopie.eingabe
    assert lauf_export(kopie)["kontext"] == k


def test_auch_eine_bereits_gespeicherte_korrektur_uebernimmt_keinen_fremden_ursprung(altfall):
    a, job = altfall
    Rolle.objects.create(mitglied=a.eingebracht_von, gremium=Gremium.EXPERTENRAT_1, antrag=a,
                         bestaetigt=True, endet_am=timezone.localdate() + timedelta(days=30))
    original_b = Beanstandung.objects.create(antrag=a, lauf=job.lauf, mitglied=a.eingebracht_von,
                                           text="Synthetische ursprüngliche Frage")
    korrektur = anfordern(original_b, a.eingebracht_von)
    fremd = lauf_kopie(job.lauf, {**job.lauf.kontext, "intern": PRIVAT})
    b = Beanstandung.objects.create(antrag=a, lauf=fremd, mitglied=a.eingebracht_von,
                                    text=original_b.text)
    rahmen = copy.deepcopy(korrektur.korrekturkontext)
    rahmen.update(ursprung=fremd.pk, beanstandung={"id": b.pk, "text": b.text, "erstellt_am": b.erstellt_am.isoformat()})
    d = {f.attname: copy.deepcopy(getattr(korrektur, f.attname)) for f in KIAuftrag._meta.concrete_fields if f.name != "id"}
    d.update(ursprung_id=fremd.pk, beanstandung_id=b.pk, korrekturkontext=neu_hashen(rahmen))
    alt = KIAuftrag.objects.create(**d)
    vorher = KIAuftrag.objects.values().get(pk=alt.pk)
    assert stand(alt) == {"zustand": "fehler"}
    assert next(e for e in korrektur_export(a) if e["auftrag"] == alt.pk) == {"auftrag": alt.pk, "zustand": "fehler"}
    assert KIAuftrag.objects.values().get(pk=alt.pk) == vorher


@pytest.mark.parametrize("kontext", [None, [], {"intern": PRIVAT}])
def test_falsche_legacyform_wird_nicht_als_leerer_altkontext_umgedeutet(a, kontext):
    lauf = KILauf(antrag=a, zweck=Zweck.RECHTSBEZUG, kontext=kontext,
                  eingabe=PRIVAT, antwort=PRIVAT)
    assert lauf_export(lauf) == {"id": None, "zweck": "rechtsbezug", "kontextstatus": "fehler"}


@pytest.mark.parametrize("prompt", ["rechtsbezug-v2", "rechtsbezug-v3", "unbekannter-prompt"])
def test_neuere_prompts_ohne_ihre_quellen_sind_keine_kontextlosen_altarchive(a, prompt):
    lauf = KILauf(antrag=a, zweck=Zweck.RECHTSBEZUG, kontext={}, auftrag_version=prompt,
                  eingabe=PRIVAT, antwort=PRIVAT)
    assert lauf_export(lauf) == {"id": None, "zweck": "rechtsbezug", "kontextstatus": "fehler"}
