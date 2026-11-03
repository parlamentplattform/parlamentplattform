"""Alte Prompts/Eingaben erhalten, neue Herkunft und tatsächlichen Ursprung binden."""

import copy
import hashlib
import json
import re
from datetime import timedelta

import pytest
from django.core import mail
from django.core.exceptions import ValidationError
from django.urls import reverse
from django.utils import timezone

from faktenbasis.kontext import eingabe as quelleneingabe
from faktenbasis.kontext import festhalten as quellen_festhalten
from faktenbasis.test_landesxml import landnorm, textquelle  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from gremien.models import Gremium, Rolle
from ki.anbieter import Antwort, AttrappenAnbieter
from ki.eingabevertrag import korrektur, rechtsbezug
from ki.kennungsabgleich import fuer_lauf
from ki.kontext import _hash, eingabe
from ki.kontext import festhalten as text_festhalten
from ki.korrekturen import anfordern, export
from ki.korrekturkontext import festhalten as korrektur_festhalten
from ki.models import KIAuftrag, KILauf, Zweck
from ki.test_kontext_auftrag import a  # noqa: F401
from ki.warteschlange import auftrag_ausfuehren, einreihen
from verfahren.models import Beanstandung
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]


@pytest.mark.parametrize("nummer", [2, 3])
def test_rechtsbezugsauftrag_hat_den_gleichen_oeffentlichen_antwortvertrag(nummer):
    from ki.auftraege import auftrag_laden
    from plattform_core.modellantwort import schema_als_dict

    text = auftrag_laden("rechtsbezug", nummer=nummer).text
    felder = schema_als_dict()["properties"]
    normen = felder["normen"]["items"]["properties"]
    # Die alte Fassung nennt die Werte im JSON-Muster, die neue zusätzlich als lesbare Liste.
    for schema in (normen["aenderung"], normen["ebene"], felder["unsicherheit"]):
        for wert in schema["enum"]:
            assert re.search(rf"\b{re.escape(wert)}\b", text)


@pytest.mark.parametrize("fassung,prompt", [(0, 1), (1, 2), (2, 3)])
def test_wartende_auftraege_behalten_ihren_tatsaechlichen_vertrag_auch_bei_korrektur(a, fassung, prompt):  # noqa: F811
    text = text_festhalten(a)
    quellen = quellen_festhalten([], hoechstzahl=3, textzeichen=30,
        text_sha256=text["sha256"], fassung=fassung) if fassung else {}
    vorher = copy.deepcopy((text, quellen))
    erwartet = eingabe(text) + ("\n\n" + quelleneingabe(quellen) if quellen else "")
    assert rechtsbezug(text, quellen) == (prompt, erwartet)
    j = KIAuftrag.objects.create(zweck=Zweck.RECHTSBEZUG, antrag=a, angefordert_von=a.eingebracht_von,
        fassung_nummer=1, kontext=text, quellenkontext=quellen)
    assert auftrag_ausfuehren(j.pk) == "erledigt"
    j.refresh_from_db()
    assert (j.kontext, j.quellenkontext) == vorher
    assert j.lauf.auftrag_version == f"rechtsbezug-v{prompt}" and j.lauf.eingabe == erwartet
    m = a.eingebracht_von
    Rolle.objects.create(mitglied=m, gremium=Gremium.EXPERTENRAT_1, antrag=a, bestaetigt=True,
        endet_am=timezone.localdate()+timedelta(days=30))
    b = Beanstandung.objects.create(antrag=a, lauf=j.lauf, mitglied=m, text="Beleg ist ungeklärt")
    rahmen = korrektur_festhalten(b, j.lauf)
    nummer, wortlaut = korrektur(rahmen)
    assert nummer == (2 if fassung == 2 else 1)
    assert json.loads(wortlaut)["urspruengliche_eingabe"] == erwartet
    k = anfordern(b, m)
    assert auftrag_ausfuehren(k.pk) == "erledigt"
    k.refresh_from_db()
    assert k.lauf.auftrag_version == f"korrektur-v{nummer}" and k.lauf.eingabe == wortlaut
    assert export(a)[0]["lauf"]["eingabe"] == wortlaut
    assert (j.kontext, j.quellenkontext) == vorher


@pytest.mark.parametrize("quellen", [None, [], False, "", 0])
def test_falsche_leerwerte_sind_kein_alter_quellenloser_vertrag(a, quellen):  # noqa: F811
    with pytest.raises(ValueError):
        rechtsbezug(text_festhalten(a), quellen)


def test_passender_quellenhash_allein_reicht_nicht_fuer_fremden_text(a):  # noqa: F811
    text = text_festhalten(a)
    q = quellen_festhalten([], hoechstzahl=3, textzeichen=30, text_sha256="a"*64)
    with pytest.raises(ValueError):
        rechtsbezug(text, q)


