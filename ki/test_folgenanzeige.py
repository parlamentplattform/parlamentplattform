"""Aktueller Bericht, frühere Fassungen, Beanstandung, Post und öffentliche Exporte."""
# ruff: noqa: F811 -- importierte pytest-Fixtures

import copy
import json

import pytest
from django.urls import reverse

from ki.anbieter import AnbieterFehler, Antwort, AttrappenAnbieter
from ki.models import Auftragsstatus, KIAuftrag, KILauf, Zweck
from ki.nachlese import antrag_export
from ki.rechtsbezug import rechtsbezug_fuer, rechtsbezug_lage
from ki.test_folgenauftraege import ANTWORT, attrappe, neu  # noqa: F401
from ki.test_kontext import antrag, vorschlag  # noqa: F401
from ki.warteschlange import auftrag_ausfuehren, einreihen
from mitglieder.models import Postauftrag
from verfahren.models import Beanstandung
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def erfolg(antrag):
    j = neu(antrag)
    assert auftrag_ausfuehren(j.pk) == "erledigt"
    j.refresh_from_db()
    return j


def test_neuer_bericht_ist_in_hauptanzeige_und_export_derselbe_oeffentliche_lauf(antrag, attrappe, client):
    job = erfolg(antrag)
    lage = rechtsbezug_lage(antrag)
    assert lage["zustand"] == "erledigt" and lage["ergebnis"]["lauf"].pk == job.lauf_id
    assert lage["ergebnis"]["folgenbericht"] and lage["ergebnis"]["formatpruefung"]["gueltig"]
    html = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "Folgen für Judikatur" in html and "Folgen für Exekutive" in html and "nicht bestimmbar" in html
    assert "Noch keine Einschätzung —" not in html and "folgen-test" in html
    d = antrag_export(antrag)
    assert d["auftraege"][0]["folgenkontext"] == job.folgenkontext
    assert d["laeufe"][0]["eingabe"] == job.lauf.eingabe and d["laeufe"][0]["kontext"]["folgen"] == job.folgenkontext
    assert d["laeufe"][0]["antwortformat"]["gueltig"]
    assert job.lauf.kontext["folgen"]["sha256"] == lage["ergebnis"]["folgen_sha256"]


def test_personalquelle_und_tatsaechlicher_gesamtbestand_stehen_getrennt_von_der_folgenprosa(antrag, attrappe, client):
    from faktenbasis.test_personalrahmen import daten

    daten()
    job = erfolg(antrag)
    p = rechtsbezug_fuer(antrag)["personalstand"]
    assert p["aggregat"]["gesamt"] == 138100 and p["ressorttabelle"]["gesamt"]["gesamt"] == 138100
    html = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "Damals verwendeter Personalbestand" in html and p["sha256"] in html and "Originalpublikation" in html
    assert str(p["aggregat"]["seite"]) in html and str(p["ressorttabelle"]["methodik_seite"]) in html
    assert job.folgenkontext["personal"] == p


def test_darstellung_ist_neutral_geordnet_aber_originalantwort_bleibt_erhalten(antrag, attrappe, monkeypatch, client):
    d = json.loads(ANTWORT)
    d["normen"] = [{"ris_id": "", "titel": t, "aenderung": "neu", "grund": "Unverifizierte Aussage"}
                   for t in ["Zweiter Modelltitel", "Erster Modelltitel"]]
    roh = json.dumps(d)
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *a: Antwort(roh, "test", 1, 2))
    job = erfolg(antrag)
    e = rechtsbezug_fuer(antrag)
    assert [n["titel"] for n in e["normen"]] == ["Erster Modelltitel", "Zweiter Modelltitel"]
    assert job.lauf.antwort == roh and e["formatpruefung"]["daten"]["normen"] == d["normen"]
    html = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "alphabetisch nach Modelltitel" in html
    assert html.index("Erster Modelltitel") < html.index("Zweiter Modelltitel")


def test_neuer_vorschlag_wartet_trotz_altem_folgenbericht_und_historie_bleibt_nachlesbar(antrag, attrappe):
    alt = erfolg(antrag)
    v = vorschlag(antrag)
    neuer = neu(antrag, vorschlagsfassung=v)
    lage = rechtsbezug_lage(antrag)
    assert lage["zustand"] == "wartet" and lage["ergebnis"] is None and lage["auftrag"].pk == neuer.pk
    assert lage["historie"][0]["lauf"].pk == alt.lauf_id and lage["historie"][0]["frueher"]
    auftrag_ausfuehren(neuer.pk)
    neuer.refresh_from_db()
    lage = rechtsbezug_lage(antrag)
    assert lage["ergebnis"]["lauf"].pk == neuer.lauf_id and lage["ergebnis"]["textstand"]["quellenart"] == "vorschlag"
    assert lage["historie"][0]["lauf"].pk == alt.lauf_id


def test_alter_rechtsbezug_bleibt_historisch_lesbar_neben_neuem_folgenbericht(antrag, attrappe, monkeypatch):
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *a: Antwort('{"normen":[],"hinweis":"Altbestand","unsicherheit":"hoch"}', "alt", 1, 2))
    alt = einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    auftrag_ausfuehren(alt.pk)
    alt.refresh_from_db()
    vorher = copy.deepcopy(alt.lauf.kontext)
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *a: Antwort(ANTWORT, "neu", 1, 2))
    neu = erfolg(antrag)
    lage = rechtsbezug_lage(antrag)
    assert lage["ergebnis"]["lauf"].pk == neu.lauf_id and lage["ergebnis"]["folgenbericht"]
    h = lage["historie"][0]
    assert h["hinweis"] == "Altbestand" and h["lauf"].auftrag_version == "rechtsbezug-v3"
    assert not h.get("folgenbericht") and KILauf.objects.get(pk=alt.lauf_id).kontext == vorher
    assert len(antrag_export(antrag)["laeufe"]) == 2


