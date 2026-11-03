"""Ein späterer Quellenstand darf keine Eingabe eines erhaltenen Auftrags ersetzen."""

import pytest
from django.core.exceptions import ValidationError

from faktenbasis.kontext import festhalten
from ki.models import KIAuftrag, Zweck
from ki.test_kontext_auftrag import a  # noqa: F401
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def altauftrag(antrag, **felder):
    return KIAuftrag.objects.create(zweck=Zweck.RECHTSBEZUG, antrag=antrag,
                                   angefordert_von=antrag.eingebracht_von, **felder)


def test_altbestand_bleibt_ohne_nachtraeglichen_quellennachweis(a):  # noqa: F811
    auftrag = altauftrag(a)
    assert auftrag.quellenkontext == {}
    auftrag.quellenkontext = festhalten([], hoechstzahl=3, textzeichen=50)
    with pytest.raises(ValidationError):
        auftrag.save(update_fields=["quellenkontext"])
    auftrag.refresh_from_db()
    assert auftrag.quellenkontext == {}


@pytest.mark.parametrize("weg", ["update", "bulk_update", "bulk_create"])
def test_mengenoperationen_koennen_die_quellen_eines_auftrags_nicht_ersetzen(a, weg):  # noqa: F811
    auftrag = altauftrag(a)
    neuer_stand = festhalten([], hoechstzahl=3, textzeichen=50)
    with pytest.raises(ValidationError):
        if weg == "update":
            KIAuftrag.objects.filter(pk=auftrag.pk).update(quellenkontext=neuer_stand)
        elif weg == "bulk_update":
            auftrag.quellenkontext = neuer_stand
            KIAuftrag.objects.bulk_update([auftrag], ["quellenkontext"])
        else:
            auftrag.quellenkontext = neuer_stand
            KIAuftrag.objects.bulk_create([auftrag], update_conflicts=True,
                                         update_fields=["quellenkontext"], unique_fields=["pk"])
    auftrag.refresh_from_db()
    assert auftrag.quellenkontext == {}


def test_neuer_auftrag_kann_den_stand_bei_anlage_festhalten_und_weiterlaufen(a):  # noqa: F811
    stand = festhalten([], hoechstzahl=3, textzeichen=50)
    auftrag = altauftrag(a, quellenkontext=stand)
    KIAuftrag.objects.filter(pk=auftrag.pk).update(versuche=1)
    auftrag.refresh_from_db()
    assert auftrag.quellenkontext == stand and auftrag.versuche == 1
