"""`demo_seed` läuft bei jedem Deploy (render.yaml) — auf der Produktionsdatenbank.

Deshalb muss jeder seiner Wächter idempotent sein (CLAUDE.md § 7, DoD 7) und darf nie im Namen
echter Menschen handeln. Befund #18: Der Hervorhebungs-Beschluss nahm ALLE aktiven Rollen des
Integritätsrats. Befund #65: Der Wächter des Abstimmungs-Chat-Blocks hing an einem Status, der
nach 14 Tagen von selbst kippt."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from gremien.models import Anlass, Entwurf, GremienBeschluss, GremienStimme, Gremium, Rolle, standard_ende
from verfahren.management.commands.demo_seed import TESTLAUF_TITEL
from verfahren.models import Antrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


def test_die_demo_stimmt_nie_im_namen_echter_ratsmitglieder_ab():
    """Ein echtes Mitglied sitzt im Integritätsrat, und ein Deploy läuft: Bis 0.45 entstand ein
    Beschluss mit seiner Stimme „dafür“ und erfundener Begründung — satzungsgemäß nicht mehr
    löschbar. Jetzt geschieht nichts, solange nicht ausschließlich Demo-Mitglieder im Rat sitzen."""
    echt = mitglied_anlegen("echtes-mitglied")
    Rolle.objects.create(mitglied=echt, gremium=Gremium.INTEGRITAETSRAT, endet_am=standard_ende(), bestaetigt=True)
    call_command("demo_seed", verbosity=0)
    call_command("demo_seed", verbosity=0)
    assert not GremienStimme.objects.filter(mitglied=echt).exists()
    assert not GremienBeschluss.objects.filter(anlass=Anlass.HERVORHEBUNG, angelegt_von=echt).exists()
    assert not Antrag.objects.filter(hervorgehoben=True).exists()


def test_der_demo_antrag_des_abstimmungschats_entsteht_nur_einmal():
    """Nach der Unterstützerfrist wertet die Schleife aus und der Status „unterstuetzer“ ist weg —
    der nächste Deploy legte den Antrag bis 0.45 ein zweites Mal an (und nichts wird gelöscht)."""
    call_command("demo_seed", verbosity=0)
    antrag = Antrag.objects.get(titel__startswith=TESTLAUF_TITEL)
    entwurf = Entwurf.objects.get(antrag=antrag)
    Entwurf.objects.filter(pk=entwurf.pk).update(review_frist=timezone.now() - timedelta(hours=1))
    antrag.refresh_from_db()
    antrag.fortschreiben()  # ein Besucher öffnet die Seite — die Schleife wertet aus
    entwurf.refresh_from_db()
    assert entwurf.status != "unterstuetzer"
    assert not Antrag.objects.filter(entwurf__status="unterstuetzer").exists()
    call_command("demo_seed", verbosity=0)
    assert Antrag.objects.filter(titel__startswith=TESTLAUF_TITEL).count() == 1