def test_formfehler_gibt_keine_gut_aussehende_teilantwort_aus(antrag, attrappe, monkeypatch, client):
    d = json.loads(ANTWORT)
    d["personal"][0]["vb_delta_max"] = 0
    d["judikatur"]["text"] = "DIESEN_TEIL_NICHT_ALS_BERICHT_ZEIGEN"
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *a: Antwort(json.dumps(d), "test", 1, 2))
    job = erfolg(antrag)
    e = rechtsbezug_fuer(antrag)
    assert e["lauf"].pk == job.lauf_id and not e["formatpruefung"]["gueltig"] and not e["judikatur"]
    html = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "keine Teilantwort" in html and "DIESEN_TEIL_NICHT_ALS_BERICHT_ZEIGEN" not in html
    assert "DIESEN_TEIL_NICHT_ALS_BERICHT_ZEIGEN" in antrag_export(antrag)["laeufe"][0]["antwort"]


def test_ohne_vorbereitung_bleibt_fehler_auch_bei_abgezogenem_anbieter_sichtbar(antrag, settings, client):
    job = einreihen(Zweck.RECHTSFOLGEN, antrag, antrag.eingebracht_von, hoechstzeichen=1)
    settings.DDOE_KI_ANBIETER = ""
    assert job.status == Auftragsstatus.GESCHEITERT and rechtsbezug_lage(antrag)["zustand"] == "gescheitert"
    html = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "Der Auftrag konnte nicht vorbereitet werden" in html
    d = antrag_export(antrag)
    assert d["auftraege"][0]["kontextstatus"] == "fehler" and not d["laeufe"]


def test_fehllauf_bleibt_in_historie_und_export_ohne_erfundene_ergebnisdaten(antrag, attrappe, monkeypatch):
    def kaputt(*a):
        raise AnbieterFehler("Technischer Testfehler")
    monkeypatch.setattr(AttrappenAnbieter, "frage", kaputt)
    job = neu(antrag)
    assert auftrag_ausfuehren(job.pk) == "verschoben"
    job.refresh_from_db()
    lage = rechtsbezug_lage(antrag)
    assert lage["zustand"] == "wartet" and lage["historie"][0]["lauf"].pk == job.lauf_id
    assert not lage["historie"][0]["normen"] and not lage["historie"][0]["judikatur"]
    e = antrag_export(antrag)["laeufe"][0]
    assert e["erfolgreich"] is False and e["antwortformat"] is None and e["kontext"]["folgen"] == job.folgenkontext


def test_fremder_beifang_im_neuen_zweck_wird_nicht_als_oeffentliche_antwort_exportiert(antrag, attrappe, client):
    job = erfolg(antrag)
    daten = {f.name: getattr(job.lauf, f.name) for f in KILauf._meta.fields if f.name != "id"}
    daten["kontext"] = {**daten["kontext"], "privat": "VERTRAULICHER_BEIFANG"}
    daten["antwort"] = "INTERNE_ANTWORT_NICHT_EXPORTIEREN"
    fremd = KILauf.objects.create(**daten)
    KIAuftrag.objects.filter(pk=job.pk).update(lauf=fremd)
    lage = rechtsbezug_lage(antrag)
    assert lage["zustand"] == "nicht_pruefbar" and lage["ergebnis"] is None
    d = antrag_export(antrag)
    assert d["laeufe"][-1] == {"id": fremd.pk, "zweck": "rechtsfolgen", "kontextstatus": "fehler"}
    html = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "VERTRAULICHER_BEIFANG" not in html + json.dumps(d)
    assert "INTERNE_ANTWORT_NICHT_EXPORTIEREN" not in html + json.dumps(d)
    assert "nicht eindeutig an den öffentlichen Auftrag gebunden" in html


def test_beanstandung_waehlt_den_gelesenen_folgenlauf_auch_nach_spaeterer_antwort(antrag, attrappe, client):
    alt = erfolg(antrag)
    neuer = neu(antrag, vorschlagsfassung=vorschlag(antrag))
    auftrag_ausfuehren(neuer.pk)
    client.force_login(antrag.eingebracht_von)
    url = reverse("verfahren:beanstanden", args=[antrag.pk])
    assert client.post(url, {"text": "Ich beanstande genau diesen Stand.", "lauf": alt.lauf_id}).status_code == 302
    assert Beanstandung.objects.get(antrag=antrag).lauf_id == alt.lauf_id


@pytest.mark.parametrize("einwilligung", [True, False])
def test_ergebnispost_ist_einmalig_mit_einwilligung_und_hat_denselben_bericht(antrag, attrappe, mailoutbox, einwilligung):
    from mitglieder.postausgang import zustellen

    m = antrag.eingebracht_von
    m.post_einwilligung = einwilligung
    m.save(update_fields=["post_einwilligung"])
    job = erfolg(antrag)
    qs = Postauftrag.objects.filter(art="rechtsbezug", mitglied=m, antrag=antrag)
    if not einwilligung:
        assert not qs.exists() and not mailoutbox
        return
    p = qs.get()
    zustellen(p.pk)
    assert len(mailoutbox) == 1
    mail = mailoutbox[0].body
    assert "Folgen für Judikatur" in mail and "Folgen für Exekutive" in mail and "nicht bestimmbar" in mail
    assert job.lauf.auftrag_version in mail and job.kontext["sha256"] in mail
    zustellen(p.pk)
    assert len(mailoutbox) == 1
