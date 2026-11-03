"""Neue Quellen werden vor Einreihung festgehalten, alte Aufträge nicht umgedeutet."""

import copy
from datetime import timedelta

import pytest
from django.db import connection, transaction
from django.urls import reverse

from faktenbasis import auswahl
from faktenbasis.kontext import eingabe as quelleneingabe
from faktenbasis.models import Norm
from faktenbasis.test_volltext import norm, xml  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from ki.anbieter import AnbieterFehler, AttrappenAnbieter
from ki.kontext import festhalten as text_festhalten
from ki.models import Auftragsstatus, KIAuftrag, KILauf, Zweck
from ki.nachlese import antrag_export, quellenstand
from ki.test_kontext_auftrag import a  # noqa: F401
from ki.warteschlange import auftrag_ausfuehren, einreihen
from parameter.models import Parameter
from verfahren.models import AntragsFassung
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]


def test_neuer_auftrag_haelt_passende_quelle_fest_kein_titellink_der_modellantwort(a, norm, client):  # noqa: F811
    a.titel = norm.kurztitel
    a.save(update_fields=["titel"])
    job = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    q, = job.quellenkontext["quellen"]
    assert q["norm_id"] == norm.pk and q["dokumenttext"] is None
    assert job.quellenkontext["auswahl"]["bestand_ids"] == [norm.pk]
    html = client.get(reverse("verfahren:antrag", args=[a.pk])).content.decode()
    assert "Nur Metadaten; kein amtlicher Dokumenttext im Auftrag." in html
    assert "Die Auswahl beweist keine rechtliche Betroffenheit" in html and q["metadaten_sha256"] not in html


def test_anbieter_verwendet_nur_festgehaltene_quellen_auch_nach_neuem_import(a, norm, monkeypatch):  # noqa: F811
    a.titel = norm.kurztitel
    a.save(update_fields=["titel"])
    job = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    vorher = copy.deepcopy(job.quellenkontext)
    def kein_nachladen(*args, **kwargs):
        raise AssertionError("Während Ausführung keine Quellen nachladen")
    monkeypatch.setattr(auswahl, "erfassen", kein_nachladen)
    original = AttrappenAnbieter.frage
    gesehen = {}
    def beobachten(self, auftragstext, eingabe):
        gesehen.update(auftragstext=auftragstext, eingabe=eingabe)
        return original(self, auftragstext, eingabe)
    monkeypatch.setattr(AttrappenAnbieter, "frage", beobachten)
    assert einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von).pk == job.pk
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    job.refresh_from_db()
    assert job.lauf.auftrag_version == "rechtsbezug-v2"
    assert job.lauf.kontext["quellen"] == vorher
    assert job.lauf.eingabe.endswith(quelleneingabe(vorher))
    assert gesehen["eingabe"] == job.lauf.eingabe and "Kontextkandidaten" in gesehen["auftragstext"]
    assert '"bestand_ids"' not in job.lauf.eingabe  # kein Tokenvolumen für interne Auswahlbelege
    export = antrag_export(a)
    assert export["auftraege"][0]["quellenkontext"] == vorher
    assert export["laeufe"][0]["kontext"]["quellen"] == vorher


def test_alter_wartender_auftrag_bleibt_explizit_v1_ohne_neue_quellen(a, norm, monkeypatch):  # noqa: F811
    alt = KIAuftrag.objects.create(zweck=Zweck.RECHTSBEZUG, antrag=a, angefordert_von=a.eingebracht_von, fassung_nummer=1)
    monkeypatch.setattr(auswahl, "erfassen", lambda *args: pytest.fail("Alter Auftrag wurde neu erfasst"))
    assert einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von).pk == alt.pk
    assert auftrag_ausfuehren(alt.pk) == "erledigt"
    alt.refresh_from_db()
    assert alt.quellenkontext == {} and alt.lauf.auftrag_version == "rechtsbezug-v1"
    assert "quellen" not in alt.lauf.kontext and quellenstand(None)["zustand"] == "alt"


def test_zeitpunkt_und_neueste_fassung_vor_titelsuche(a, norm):  # noqa: F811
    a.titel = norm.kurztitel
    a.save(update_fields=["titel"])
    alt = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    from faktenbasis.kontext import _hash
    daten = copy.deepcopy(norm.rohdaten)
    daten["Test"] = "Neue Metadaten"
    Norm.objects.create(
        ris_id=norm.ris_id, gesetzesnummer=norm.gesetzesnummer, kurztitel="Unpassender Wüstentitel",
        titel="", abschnitt="", stand=norm.stand, quelle=norm.quelle, rohdaten=daten,
        inhalt_hash=_hash(daten), importlauf=norm.importlauf,
    )
    AntragsFassung.objects.create(antrag=a, nummer=2, wortlaut="Zweite Fassung")
    neu = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    assert not neu.quellenkontext["quellen"] and len(neu.quellenkontext["auswahl"]["bestand_ids"]) == 1
    assert alt.quellenkontext["quellen"][0]["norm_id"] == norm.pk
    assert not auswahl.erfassen(neu.kontext, jetzt=norm.importlauf.begonnen_am - timedelta(seconds=1))["quellen"]


