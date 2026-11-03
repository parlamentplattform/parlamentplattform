"""Korrektur separat im Budget, exakter Ursprung und keine privaten Beifänge."""

import copy
import json
import re
from datetime import timedelta

import pytest
from django.core.exceptions import ValidationError
from django.db import transaction
from django.urls import reverse
from django.utils import timezone

from gremien.models import Gremium, Rolle
from ki.anbieter import Antwort, AttrappenAnbieter
from ki.korrekturen import anfordern, export, hinzufuegen
from ki.models import KIAuftrag, KILauf, Zweck
from ki.nachlese import antrag_export
from ki.test_warteschlange import JSON_ANTWORT
from ki.warteschlange import abarbeiten, auftrag_ausfuehren, einreihen, heute_gestartet
from verfahren.models import AuditEintrag, Beanstandung, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def test_korrekturauftrag_verlangt_nur_werte_des_oeffentlichen_antwortschemas():
    from ki.auftraege import auftrag_laden
    from plattform_core.modellantwort import schema_als_dict

    text = auftrag_laden("korrektur", nummer=1).text
    felder = schema_als_dict()["properties"]
    normen = felder["normen"]["items"]["properties"]
    for etikett, schema in (("Erlaubte Änderungen", normen["aenderung"]), ("Ebenen", normen["ebene"]),
                            ("Unsicherheit", felder["unsicherheit"])):
        angabe = re.search(rf"{etikett}: ([^.]+)\.", text)
        assert angabe is not None
        assert {s.strip() for s in angabe[1].split(",")} == set(schema["enum"])


