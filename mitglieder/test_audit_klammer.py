"""GP-129: Jede schreibende Handlung der App mitglieder steht mit ihrem Audit-Eintrag in einer Transaktion.

Je Stelle wird der Audit-Eintrag zum Scheitern gebracht; danach darf von der Handlung nichts
zurückbleiben (kein halbes Konto, kein Postauftrag ohne Protokoll, keine ungeprotokollierte Änderung)."""

from datetime import timedelta

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from mitglieder.models import Adresswechsel, Gemeinde, Identitaetsstufe, Mitglied, Postauftrag
from mitglieder.test_verwaltung import admin_anlegen
from mitglieder.test_views import ANMELDUNG, botschutz
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


class AuditGescheitert(RuntimeError):
    pass


@pytest.fixture(autouse=True)
def _gemeindeverzeichnis(db):
    from django.core.management import call_command

    call_command('gemeinden_laden')


@pytest.fixture
def audit_scheitert(monkeypatch):
    """audit_scheitert(typ, aktion=None): Ab jetzt wirft jeder passende Audit-Eintrag."""
    original = AuditEintrag.anhaengen

    def setzen(typ, aktion=None):
        def anhaengen(cls, ereignis, *args, **kwargs):
            if ereignis.get('typ') == typ and (aktion is None or ereignis.get('aktion') == aktion):
                raise AuditGescheitert(typ)
            return original(ereignis, *args, **kwargs)

        monkeypatch.setattr(AuditEintrag, 'anhaengen', classmethod(anhaengen))

    return setzen


def test_ausweiscode_bleibt_ohne_audit_unvergeben(audit_scheitert):
    from mitglieder.ausweis import ausweis_code_sicherstellen

    anna = mitglied_anlegen('anna')
    audit_scheitert('ausweis_ausgestellt')
    with pytest.raises(AuditGescheitert):
        ausweis_code_sicherstellen(anna)
    frisch = Mitglied.objects.get(pk=anna.pk)
    assert frisch.ausweis_code == '' and frisch.ausweis_ausgestellt_am is None and frisch.ausweis_schluessel is None


def test_regionspost_bleibt_ohne_audit_unbeauftragt(audit_scheitert, ordnung):  # noqa: F811
    from mitglieder.post import region_benachrichtigen, region_empfaenger
    from verfahren.models import antrag_einbringen

    ort = Gemeinde.objects.get(name='Eferding')
    for name in ('steller', 'leserin'):
        m = mitglied_anlegen(name, gemeinde=ort.name)
        Mitglied.objects.filter(pk=m.pk).update(wohnsitz=ort, post_einwilligung=True)
    steller = Mitglied.objects.get(username='steller')
    antrag = antrag_einbringen(steller, **ANTRAG, ordnung=ordnung, ebene='gemeinde', gebiet=ort.name)
    Postauftrag.objects.filter(art='neuer_antrag').delete()  # was das Einbringen selbst beauftragt hat
    assert region_empfaenger(antrag).exists()
    audit_scheitert('post_neuer_antrag')
    with pytest.raises(AuditGescheitert):
        region_benachrichtigen(antrag)
    assert not Postauftrag.objects.filter(art='neuer_antrag').exists()


def test_andere_geraete_abmelden_bleibt_ohne_audit_wirkungslos(client, audit_scheitert):
    anna = mitglied_anlegen('anna')
    kennwort_vorher = Mitglied.objects.get(pk=anna.pk).password
    client.force_login(anna)
    audit_scheitert('profil', 'sitzungen_beendet')
    with pytest.raises(AuditGescheitert):
        client.post(reverse('mitglieder:profil_sitzungen_beenden'))
    assert Mitglied.objects.get(pk=anna.pk).password == kennwort_vorher


def test_mitgliederpost_bleibt_ohne_audit_unbeauftragt(client, audit_scheitert):
    admin, bert = admin_anlegen('admina'), mitglied_anlegen('bert')
    client.force_login(admin)
    audit_scheitert('verwaltung', 'mitgliederpost')
    with pytest.raises(AuditGescheitert):
        client.post(reverse('mitglieder:verwaltung_mitglied', args=[bert.pk]), {'aktion': 'mitgliederpost'})
    assert not Postauftrag.objects.filter(mitglied=bert).exists()


def test_adresswechsel_bleibt_ohne_audit_unbeantragt_und_unverschickt(client, audit_scheitert):
    from mitglieder.verwaltung import _adresswechsel_beantragen

    admin, bert = admin_anlegen('admina'), mitglied_anlegen('bert')
    anfrage = client.get(reverse('mitglieder:verwaltung')).wsgi_request  # nur für build_absolute_uri
    anfrage.user = admin
    audit_scheitert('verwaltung', 'email_geaendert_beantragt')
    with pytest.raises(AuditGescheitert):
        _adresswechsel_beantragen(anfrage, bert, 'neu@example.org')
    assert not Adresswechsel.objects.filter(mitglied=bert).exists()
    assert mail.outbox == []


def test_beitragserinnerung_bleibt_ohne_audit_unbeauftragt(client, audit_scheitert):
    admin, bert = admin_anlegen('admina'), mitglied_anlegen('bert', tage=800)
    Mitglied.objects.filter(pk=bert.pk).update(
        post_einwilligung=True, beitrag_zuletzt_am=timezone.localdate() - timedelta(days=500)
    )
    client.force_login(admin)
    audit_scheitert('verwaltung', 'beitrag_erinnerung')
    with pytest.raises(AuditGescheitert):
        client.post(reverse('mitglieder:beitrag_erinnern'), {'mitglied': [bert.pk]})
    assert not Postauftrag.objects.filter(mitglied=bert, art='beitragserinnerung').exists()


def test_registrierung_bleibt_ohne_audit_ohne_konto_und_ohne_mail(client, audit_scheitert):
    daten = {**ANMELDUNG, **botschutz(client)}
    audit_scheitert('registrierung')
    with pytest.raises(AuditGescheitert):
        client.post(reverse('mitglieder:registrieren'), daten)
    assert not Mitglied.objects.filter(email=ANMELDUNG['email']).exists()
    assert mail.outbox == []


def test_bestaetigung_bleibt_ohne_audit_unwirksam_und_der_link_gueltig(client, audit_scheitert):
    from mitglieder.auth_flows import EinmalToken

    eva = mitglied_anlegen('eva', stufe=Identitaetsstufe.UNGEPRUEFT)
    Mitglied.objects.filter(pk=eva.pk).update(is_active=False, beitritt=None)
    token = EinmalToken.ausstellen(eva, EinmalToken.Zweck.BESTAETIGUNG)
    audit_scheitert('email_bestaetigt')
    with pytest.raises(AuditGescheitert):
        client.post(reverse('mitglieder:bestaetigen', args=[token]))
    frisch = Mitglied.objects.get(pk=eva.pk)
    assert frisch.is_active is False and frisch.beitritt is None and frisch.mitgliedsnummer is None
    assert EinmalToken.objects.filter(mitglied=eva, verbraucht_am__isnull=True).exists()
    assert '_auth_user_id' not in client.session