def test_anbieterausfall_archiviert_dieselbe_tatsaechliche_quelleneingabe(a, monkeypatch):  # noqa: F811
    job = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    def kaputt(*args):
        raise AnbieterFehler("Testausfall")
    monkeypatch.setattr(AttrappenAnbieter, "frage", kaputt)
    assert auftrag_ausfuehren(job.pk) == "verschoben"
    job.refresh_from_db()
    assert job.lauf.kontext["quellen"] == job.quellenkontext and not job.lauf.erfolgreich


def test_erfassungsfehler_hemmt_nicht_und_macht_keinen_anbieteraufruf(a, monkeypatch, client):  # noqa: F811
    def kaputt(*args):
        with connection.cursor() as c:
            c.execute("SELECT * FROM absichtlich_fehlende_quellentabelle")
    monkeypatch.setattr(auswahl, "erfassen", kaputt)
    with transaction.atomic():
        job = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
        assert KIAuftrag.objects.count() == 1
    assert job.status == Auftragsstatus.GESCHEITERT and job.versuche == 0
    assert auftrag_ausfuehren(job.pk) == "uebersprungen" and not KILauf.objects.exists()
    html = client.get(reverse("verfahren:antrag", args=[a.pk])).content.decode()
    assert "konnte nicht erfasst oder geprüft werden" in html and "alle Versuche aufgebraucht" not in html


def test_parameter_null_friert_ehrlich_begrenzte_leere_quellen_ein(a, norm):  # noqa: F811
    Parameter.objects.update_or_create(schluessel="quellenkontext-hoechstzahl", defaults={"wert": "0"})
    a.titel = norm.kurztitel
    a.save(update_fields=["titel"])
    job = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    assert job.quellenkontext["quellen"] == [] and job.quellenkontext["hoechstzahl"] == 0
    assert job.quellenkontext["auswahl"]["treffer_begrenzt"]


def test_brief_nennt_quellenhash_des_tatsaechlichen_laufs(a, norm, mailoutbox):  # noqa: F811
    from mitglieder.post import rechtsbezug_brief
    a.titel = norm.kurztitel
    a.save(update_fields=["titel"])
    job = einreihen(Zweck.RECHTSBEZUG, a, a.eingebracht_von)
    assert auftrag_ausfuehren(job.pk) == "erledigt"
    assert rechtsbezug_brief(a.eingebracht_von, a)
    assert job.quellenkontext["sha256"] in mailoutbox[-1].body
    assert "nicht gegen diese Quellen verifiziert" in mailoutbox[-1].body


def test_beschaedigter_quellenstand_ruft_keinen_anbieter_auf(a, monkeypatch):  # noqa: F811
    stand = auswahl.erfassen(text_festhalten(a))
    stand["sha256"] = "0" * 64
    job = KIAuftrag.objects.create(zweck=Zweck.RECHTSBEZUG, antrag=a, angefordert_von=a.eingebracht_von,
                                  fassung_nummer=1, quellenkontext=stand)
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: pytest.fail("Beschädigter Kontext wurde gesendet"))
    assert auftrag_ausfuehren(job.pk) == "verschoben"
    assert not KILauf.objects.exists() and quellenstand(stand)["zustand"] == "fehler"


def test_quellen_einer_anderen_textfassung_werden_nicht_als_passender_kontext_gesendet(a, monkeypatch):  # noqa: F811
    ursprung = text_festhalten(a)
    stand = auswahl.erfassen(ursprung)
    AntragsFassung.objects.create(antrag=a, nummer=2, wortlaut="Anderer Wortlaut")
    job = KIAuftrag.objects.create(
        zweck=Zweck.RECHTSBEZUG, antrag=a, angefordert_von=a.eingebracht_von, fassung_nummer=2,
        kontext=text_festhalten(a), quellenkontext=stand,
    )
    monkeypatch.setattr(AttrappenAnbieter, "frage", lambda *args: pytest.fail("Quellen wurden einem anderen Text zugeordnet"))
    assert auftrag_ausfuehren(job.pk) == "verschoben"
    assert not KILauf.objects.exists()
    assert quellenstand(stand, text_sha256=job.kontext["sha256"])["zustand"] == "fehler"