@pytest.fixture
def fall(settings, monkeypatch, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    monkeypatch.setattr(
        AttrappenAnbieter, "frage", lambda *args: Antwort(JSON_ANTWORT, "test-korrektur", 10, 20)
    )
    m = mitglied_anlegen("korrektur-fachkraft")
    a = antrag_einbringen(m, **ANTRAG, ordnung=ordnung)
    r = Rolle.objects.create(
        mitglied=m,
        gremium=Gremium.EXPERTENRAT_1,
        antrag=a,
        endet_am=timezone.localdate() + timedelta(days=30),
        bestaetigt=True,
    )
    alt = einreihen(Zweck.RECHTSBEZUG, a, m)
    assert auftrag_ausfuehren(alt.pk) == "erledigt"
    alt.refresh_from_db()
    b = Beanstandung.objects.create(
        antrag=a, lauf=alt.lauf, mitglied=m, text="Die Begründung ist nicht belegt."
    )
    return a, m, r, alt, b


def test_anfordern_bleibt_idempotent_und_aendert_kein_original(fall, monkeypatch):
    a, m, r, alt, b = fall
    vorher = KILauf.objects.filter(pk=alt.lauf_id).values().get()
    beanstandung = Beanstandung.objects.filter(pk=b.pk).values().get()
    monkeypatch.setattr(
        AttrappenAnbieter, "frage", lambda *args: pytest.fail("Anfordern darf keinen Anbieter aufrufen")
    )
    job = anfordern(b, m)
    assert anfordern(b, m).pk == job.pk
    assert job.ursprung_id == alt.lauf_id and job.zweck == Zweck.KORREKTUR
    assert job.quellenkontext == alt.quellenkontext and job.kontext == alt.kontext
    assert AuditEintrag.objects.filter(ereignis__typ="ki_korrektur_angefordert").count() == 1
    assert KILauf.objects.filter(pk=alt.lauf_id).values().get() == vorher
    assert Beanstandung.objects.filter(pk=b.pk).values().get() == beanstandung


def test_ausfuehren_verwendet_genau_den_alten_rahmen_und_laesst_beanstandung_offen(fall, monkeypatch):
    a, m, r, alt, b = fall
    job = anfordern(b, m)
    eingabe = alt.lauf.eingabe
    a.titel = "Ein inzwischen anderer Titel"
    a.save(update_fields=["titel"])

    def frage(_self, prompt, text):
        d = json.loads(text)
        assert d["urspruengliche_eingabe"] == eingabe
        assert d["urspruengliche_antwort"] == JSON_ANTWORT and d["beanstandung"] == b.text
        assert m.username not in text and "anderer Titel" not in text
        return Antwort('{"normen":[],"hinweis":"Ungeklärt","unsicherheit":"hoch"}', "nachrechnung", 7, 8)

    monkeypatch.setattr(AttrappenAnbieter, "frage", frage)
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    job.refresh_from_db()
    b.refresh_from_db()
    assert job.lauf.zweck == Zweck.KORREKTUR and job.lauf.auftrag_version == "korrektur-v1"
    assert job.lauf.kontext["text"] == alt.kontext and job.lauf.kontext["korrektur"] == job.korrekturkontext
    assert b.erledigt_am is None and b.erledigt_vermerk == ""
    assert antrag_export(a)["laeufe"][0]["id"] == alt.lauf_id
    assert export(a)[0]["lauf"]["id"] == job.lauf_id


@pytest.mark.parametrize("sperre", ["fremd", "ruht", "abgelaufen", "keine_rolle", "ungeprueft", "pausiert", "testkonto", "inaktiv"])
def test_nur_zustaendige_aktive_fachkraft_darf_anfordern(fall, sperre, ordnung):  # noqa: F811
    a, m, r, alt, b = fall
    if sperre == "fremd":
        r.antrag = antrag_einbringen(m, **ANTRAG, ordnung=ordnung)
    elif sperre == "ruht":
        r.ruht_seit = timezone.now()
    elif sperre == "abgelaufen":
        r.endet_am = timezone.localdate() - timedelta(days=1)
    elif sperre == "keine_rolle":
        r.gremium = Gremium.EXPERTENRAT_2
    elif sperre == "pausiert":
        m.status = "pausiert"
        m.save(update_fields=["status"])
    elif sperre == "testkonto":
        m.testkonto = True
        m.save(update_fields=["testkonto"])
    elif sperre == "inaktiv":
        m.is_active = False
        m.save(update_fields=["is_active"])
    else:
        m.identitaetsstufe = "ungeprueft"
        m.save(update_fields=["identitaetsstufe"])
    r.save()
    with pytest.raises(PermissionError):
        anfordern(b, m)
    assert not KIAuftrag.objects.filter(zweck=Zweck.KORREKTUR).exists()


@pytest.mark.parametrize("art", ["intern", "alt", "fremder_antrag", "fehlerhaft", "kein_ursprung"])
def test_keine_internen_alten_oder_fremden_eingaben_uebernehmen(fall, art, ordnung):  # noqa: F811
    a, m, r, alt, b = fall
    data = {f.name: getattr(alt.lauf, f.name) for f in KILauf._meta.fields if f.name != "id"}
    data["kontext"] = copy.deepcopy(data["kontext"])
    if art == "intern":
        data.update(zweck=Zweck.EINSCHAETZUNG, eingabe="VERTRAULICH")
    elif art == "alt":
        data["kontext"] = {}
    elif art == "fremder_antrag":
        data["antrag"] = antrag_einbringen(m, **ANTRAG, ordnung=ordnung)
    elif art == "fehlerhaft":
        data["kontext"]["text"]["wortlaut"] = "Beschädigt"
    else:
        data["kontext"]["auftrag"] = 999999
    lauf = KILauf.objects.create(**data)
    bad = Beanstandung.objects.create(antrag=a, lauf=lauf, mitglied=m, text=b.text)
    with pytest.raises(ValidationError):
        anfordern(bad, m)
    assert not KIAuftrag.objects.filter(zweck=Zweck.KORREKTUR).exists()


def test_ohne_anbieter_und_ohne_tageskontingent_bleibt_auftrag_unversucht(fall, settings):
    a, m, r, alt, b = fall
    j = anfordern(b, m)
    settings.DDOE_KI_ANBIETER = ""
    assert abarbeiten()["anbieter"] is False
    j.refresh_from_db()
    assert j.versuche == 0
    settings.DDOE_KI_ANBIETER = "attrappe"
    # Ein tatsächlicher Korrekturaufruf zählt im selben Kalendertageskontingent mit.
    vorher = heute_gestartet()
    assert auftrag_ausfuehren(j.pk) == "erledigt"
    assert heute_gestartet() == vorher + 1


def test_fehler_wird_als_lauf_archiviert_und_spaeter_neu_versucht(fall, monkeypatch):
    from ki.anbieter import AnbieterFehler

    a, m, r, alt, b = fall
    j = anfordern(b, m)

    def fehler(*args):
        raise AnbieterFehler("Technischer Testfehler")

    monkeypatch.setattr(AttrappenAnbieter, "frage", fehler)
    assert auftrag_ausfuehren(j.pk) == "verschoben"
    j.refresh_from_db()
    fehl = j.lauf_id
    assert fehl and not j.lauf.erfolgreich
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: Antwort(JSON_ANTWORT, "nochmal", 1, 2))
    assert auftrag_ausfuehren(j.pk, jetzt=j.naechster_versuch) == "erledigt"
    assert KILauf.objects.get(pk=fehl).erfolgreich is False
    assert Beanstandung.objects.get(pk=b.pk).erledigt_am is None
    assert [k["erfolgreich"] for k in export(a)[0]["laeufe"]] == [False, True]


