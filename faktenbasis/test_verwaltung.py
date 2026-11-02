"""Rechte, ausdrücklicher Einzelabruf, Audit und gemeinsamer Schutz ohne Netz."""

from datetime import UTC, datetime, timedelta
from io import StringIO

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test import Client
from django.urls import reverse
from django.utils import translation

from faktenbasis import abrufschutz, importieren, volltext
from faktenbasis.models import AbrufSperre, Norm, NormTextAbruf, RisImport
from faktenbasis.ris import RisFehler, antwort_parsen
from faktenbasis.test_ris import NUMMER, STAND, beispiel
from faktenbasis.test_xmltext import xml_beispiel
from mitglieder.models import Identitaetsstufe, Mitgliedsstatus
from parameter.models import Parameter
from verfahren.audit_oeffentlich import ereignis_oeffentlich
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


@pytest.fixture
def abrufe(monkeypatch):
    uhr = [datetime(2026, 11, 2, 21, 0, tzinfo=UTC)]
    monkeypatch.setattr(abrufschutz, "_jetzt", lambda: uhr[0])
    daten = beispiel()
    # Dasselbe NOR wie im XML-Testbeispiel für beide Übernahmewege.
    import json

    from faktenbasis.test_xmltext import RIS_ID
    daten = json.loads(json.dumps(daten).replace("NOR11000363", RIS_ID))
    protokoll = []
    def meta(*args):
        protokoll.append(("metadaten", args))
        return antwort_parsen(daten, NUMMER)
    def text(url):
        protokoll.append(("text", url))
        return xml_beispiel()
    monkeypatch.setattr(importieren, "abrufen", meta)
    monkeypatch.setattr(volltext, "abrufen", text)
    return uhr, protokoll


def admin(client, **werte):
    person = mitglied_anlegen()
    person.ist_admin = True
    for name, wert in werte.items():
        setattr(person, name, wert)
    person.save()
    client.force_login(person)
    return person


def anfrage(client):
    return client.post(reverse("faktenbasis:verwaltung"), {"gesetzesnummer": NUMMER, "stand": STAND.isoformat()})


@pytest.mark.parametrize("wer", ["gast", "mitglied", "ungeprueft", "pausiert", "testkonto", "inaktiv"])
def test_rechte_vor_jedem_abruf_auch_bei_fremder_zielkennung(client, abrufe, wer):
    if wer == "mitglied":
        client.force_login(mitglied_anlegen())
    elif wer != "gast":
        admin(client, **{
            "ungeprueft": {"identitaetsstufe": Identitaetsstufe.UNGEPRUEFT},
            "pausiert": {"status": Mitgliedsstatus.PAUSIERT},
            "testkonto": {"testkonto": True}, "inaktiv": {"is_active": False},
        }[wer])
    erwartung = 302 if wer in {"gast", "inaktiv"} else 403
    assert client.get(reverse("faktenbasis:verwaltung")).status_code == erwartung
    assert anfrage(client).status_code == erwartung
    assert client.post(reverse("faktenbasis:dokumenttext_abrufen", args=[99999])).status_code == erwartung
    assert not abrufe[1] and not RisImport.objects.exists() and not AbrufSperre.objects.exists()
    assert "Amtliche Quelle übernehmen" not in client.get(reverse("faktenbasis:index")).content.decode()


def test_formular_get_ist_lesend_post_importiert_einmal_mit_audit(client, abrufe):
    person = admin(client)
    get = client.get(reverse("faktenbasis:verwaltung"))
    assert get.status_code == 200 and "no-store" in get["Cache-Control"]
    assert not AbrufSperre.objects.exists() and not abrufe[1]
    assert anfrage(client).status_code == 302
    assert len(abrufe[1]) == 1 and Norm.objects.count() == 1
    ereignis = AuditEintrag.objects.last().ereignis
    assert ereignis["durch"] == person.pk and ereignis["aktion"] == "faktenbasis_metadaten"
    assert ereignis_oeffentlich(ereignis)[0]["durch"] == "•" and "salz" in ereignis
    assert person.email not in str(ereignis) and "sperrcode" not in str(ereignis)
    assert "Diesen Dokumenttext einmal abrufen" in client.get(reverse("faktenbasis:norm", args=[Norm.objects.get().pk])).content.decode()


@pytest.mark.parametrize("nummer,stand", [
    ("123", "2026-11-02"), ("１００００３６２", "2026-11-02"),
    ("https://evil.invalid", "2026-11-02"), (NUMMER, "2026-02-30"), (NUMMER, "20261102"),
])
def test_formfehler_schreiben_und_rufen_nichts_ab(client, abrufe, nummer, stand):
    admin(client)
    antwort = client.post(reverse("faktenbasis:verwaltung"), {"gesetzesnummer": nummer, "stand": stand})
    assert antwort.status_code == 200 and antwort.context["formular"].errors
    assert not abrufe[1] and not AbrufSperre.objects.exists() and not AuditEintrag.objects.exists()


