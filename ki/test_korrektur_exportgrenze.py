"""Öffentliche Altverträge dürfen weder Zusatzfelder noch fremde Versuche ausgeben."""
# ruff: noqa: F811 -- importierte pytest-Fixture

import copy
import json
from datetime import timedelta

import pytest
from django.utils import timezone

from faktenbasis.kontext import festhalten as quellen_festhalten
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from gremien.models import Gremium, Rolle
from ki.anbieter import Antwort, AttrappenAnbieter
from ki.kontext import _hash
from ki.kontext import festhalten as text_festhalten
from ki.korrekturen import anfordern, export, stand
from ki.korrekturkontext import pruefen
from ki.models import KIAuftrag, KILauf, Zweck
from ki.test_kontext_auftrag import a  # noqa: F401
from ki.test_warteschlange import JSON_ANTWORT
from ki.warteschlange import auftrag_ausfuehren
from verfahren.models import Beanstandung
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]
PRIVAT = "NUR_SYNTHETISCHER_PRIVATBEIFANG"


@pytest.fixture(params=[0, 1, 2], ids=["ohne-quellen-korrektur1", "quellen1-korrektur1", "quellen2-korrektur2"])
def altfall(a, request, monkeypatch):  # noqa: F811
    return altfall_erzeugen(a, request.param, monkeypatch)


def altfall_erzeugen(a, quellenfassung, monkeypatch):
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: Antwort(JSON_ANTWORT, "lokaler-test", 1, 2))
    text = text_festhalten(a)
    q = quellen_festhalten([], hoechstzahl=3, textzeichen=30, text_sha256=text["sha256"],
                          fassung=quellenfassung) if quellenfassung else {}
    original = KIAuftrag.objects.create(zweck=Zweck.RECHTSBEZUG, antrag=a, angefordert_von=a.eingebracht_von,
        fassung_nummer=1, kontext=text, quellenkontext=q)
    assert auftrag_ausfuehren(original.pk) == "erledigt"
    original.refresh_from_db()
    Rolle.objects.create(mitglied=a.eingebracht_von, gremium=Gremium.EXPERTENRAT_1, antrag=a,
                         bestaetigt=True, endet_am=timezone.localdate() + timedelta(days=30))
    b = Beanstandung.objects.create(antrag=a, lauf=original.lauf, mitglied=a.eingebracht_von,
                                    text="Nur eine synthetische Quellenfrage.")
    job = anfordern(b, a.eingebracht_von)
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    job.refresh_from_db()
    return a, job


def neu_hashen(d):
    d.pop("sha256", None)
    return {**d, "sha256": _hash(d)}


def lauf_kopie(lauf, kontext):
    daten = {f.attname: copy.deepcopy(getattr(lauf, f.attname)) for f in KILauf._meta.concrete_fields if f.name != "id"}
    daten["kontext"] = kontext
    return KILauf.objects.create(**daten)


@pytest.mark.parametrize("fehler", ["zusatzfeld", "text", "quellen", "versuch", "fehlendes_feld", "auftragstyp"])
def test_ausgewaehlter_altlauf_mit_fremdem_kontext_wird_nicht_oeffentlich(altfall, fehler):
    a, job = altfall
    alter_lauf = job.lauf
    vorher = KILauf.objects.values().get(pk=alter_lauf.pk)
    k = copy.deepcopy(alter_lauf.kontext)
    if fehler == "zusatzfeld":
        k["privat"] = PRIVAT
    elif fehler == "text":
        k["text"] = neu_hashen({**k["text"], "privat": PRIVAT})
    elif fehler == "quellen":
        k["quellen"] = {**k["quellen"], "privat": PRIVAT}
    elif fehler == "versuch":
        k["versuch"] = PRIVAT
    elif fehler == "auftragstyp":
        k["auftrag"] = float(job.pk)
    else:
        del k["text"]
    fremd = lauf_kopie(alter_lauf, k)
    KIAuftrag.objects.filter(pk=job.pk).update(lauf=fremd)
    job.refresh_from_db()
    assert PRIVAT not in json.dumps(export(a))
    assert stand(job) == {"zustand": "fehler"}
    assert KILauf.objects.values().get(pk=alter_lauf.pk) == vorher
    assert KILauf.objects.get(pk=fremd.pk).kontext == k  # Kein nachträgliches Bereinigen.