@pytest.mark.parametrize("feld", ["beanstandung", "ursprung", "korrekturkontext"])
def test_neue_auftragsbeziehungen_und_kontext_sind_unveraenderlich(fall, feld):
    a, m, r, alt, b = fall
    j = anfordern(b, m)
    with transaction.atomic():
        with pytest.raises(ValidationError):
            KIAuftrag.objects.filter(pk=j.pk).update(**{feld: None})
        assert KIAuftrag.objects.filter(pk=j.pk).exists()


@pytest.mark.parametrize("weg", ["save", "update", "bulk_update", "upsert", "delete", "instanz_delete", "neue_instanz"])
def test_beanstandung_bleibt_auch_ausserhalb_des_webformulars_unveraenderlich(fall, weg):
    a, m, r, alt, b = fall
    vor = Beanstandung.objects.filter(pk=b.pk).values().get()
    b.text = "Ersetzt"
    with transaction.atomic():
        with pytest.raises(ValidationError):
            if weg == "save":
                b.save()
            elif weg == "update":
                Beanstandung.objects.filter(pk=b.pk).update(text="Neu")
            elif weg == "bulk_update":
                Beanstandung.objects.bulk_update([b], ["text"])
            elif weg == "upsert":
                Beanstandung.objects.bulk_create(
                    [b], update_conflicts=True, unique_fields=["pk"], update_fields=["text"]
                )
            elif weg == "instanz_delete":
                b.delete()
            elif weg == "neue_instanz":
                Beanstandung(pk=b.pk, antrag=a, lauf=alt.lauf, mitglied=m, text="Ersetzt").save()
            else:
                Beanstandung.objects.filter(pk=b.pk).delete()
        assert Beanstandung.objects.filter(pk=b.pk).values().get() == vor


def test_post_schreibt_erst_nach_rollenpruefung_und_get_rechnet_nicht(fall, client):
    a, m, r, alt, b = fall
    url = reverse("verfahren:korrektur_anfordern", args=[a.pk, b.pk])
    assert client.post(url).status_code == 302
    client.force_login(m)
    assert client.get(url).status_code == 405
    antwort = client.post(url)
    assert antwort.status_code == 302 and client.post(url).status_code == 302
    assert antwort["Location"] == reverse("verfahren:antrag", args=[a.pk]) + f"#beanstandung-{b.pk}"
    assert KIAuftrag.objects.filter(beanstandung=b).count() == 1
    assert KILauf.objects.count() == 1  # die Rechnung passiert nicht im POST oder GET
    j = KIAuftrag.objects.get(beanstandung=b)
    ansicht = hinzufuegen(a, [b], m)[0].korrekturstand
    assert ansicht["zustand"] == "geplant" and ansicht["auftrag"].pk == j.pk


