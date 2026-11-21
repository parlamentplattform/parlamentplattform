"""GP-129 in den Gremien: Handlung und Audit-Eintrag gemeinsam oder gar nicht.

Scheitert der Eintrag in die Kette, darf von der Handlung nichts zurückbleiben — sonst stünde eine
Gremienhandlung in der Datenbank, die das öffentliche Protokoll nie erfährt (CLAUDE.md § 4)."""

from __future__ import annotations

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import (
    Entwurf,
    EntwurfsStatus,
    GremienBeschluss,
    Hinweis,
    HinweisStatus,
    Pruefung,
    Ueberlastungsmeldung,
)
from gremien.test_koordination import _ausgewerteter_test, korat
from gremien.test_werkstatt import einreichen, mitglied_anlegen, ordnung, werkstatt_lage  # noqa: F401
from parameter.models import TestStatus as ParameterTeststatus
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db


class KetteGestoert(RuntimeError):
    pass


@pytest.fixture
def scheitert(monkeypatch):
    """Lässt den Audit-Eintrag eines Typs scheitern; alle anderen gehen durch."""
    original = AuditEintrag.anhaengen.__func__

    def setzen(typ: str):
        def anhaengen(cls, ereignis):
            if ereignis.get('typ') == typ:
                raise KetteGestoert(typ)
            return original(cls, ereignis)

        monkeypatch.setattr(AuditEintrag, 'anhaengen', classmethod(anhaengen))

    return setzen


def test_fenster_oeffnen_bleibt_ohne_eintrag_ungeschehen(client, ordnung, scheitert):  # noqa: F811
    antrag, _u, er = werkstatt_lage(ordnung)
    client.force_login(er[0])
    scheitert('entwurfsfenster_geoeffnet')
    with pytest.raises(KetteGestoert):
        client.post(reverse('gremien:fenster_aktion', args=[antrag.pk]), {'aktion': 'oeffnen'})
    assert not Entwurf.objects.filter(antrag=antrag).exists()


def test_einreichungsbeschluss_bleibt_ohne_eintrag_ungeschehen(client, ordnung, scheitert):  # noqa: F811
    antrag, _u, er = werkstatt_lage(ordnung)
    client.force_login(er[0])
    aktion = reverse('gremien:fenster_aktion', args=[antrag.pk])
    client.post(aktion, {'aktion': 'oeffnen'})
    scheitert('gremienbeschluss_angelegt')
    with pytest.raises(KetteGestoert):
        client.post(aktion, {'aktion': 'einreichung'})
    assert not GremienBeschluss.objects.filter(antrag=antrag).exists()


def test_vollzugsbezug_und_nachlosung_gemeinsam_oder_gar_nicht(client, ordnung, scheitert):  # noqa: F811
    """Ohne Fachliste kann Gruppe 2 nicht gelost werden; scheitert dieser Eintrag, bleibt auch der
    Vollzugsbezug, wie er war."""
    antrag, _u, er = werkstatt_lage(ordnung)
    client.force_login(er[0])
    aktion = reverse('gremien:fenster_aktion', args=[antrag.pk])
    client.post(aktion, {'aktion': 'oeffnen'})
    scheitert('auslosung_nicht_moeglich')
    with pytest.raises(KetteGestoert):
        client.post(aktion, {'aktion': 'vollzugsbezug', 'vollzugsbezug': 'ja'})
    assert Entwurf.objects.get(antrag=antrag).vollzugsbezug is False
    assert not any(e.ereignis.get('typ') == 'vollzugsbezug_gesetzt' for e in AuditEintrag.objects.all())


def test_hinweis_zum_beschluss_bleibt_ohne_eintrag_offen(client, scheitert):
    leute = korat()
    test, _beschluss = _ausgewerteter_test(client, leute)
    hinweis = Hinweis.objects.filter(parametertest=test, status=HinweisStatus.OFFEN).get()
    vorher = GremienBeschluss.objects.count()
    client.force_login(leute[0])
    scheitert('hinweis_erledigt')
    with pytest.raises(KetteGestoert):
        client.post(reverse('gremien:koordination_hinweis', args=[hinweis.pk]), {'aktion': 'beschluss'})
    hinweis.refresh_from_db()
    test.refresh_from_db()
    assert hinweis.status == HinweisStatus.OFFEN and test.einfuehrung_beschluss_id is None
    assert GremienBeschluss.objects.count() == vorher


def test_einfuehrungsbeschluss_bleibt_ohne_eintrag_ungeschehen(client, scheitert):
    leute = korat()
    test, _beschluss = _ausgewerteter_test(client, leute)
    vorher = GremienBeschluss.objects.count()
    client.force_login(leute[0])
    scheitert('gremienbeschluss_angelegt')
    with pytest.raises(KetteGestoert):
        client.post(reverse('gremien:koordination_test', args=[test.pk]), {'aktion': 'einfuehrung'})
    test.refresh_from_db()
    assert test.einfuehrung_beschluss_id is None and GremienBeschluss.objects.count() == vorher


def test_verwerfen_eines_tests_bleibt_ohne_eintrag_ungeschehen(client, scheitert):
    leute = korat()
    test, _beschluss = _ausgewerteter_test(client, leute)
    client.force_login(leute[0])
    scheitert('parametertest_verworfen')
    with pytest.raises(KetteGestoert):
        client.post(reverse('gremien:koordination_test', args=[test.pk]), {'aktion': 'verwerfen', 'grund': 'Kein Effekt.'})
    test.refresh_from_db()
    assert test.status == ParameterTeststatus.AUSGEWERTET and 'Verworfen' not in test.auswertung
    assert Hinweis.objects.filter(parametertest=test, status=HinweisStatus.OFFEN).exists()


def test_ueberlastungsmeldung_bleibt_ohne_eintrag_ungeschehen(client, scheitert):
    admin = mitglied_anlegen('admin')
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    scheitert('ueberlastung_gemeldet')
    with pytest.raises(KetteGestoert):
        client.post(reverse('gremien:ueberlastung_melden'), {'stelle': 'Berichtswesen', 'begruendung': 'Zu viele Aufträge.'})
    assert not Ueberlastungsmeldung.objects.exists()


def test_fortschreiben_auf_der_pruefseite_bleibt_ohne_eintrag_ungeschehen(client, ordnung, scheitert):  # noqa: F811
    """Ohne besetzte Gruppe 2 und nach verstrichener Prüffrist schreibt die Prüfseite den Vorschlag fort."""
    antrag, _u, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er, vollzugsbezug=True)
    tage = antrag.policy().pruefung_tage
    Entwurf.objects.filter(pk=entwurf.pk).update(eingereicht_am=timezone.now() - timedelta(days=tage, hours=1))
    admin = mitglied_anlegen('admin')
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    scheitert('pruefung_frist_verstrichen')
    with pytest.raises(KetteGestoert):
        client.get(reverse('gremien:pruefung'))
    entwurf.refresh_from_db()
    assert entwurf.status == EntwurfsStatus.PRUEFUNG and not Pruefung.objects.filter(entwurf=entwurf).exists()