def test_csrf_sperrt_beide_aktionen_und_get_des_textes_schreibt_nicht(client, abrufe):
    person = admin(client)
    gesichert = Client(enforce_csrf_checks=True)
    gesichert.force_login(person)
    assert anfrage(gesichert).status_code == 403
    assert gesichert.post(reverse("faktenbasis:dokumenttext_abrufen", args=[99999])).status_code == 403
    assert client.get(reverse("faktenbasis:dokumenttext_abrufen", args=[99999])).status_code == 405
    assert not abrufe[1]


def test_gemeinsamer_schutz_fuer_web_und_beide_cli_befehle(client, abrufe):
    admin(client)
    uhr, protokoll = abrufe
    anfrage(client)
    norm = Norm.objects.get()
    url = reverse("faktenbasis:dokumenttext_abrufen", args=[norm.pk])
    assert client.post(url).status_code == 302
    assert len(protokoll) == 1 and not NormTextAbruf.objects.exists()
    with pytest.raises(CommandError, match="abruf_belegt"):
        call_command("ris_volltext", norm=norm.pk, stdout=StringIO())
    uhr[0] += timedelta(seconds=2)
    call_command("ris_volltext", norm=norm.pk, stdout=StringIO())
    assert len(protokoll) == 2 and NormTextAbruf.objects.get().erfolgreich
    with pytest.raises(CommandError, match="abruf_belegt"):
        call_command("ris_import", gesetzesnummer=NUMMER, stand=STAND.isoformat(), stdout=StringIO())
    Parameter.objects.create(schluessel="faktenbasis-manuelle-abrufe-je-stunde", wert="2")
    uhr[0] += timedelta(seconds=2)
    with pytest.raises(CommandError, match="abruf_kontingent"):
        call_command("ris_import", gesetzesnummer=NUMMER, stand=STAND.isoformat(), stdout=StringIO())
    assert len(protokoll) == 2 and RisImport.objects.count() == 1 and AbrufSperre.objects.get().anzahl == 2


def test_abruffehler_wird_erhalten_und_fremder_servertext_nicht_ausgegeben(client, abrufe, monkeypatch):
    admin(client)
    anfrage(client)
    abrufe[0][0] += timedelta(seconds=2)
    def kaputt(*args):
        raise RisFehler("abruf")
    monkeypatch.setattr(importieren, "abrufen", kaputt)
    antwort = client.post(reverse("faktenbasis:verwaltung"), {"gesetzesnummer": NUMMER, "stand": STAND.isoformat()}, follow=True)
    assert antwort.status_code == 200 and "Bereits gespeicherte Angaben bleiben erhalten" in antwort.content.decode()
    assert not RisImport.objects.first().erfolgreich and Norm.objects.count() == 1
    assert AuditEintrag.objects.last().ereignis["fehlercode"] == "abruf"


def test_oeffentliche_nachlese_bleibt_ohne_schreibweg(client, abrufe):
    importieren.importieren(NUMMER, STAND)
    norm = Norm.objects.get()
    detail = reverse("faktenbasis:norm", args=[norm.pk])
    assert "Diesen Dokumenttext einmal abrufen" not in client.get(detail).content.decode()
    assert client.post(detail, {}).status_code == 405
    assert client.post(reverse("faktenbasis:index"), {}).status_code == 405


@pytest.mark.django_db(transaction=True)
def test_verwaltungsabruf_haelt_keine_datenbanktransaktion_offen(client, abrufe, monkeypatch):
    admin(client)
    original = importieren.abrufen
    def beobachten(*args):
        assert not connection.in_atomic_block
        return original(*args)
    monkeypatch.setattr(importieren, "abrufen", beobachten)
    assert anfrage(client).status_code == 302
    assert Norm.objects.count() == 1


def test_offener_anmeldeadresswechsel_sperrt_den_abruf(client, abrufe, monkeypatch):
    person = admin(client)
    monkeypatch.setattr(type(person), "adresswechsel_offen", property(lambda self: True))
    assert anfrage(client).status_code == 403
    assert not abrufe[1]


def test_formular_auch_auf_englisch_ohne_sprachleck(client):
    admin(client)
    with translation.override("en"):
        antwort = client.get(reverse("faktenbasis:verwaltung"), HTTP_ACCEPT_LANGUAGE="en")
    assert "Import an official source" in antwort.content.decode()
    assert "Retrieve metadata once" in antwort.content.decode()


@pytest.mark.parametrize("nummer,stand", [("x", STAND), (NUMMER, "2026-11-02")])
def test_fachoperation_prueft_argumente_vor_der_reservierung(abrufe, nummer, stand):
    with pytest.raises(RisFehler):
        importieren.importieren(nummer, stand)
    assert not AbrufSperre.objects.exists() and not abrufe[1]
