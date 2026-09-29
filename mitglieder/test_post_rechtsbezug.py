"""Der Brief „betroffene Gesetze“ (FB-K7, FB-H6): Er nennt den Kontextstand des Laufs — Datum in
Wiener Zeit und die geprüfte Fassung (§ 6 Abs 11 lit b), wie Karte und Erbschaft."""

import zoneinfo

import pytest
from django.core import mail

from ki.models import KILauf, Zweck
from ki.warteschlange import abarbeiten, einreihen
from mitglieder.postausgang import offene_zustellen
from verfahren.test_rechtsbezug_anzeige import _antrag, json_attrappe  # noqa: F401
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def test_brief_nennt_stand_und_fassung_des_laufs(json_attrappe, ordnung):  # noqa: F811
    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    abarbeiten()
    assert offene_zustellen() == 1
    lauf = KILauf.objects.get(zweck=Zweck.RECHTSBEZUG)
    stand = lauf.erstellt_am.astimezone(zoneinfo.ZoneInfo("Europe/Vienna")).strftime("%d.%m.%Y, %H:%M")
    brief = mail.outbox[-1].body
    assert f"Stand: {stand} · zu Fassung 1" in brief