def test_korrektur_lehnt_anderen_ursprung_trotz_neuer_gueltiger_hashes_ab(a):  # noqa: F811
    j = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    assert auftrag_ausfuehren(j.pk) == "erledigt"
    j.refresh_from_db()
    b = Beanstandung.objects.create(antrag=a, lauf=j.lauf, mitglied=a.eingebracht_von, text="Unbelegt")
    d = korrektur_festhalten(b, j.lauf)
    d["eingabe"] = "NICHT DER OEFFENTLICHE WORTLAUT"
    d["eingabe_sha256"] = hashlib.sha256(d["eingabe"].encode()).hexdigest()
    d["sha256"] = _hash({k: v for k, v in d.items() if k != "sha256"})
    with pytest.raises(ValueError, match="ursprüngliche"):
        korrektur(d)


def test_landeskontext_geht_mit_v3_einmalig_ins_modell_nachlese_bleibt_ohne_db(a, landnorm, textquelle, monkeypatch, django_assert_num_queries, client):  # noqa: F811
    from faktenbasis.volltext import importieren

    importieren(landnorm)
    a.eingebracht_von.post_einwilligung = True
    a.eingebracht_von.save(update_fields=["post_einwilligung"])
    a.titel = landnorm.kurztitel
    a.save(update_fields=["titel"])
    gesehen = []
    def frage(self, prompt, text):
        gesehen.append((prompt, text))
        return Antwort(json.dumps({"normen": [{"titel": "Ungeprüfte Deutung", "ebene": "Land",
            "kennung": landnorm.ris_id, "aenderung": "beruehrt", "begruendung": "Ungeprüft"}],
            "hinweis": "Keine Zuständigkeitsprüfung", "unsicherheit": "hoch"}), "test-land", 10, 20)
    monkeypatch.setattr(AttrappenAnbieter, "frage", frage)
    j = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    assert auftrag_ausfuehren(j.pk) == "erledigt"
    j.refresh_from_db()
    assert len(gesehen) == 1 and j.lauf.auftrag_version == "rechtsbezug-v3"
    assert '"bundesland": "Oberösterreich"' in gesehen[0][1]
    with django_assert_num_queries(0):
        d = fuer_lauf(j.lauf)
    q = d["zuordnungen"][0]["quelle"]
    assert q["norm_id"] == landnorm.pk and q["ebene"] == "Land" and q["bundesland"] == "Oberösterreich"
    assert not d["rechtlich_verifiziert"]
    html = client.get(reverse("verfahren:antrag", args=[a.pk])).content.decode()
    assert "Auswahlumfang: vorhandenes Bundes- und Landesrecht" in html
    assert "Land · Oberösterreich" in html and "rechtsbezug-v3" in html
    from ki.nachlese import antrag_export
    from mitglieder.postausgang import offene_zustellen

    daten = antrag_export(a)
    assert daten["laeufe"][0]["kennungsabgleich"]["zuordnungen"][0]["quelle"] == q
    assert daten["laeufe"][0]["kontext"]["quellen"] == j.quellenkontext
    assert offene_zustellen() == 1
    assert "Land · Oberösterreich" in mail.outbox[-1].body
    assert "ohne räumliche Zuständigkeitsprüfung" in mail.outbox[-1].body


@pytest.mark.parametrize("fehler", ["eingabe", "prompt"])
def test_unbewiesener_ursprung_wird_auch_mit_passendem_job_nicht_als_korrektur_versendet(a, fehler):  # noqa: F811
    j = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    assert auftrag_ausfuehren(j.pk) == "erledigt"
    j.refresh_from_db()
    daten = {f.attname: copy.deepcopy(getattr(j.lauf, f.attname)) for f in KILauf._meta.concrete_fields if f.name != "id"}
    daten["eingabe" if fehler == "eingabe" else "auftrag_version"] = "NICHT BELEGT"
    falsch = KILauf.objects.create(**daten)
    j.lauf = falsch
    j.save(update_fields=["lauf"])
    m = a.eingebracht_von
    Rolle.objects.create(mitglied=m, gremium=Gremium.EXPERTENRAT_1, antrag=a, bestaetigt=True,
        endet_am=timezone.localdate()+timedelta(days=30))
    b = Beanstandung.objects.create(antrag=a, lauf=falsch, mitglied=m, text="Ungeklärte Herkunft")
    with pytest.raises(ValidationError):
        anfordern(b, m)
    assert not KIAuftrag.objects.filter(zweck=Zweck.KORREKTUR).exists()
