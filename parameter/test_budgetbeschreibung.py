import pytest

from parameter.models import KI_MONAT_BESCHREIBUNG_ALT, Aenderung, Parameter, erstbestand_sicherstellen
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db


def test_nur_falscher_alter_systemtext_wird_mit_nachweis_berichtigt_wert_bleibt():
    p = Parameter.objects.create(schluessel="ki-monatstokens", wert="777", beschreibung=KI_MONAT_BESCHREIBUNG_ALT, quelle="Test")
    erstbestand_sicherstellen()
    p.refresh_from_db()
    assert p.wert == "777" and "Keine garantierte Geldobergrenze" in p.beschreibung
    beleg = AuditEintrag.objects.get(ereignis__typ="parameterbeschreibung_berichtigt").ereignis
    assert beleg["alte_beschreibung"] == KI_MONAT_BESCHREIBUNG_ALT and beleg["neue_beschreibung"] == p.beschreibung
    assert not Aenderung.objects.filter(parameter=p).exists()  # Keine fingierte Wertänderung.
    erstbestand_sicherstellen()
    assert AuditEintrag.objects.filter(ereignis__typ="parameterbeschreibung_berichtigt").count() == 1


def test_eigene_beschreibung_und_alle_budgets_bleiben_unveraendert():
    p = Parameter.objects.create(schluessel="ki-monatstokens", wert="0", beschreibung="Eigene belegte Erläuterung", quelle="Test")
    erstbestand_sicherstellen()
    p.refresh_from_db()
    assert p.wert == "0" and p.beschreibung == "Eigene belegte Erläuterung"
    assert not AuditEintrag.objects.filter(ereignis__typ="parameterbeschreibung_berichtigt").exists()
