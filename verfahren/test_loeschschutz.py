"""Verfahrensbezüge überleben jede Kontoänderung (Bestandsaufnahme A10, Schritt 2 · 0.52.0).

Kein Code löscht ein Mitglied — der Austritt anonymisiert (§ 8 Abs 4). Wer es doch versucht (Shell,
ein künftiger Admin-Pfad), darf Unterstützungen, die Brücke Mitglied ↔ Pseudonym und die Reaktionen im
Abstimmungs-Chat nicht still mitnehmen: Zähler, Schwellen und der Ein-Stimme-Schutz hingen daran."""

import pytest
from django.db.models import ProtectedError

from verfahren.models import Kommentar, Reaktion, StimmRegister, Unterstuetzung, antrag_einbringen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def test_eine_unterstuetzung_verhindert_das_loeschen(ordnung):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen("steller"), **ANTRAG, ordnung=ordnung)
    helfer = mitglied_anlegen("helfer")
    Unterstuetzung.objects.create(antrag=antrag, mitglied=helfer)
    with pytest.raises(ProtectedError):
        helfer.delete()
    assert Unterstuetzung.objects.filter(mitglied=helfer).exists()


def test_die_bruecke_zum_pseudonym_verhindert_das_loeschen(ordnung):  # noqa: F811
    from verfahren.models import stimme_abgeben

    leute = [mitglied_anlegen(f"w{i}") for i in range(4)]
    antrag = antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung)
    in_abstimmung_bringen(antrag, leute[1:3])
    antrag.refresh_from_db()
    stimme_abgeben(antrag, leute[3], "ja")
    with pytest.raises(ProtectedError):
        leute[3].delete()
    assert StimmRegister.objects.filter(mitglied=leute[3]).exists()


def test_eine_reaktion_verhindert_das_loeschen(ordnung):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen("steller2"), **ANTRAG, ordnung=ordnung)
    leserin = mitglied_anlegen("leserin")
    beitrag = Kommentar.objects.create(antrag=antrag, mitglied=None, text="Ein Beitrag.")
    Reaktion.objects.create(kommentar=beitrag, mitglied=leserin, art="zustimmung")
    with pytest.raises(ProtectedError):
        leserin.delete()
    assert Reaktion.objects.filter(mitglied=leserin).exists()


def test_ein_konto_ohne_verfahrensbezug_bleibt_loeschbar():
    """Kein Schutz um seiner selbst willen: Ein Konto, das nie mitgewirkt hat (etwa eine abgebrochene
    Registrierung), hält nichts fest, was ein Verfahren braucht."""
    niemand = mitglied_anlegen("niemand")
    niemand.delete()
