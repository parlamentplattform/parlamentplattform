"""Gesamtprüfung 18.11.2026, zweite Behebungsrunde — Nachweis, Anzeige und Schutz vor stillem
Überschreiben in den Räten. An Mehrheiten, Fristen, Besetzung und Wirkung der Beschlüsse ändert
sich nichts; die Tests halten fest, was die Kette und die öffentlichen Seiten davon berichten."""

import pytest

from gremien.models import Gremium, Rolle
from gremien.test_pruefung import korat_beschliessen, korat_lage, pruef_lage
from gremien.test_werkstatt import ordnung  # noqa: F401
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db

#: Schlüssel, unter denen ein Ereignis eine Person nennen könnte (vgl. `verfahren.audit_oeffentlich`).
PERSONENSCHLUESSEL = ('mitglied', 'durch', 'konten', 'angelegt_von', 'name', 'grund')


def ereignisse(typ, **felder):
    return [
        e.ereignis
        for e in AuditEintrag.objects.order_by('lfd')
        if e.ereignis.get('typ') == typ and all(e.ereignis.get(k) == v for k, v in felder.items())
    ]


# --- GP-037 · Gremienhandlungen ohne Audit-Eintrag -------------------------------------------


def test_der_pruefbeschluss_steht_als_angelegt_in_der_kette(client, ordnung):  # noqa: F811
    """GP-037: Der Prüfbeschluss der Gruppe 2 entstand ohne Eintrag — als einziger Beschluss der Räte.
    Er trägt dieselbe Art wie alle anderen (`gremienbeschluss_angelegt`) und nennt niemanden."""
    antrag, entwurf, er, gruppe2, beschluss = pruef_lage(client, ordnung)
    eintraege = ereignisse('gremienbeschluss_angelegt', beschluss=beschluss.pk)
    assert len(eintraege) == 1
    eintrag = eintraege[0]
    assert eintrag['gremium'] == Gremium.EXPERTENRAT_2.value and eintrag['anlass'] == 'pruefung'
    assert eintrag['antrag'] == antrag.pk and eintrag['nummer'] == beschluss.nummer
    assert not set(eintrag) & set(PERSONENSCHLUESSEL)
    # Ein zweiter Lauf legt weder einen zweiten Beschluss noch einen zweiten Eintrag an.
    entwurf.fortschreiben(antrag)
    assert len(ereignisse('gremienbeschluss_angelegt', anlass='pruefung')) == 1


def test_der_austausch_beendet_jede_rolle_mit_eintrag(client, ordnung):  # noqa: F811
    """GP-037: Gibt der Koordinationsrat dem Austausch statt, enden die Rollen der Gruppe 1 für diesen
    Antrag. Je Rolle steht das in der Kette — mit der Beschlussnummer, ohne Personenwert."""
    antrag, entwurf, er, korat = korat_lage(client, ordnung)
    beschluss = korat_beschliessen(client, korat, entwurf.pruefungen.get(), 'dafuer', 'Die Zweifel wiegen schwer.')
    beschluss.refresh_from_db()
    beendet = list(Rolle.objects.filter(mitglied__in=er, gremium=Gremium.EXPERTENRAT_1))
    assert beendet and all(not r.aktiv for r in beendet)
    eintraege = ereignisse('rolle_beendet', beschluss=beschluss.pk)
    assert sorted(e['rolle'] for e in eintraege) == sorted(r.pk for r in beendet)
    for eintrag in eintraege:
        assert eintrag['anlass'] == 'austausch' and eintrag['nummer'] == beschluss.nummer
        assert eintrag['antrag'] == antrag.pk and eintrag['gremium'] == Gremium.EXPERTENRAT_1.value
        assert not set(eintrag) & set(PERSONENSCHLUESSEL)
