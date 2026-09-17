from datetime import timedelta

import pytest
from django.core import mail
from django.utils import timezone

from mitglieder.models import Identitaetsstufe, Postauftrag
from mitglieder.post import willkommen_senden
from mitglieder.postausgang import zustellen
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


def test_versand_erst_nach_commit_und_nur_einmal(django_capture_on_commit_callbacks):
    m = mitglied_anlegen("post-neu", stufe=Identitaetsstufe.UNGEPRUEFT)
    m.first_name = "Anna"
    m.save()
    with django_capture_on_commit_callbacks(execute=True):
        assert willkommen_senden(m)
        assert mail.outbox == []
    a = Postauftrag.objects.get(mitglied=m)
    assert a.erledigt and len(mail.outbox) == 1
    assert len(mail.outbox[0].attachments) == 1
    assert not zustellen(a.pk)
    assert len(mail.outbox) == 1


def test_smtp_fehler_bleibt_offen_und_wird_wiederholt(monkeypatch, django_capture_on_commit_callbacks):
    m = mitglied_anlegen("post-fehler")
    m.first_name = "Anna"
    m.save()
    with monkeypatch.context() as patch:
        patch.setattr("mitglieder.post.EmailMessage.send", lambda *a, **kw: 0)
        with django_capture_on_commit_callbacks(execute=True):
            willkommen_senden(m)
    a = Postauftrag.objects.get(mitglied=m)
    assert not a.erledigt and a.versandt_am is None
    assert zustellen(a.pk, timezone.now() + timedelta(hours=2))
    assert len(mail.outbox) == 1


def test_pdf_wird_getrennt_nachgeliefert(monkeypatch, django_capture_on_commit_callbacks):
    m = mitglied_anlegen("post-pdf")
    m.first_name = "Anna"
    m.save()
    with monkeypatch.context() as patch:
        patch.setattr("mitglieder.post._ausweis_anhang", lambda m: None)
        with django_capture_on_commit_callbacks(execute=True):
            willkommen_senden(m)
    a = Postauftrag.objects.get(mitglied=m)
    assert a.versandt_am and not a.erledigt
    assert len(mail.outbox) == 1 and not mail.outbox[0].attachments
    assert zustellen(a.pk, timezone.now() + timedelta(hours=2))
    assert len(mail.outbox) == 2 and len(mail.outbox[1].attachments) == 1
    assert not zustellen(a.pk)


def test_rollback_erzeugt_keinen_brief(django_capture_on_commit_callbacks):
    from django.db import transaction
    m = mitglied_anlegen("rollback")
    with django_capture_on_commit_callbacks(execute=True):
        with pytest.raises(ValueError), transaction.atomic():
            willkommen_senden(m)
            raise ValueError("Abbruch")
    assert not Postauftrag.objects.filter(mitglied=m).exists()
    assert mail.outbox == []


def test_reservierter_auftrag_wird_nicht_parallel_gesendet():
    m = mitglied_anlegen("reserviert")
    a = Postauftrag.objects.create(mitglied=m, art="willkommen",
        gesperrt_bis=timezone.now()+timedelta(minutes=5), sperrcode="anderer-worker")
    assert not zustellen(a.pk)
    assert mail.outbox == []


def test_austritt_vor_wiederholung_verhindert_versand():
    from mitglieder.models import Mitgliedsstatus
    m = mitglied_anlegen("austritt-post")
    a = Postauftrag.objects.create(mitglied=m, art="willkommen")
    m.status = Mitgliedsstatus.AUSGETRETEN
    m.save(update_fields=["status"])
    assert not zustellen(a.pk)
    a.refresh_from_db()
    assert a.erledigt and mail.outbox == []


def test_ungepruefter_ausweis_zeigt_nur_ausstaendigen_status(client):
    from mitglieder.ausweis import ausweis_code_sicherstellen
    m = mitglied_anlegen("ausstaendig", stufe=Identitaetsstufe.UNGEPRUEFT)
    code = ausweis_code_sicherstellen(m)
    html = client.get(f"/ausweis/{m.pk}/{code}/").content.decode()
    assert 'data-stand="ausstaendig"' in html
    assert m.email not in html
    assert 'data-stand="ungueltig"' in client.get(f"/ausweis/{m.pk}/falsch/").content.decode()
    assert client.get('/ausweis/999999999999999999999999/abcdef/').status_code == 200


def test_probe_geht_nur_an_eigenes_konto_ohne_poststempel(client, django_capture_on_commit_callbacks):
    m = mitglied_anlegen("probe-eigen")
    m.first_name = "Michael"
    m.last_name = "Hackl"
    m.save()
    fremd = mitglied_anlegen("probe-fremd")
    client.force_login(m)
    assert client.get('/profil/ausweis/mail/').status_code == 405
    with django_capture_on_commit_callbacks(execute=True):
        assert client.post('/profil/ausweis/mail/', {"mitglied": fremd.pk, "email": fremd.email}).status_code == 302
    assert len(mail.outbox) == 1 and mail.outbox[0].to == [m.email]
    assert mail.outbox[0].subject.startswith("Vorschau:") and len(mail.outbox[0].attachments) == 1
    m.refresh_from_db()
    assert m.willkommen_post_am is None and m.freischaltung_post_am is None
    assert 'data-ausweis-probe="versandt"' in client.get("/profil/").content.decode()
    with django_capture_on_commit_callbacks(execute=True):
        client.post('/profil/ausweis/mail/')
    assert len(mail.outbox) == 1


def test_gast_kann_keine_probe_anfordern(client):
    assert client.post('/profil/ausweis/mail/').status_code == 302
    assert not Postauftrag.objects.exists()