@pytest.mark.parametrize("key", ["ki-tageslaeufe", "ki-monatstokens"])
def test_erschoepftes_gemeinsames_budget_verbraucht_keinen_versuch(fall, key):
    from parameter.models import Parameter
    a, m, r, alt, b = fall
    j = anfordern(b, m)
    Parameter.objects.create(schluessel=key, wert="0", beschreibung="Testgrenze", quelle="Test")
    assert abarbeiten()["erledigt"] == 0
    j.refresh_from_db()
    assert j.versuche == 0 and j.lauf_id is None


def test_get_und_csrf_fehler_reihen_keine_korrektur_ein(fall):
    from django.test import Client
    a, m, r, alt, b = fall
    c = Client(enforce_csrf_checks=True)
    c.force_login(m)
    u = reverse("verfahren:korrektur_anfordern", args=[a.pk, b.pk])
    assert c.post(u).status_code == 403
    assert not KIAuftrag.objects.filter(zweck=Zweck.KORREKTUR).exists()


def test_veraenderter_rahmen_oder_fremder_lauf_leckt_keine_daten(fall):
    a, m, r, alt, b = fall
    j = anfordern(b, m)
    privat = KILauf.objects.create(zweck=Zweck.EINSCHAETZUNG, antrag=a, angefordert_von=m,
        anbieter="attrappe", modell="intern", eingabe="PRIVATER ENTWURF", antwort="GEHEIM")
    KIAuftrag.objects.filter(pk=j.pk).update(lauf=privat)
    assert "GEHEIM" not in json.dumps(export(a))
    assert export(a) == [{"auftrag": j.pk, "zustand": "fehler"}]


def test_explizit_gewahlter_lauf_bleibt_trotz_neuerer_antwort_ziel_der_beanstandung(fall, client):
    a, m, r, alt, b = fall
    KILauf.objects.create(zweck=Zweck.RECHTSBEZUG, antrag=a, angefordert_von=m,
        anbieter="attrappe", modell="neu", eingabe="Späterer Stand", antwort="Neu")
    client.force_login(m)
    u = reverse("verfahren:beanstanden", args=[a.pk])
    assert client.post(u, {"text":"Ich beanstande den früher gelesenen Lauf.", "lauf":alt.lauf_id}).status_code == 302
    assert a.beanstandungen.order_by("-pk").first().lauf_id == alt.lauf_id
    assert client.post(u, {"text":"Nicht zulässig", "lauf":999999}).status_code == 302
    assert a.beanstandungen.count() == 2


def test_webpfad_verweigert_fremder_gruppe_und_falschem_antrag_die_nachrechnung(fall, client, ordnung):  # noqa: F811
    a, m, r, alt, b = fall
    fremd = mitglied_anlegen("andere-fachkraft")
    client.force_login(fremd)
    assert client.post(reverse("verfahren:korrektur_anfordern", args=[a.pk, b.pk])).status_code == 403
    client.force_login(m)
    anderer = antrag_einbringen(m, **ANTRAG, ordnung=ordnung)
    assert client.post(reverse("verfahren:korrektur_anfordern", args=[anderer.pk, b.pk])).status_code == 404
    assert not KIAuftrag.objects.filter(zweck=Zweck.KORREKTUR).exists()


@pytest.mark.parametrize("wert", [None, {}, {"sha256": "ü"}, {"version": 1, "sha256": "f" * 64}])
def test_beschaedigter_korrekturrahmen_wird_nicht_still_ergaenzt(wert):
    from ki.korrekturkontext import pruefen

    with pytest.raises(ValueError):
        pruefen(wert)


def test_gespeicherte_beanstandung_statt_veraendertem_python_objekt_wird_eingereiht(fall):
    a, m, r, alt, b = fall
    text = b.text
    b.text = "Nur im Arbeitsspeicher verändert"
    job = anfordern(b, m)
    assert job.korrekturkontext["beanstandung"]["text"] == text


def test_korrektur_ist_nicht_ueber_allgemeines_einreihen_umgehbar(fall):
    a, m, r, alt, b = fall
    with pytest.raises(ValueError):
        einreihen(Zweck.KORREKTUR, a, m)
