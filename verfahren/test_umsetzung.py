"""Das Fortschreiben des Umsetzungsregisters über die Antragsseite (F-55, § 6 Abs 10)."""

import pytest
from django.urls import reverse

from verfahren.models import AuditEintrag, Vollzugseintrag
from verfahren.test_views_aktionen import ordnung  # noqa: F401
from verfahren.test_vollzug import admin_anlegen, angenommenen_antrag

pytestmark = pytest.mark.django_db


def test_gp173_unbekannter_stand_wird_als_solcher_gemeldet(client, ordnung):  # noqa: F811
    """GP-173 (ASR-16): Ein unbekannter Status hieß „Das Umsetzungsregister führt nur angenommene
    Anträge“ — auch beim angenommenen Antrag. Die Meldung nennt jetzt den Stand."""
    antrag, _leute = angenommenen_antrag(ordnung)
    client.force_login(admin_anlegen())
    vorher = AuditEintrag.objects.count()
    antwort = client.post(
        reverse('verfahren:vollzug', args=[antrag.pk]), {'status': 'erfunden', 'vermerk': 'x'}, follow=True
    )
    meldungen = [str(m) for m in antwort.context['messages']]
    assert any('erfunden' in m for m in meldungen), meldungen
    assert not any('nur angenommene' in m for m in meldungen)
    assert not Vollzugseintrag.objects.exists() and AuditEintrag.objects.count() == vorher