def test_fremder_historischer_versuch_bleibt_gespeichert_aber_nicht_im_oeffentlichen_export(altfall):
    a, job = altfall
    korrekt = job.lauf
    fremd = lauf_kopie(korrekt, {**copy.deepcopy(korrekt.kontext), "privat": PRIVAT})
    d = export(a)[0]
    assert PRIVAT not in json.dumps(d)
    assert d["lauf"]["id"] == korrekt.pk
    assert [k["id"] for k in d["laeufe"]] == [korrekt.pk]
    assert KILauf.objects.get(pk=fremd.pk).kontext["privat"] == PRIVAT


@pytest.mark.parametrize("fehler", ["wurzel", "beanstandung", "text", "quellen", "versionstyp"])
def test_alter_korrekturrahmen_akzeptiert_keine_neu_gehashten_zusatzfelder(altfall, fehler):
    _a, job = altfall
    d = copy.deepcopy(job.korrekturkontext)
    if fehler == "wurzel":
        d["privat"] = PRIVAT
    elif fehler == "versionstyp":
        d["version"] = True
    elif fehler == "text":
        d["text"] = neu_hashen({**d["text"], "privat": PRIVAT})
    else:
        d[fehler]["privat"] = PRIVAT
    with pytest.raises(ValueError):
        pruefen(neu_hashen(d))


def test_gueltiger_alter_vertrag_bleibt_bytegleich_auch_mit_explizit_leerem_folgenfeld(altfall):
    a, job = altfall
    original = copy.deepcopy(job.lauf.kontext)
    raw = job.lauf.eingabe
    assert export(a)[0]["lauf"]["eingabe"] == raw
    assert export(a)[0]["lauf"]["kontext"] == original
    neu = lauf_kopie(job.lauf, {**original, "folgen": {}})
    KIAuftrag.objects.filter(pk=job.pk).update(lauf=neu)
    job.refresh_from_db()
    assert stand(job)["lauf"].pk == neu.pk
    assert export(a)[0]["lauf"]["eingabe"] == raw
    assert job.lauf.kontext == {**original, "folgen": {}}


@pytest.mark.parametrize("ort", ["wurzel", "beanstandung", "text", "quellen"])
def test_auch_wartender_rahmen_wird_vor_dem_oeffentlichen_export_geprueft(altfall, ort):
    a, job = altfall
    ursprung = job.ursprung
    alt = KILauf.objects.values().get(pk=ursprung.pk)
    b = Beanstandung.objects.create(antrag=a, lauf=ursprung, mitglied=a.eingebracht_von,
                                    text=job.beanstandung.text)
    rahmen = copy.deepcopy(job.korrekturkontext)
    rahmen["beanstandung"] = {"id": b.pk, "text": b.text, "erstellt_am": b.erstellt_am.isoformat()}
    if ort == "wurzel":
        rahmen["privat"] = PRIVAT
    elif ort == "text":
        rahmen["text"] = neu_hashen({**rahmen["text"], "privat": PRIVAT})
    else:
        rahmen[ort]["privat"] = PRIVAT
    rahmen = neu_hashen(rahmen)
    daten = {f.attname: copy.deepcopy(getattr(job, f.attname)) for f in KIAuftrag._meta.concrete_fields if f.name != "id"}
    daten.update(beanstandung_id=b.pk, korrekturkontext=rahmen, lauf_id=None, status="geplant", versuche=0)
    if ort == "text":
        daten["kontext"] = rahmen["text"]
    if ort == "quellen":
        daten["quellenkontext"] = rahmen["quellen"]
    schlecht = KIAuftrag.objects.create(**daten)
    assert stand(schlecht) == {"zustand": "fehler"}
    assert PRIVAT not in json.dumps(export(a))
    assert KIAuftrag.objects.get(pk=schlecht.pk).korrekturkontext == rahmen
    assert KILauf.objects.values().get(pk=ursprung.pk) == alt


@pytest.mark.parametrize("feld", ["titel", "wortlaut", "begruendung", "ebene", "ebene_wort", "gebiet", "erfasst_am", "fassung_id"])
def test_verschachtelte_fremddaten_sind_kein_oeffentliches_textfeld(altfall, feld):
    _a, job = altfall
    d = copy.deepcopy(job.korrekturkontext)
    d["text"][feld] = {"privat": PRIVAT}
    d["text"] = neu_hashen(d["text"])
    with pytest.raises(ValueError):
        pruefen(neu_hashen(d))


def test_gueltiger_rahmen_wird_ohne_heutige_datenbank_oder_nachberechnung_geprueft(altfall, django_assert_num_queries):
    _a, job = altfall
    vorher = copy.deepcopy(job.korrekturkontext)
    with django_assert_num_queries(0):
        d = pruefen(job.korrekturkontext)
    assert d == {k: v for k, v in vorher.items() if k != "sha256"}
    assert job.korrekturkontext == vorher
