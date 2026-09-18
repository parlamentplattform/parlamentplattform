"""Bestandsbriefe nur durch Admins, passend zum Status und ohne Doppelversand."""
import pytest
from django.core import mail
from django.urls import reverse

from mitglieder.models import Identitaetsstufe, Mitgliedsstatus, Postauftrag
from mitglieder.test_ausweis import geprueftes_mitglied

pytestmark = pytest.mark.django_db


def adresse(person):
    return reverse("mitglieder:verwaltung_mitglied", args=[person.pk])


@pytest.mark.parametrize("geprueft", [False, True])
def test_nachholen_passt_zum_status_und_versendet_nur_einmal(client, django_capture_on_commit_callbacks, geprueft):
    admin = geprueftes_mitglied("adminpost", ist_admin=True)
    person = geprueftes_mitglied("bestandpost")
    if not geprueft:
        person.identitaetsstufe = Identitaetsstufe.UNGEPRUEFT
        person.save(update_fields=["identitaetsstufe"])
    client.force_login(admin)
    assert client.get(adresse(person)).status_code == 200
    assert not Postauftrag.objects.filter(mitglied=person).exists()
    for _ in range(2):
        with django_capture_on_commit_callbacks(execute=True):
            antwort = client.post(adresse(person), {"aktion": "mitgliederpost"})
        assert antwort.status_code == 302
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == [person.email]
    a = Postauftrag.objects.get(mitglied=person)
    assert a.art == ("freischaltung" if geprueft else "willkommen")
    assert a.erledigt and a.versandt_am and a.anhang_versandt_am
    assert "PDF versendet" in client.get(adresse(person)).content.decode()


@pytest.mark.parametrize("felder", [
    {"testkonto": True}, {"is_active": False}, {"email": ""},
    {"status": Mitgliedsstatus.AUSGETRETEN}, {"status": Mitgliedsstatus.AUSGESCHLOSSEN},
])
def test_unzulaessige_konten_erhalten_keine_post(client, django_capture_on_commit_callbacks, felder):
    admin = geprueftes_mitglied("adminpost", ist_admin=True)
    person = geprueftes_mitglied("bestandpost", **felder)
    client.force_login(admin)
    with django_capture_on_commit_callbacks(execute=True):
        client.post(adresse(person), {"aktion": "mitgliederpost"})
    assert not Postauftrag.objects.filter(mitglied=person).exists()
    assert len(mail.outbox) == 0


def test_mitglied_ohne_adminrechte_kann_keine_bestandspost_ausloesen(client):
    person = geprueftes_mitglied("bestandpost")
    url = adresse(person)
    assert client.post(url, {"aktion": "mitgliederpost"}).status_code == 302
    client.force_login(person)
    assert client.post(url, {"aktion": "mitgliederpost"}).status_code == 403
    assert not Postauftrag.objects.exists()
