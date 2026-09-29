"""Sperrtests der Parameterverwaltung (Prüfung 0.50.0, P-43): Gast → Anmeldung, Mitglied ohne
Adminrecht → 403 ohne Wirkung, Admin → die Handlung geschieht (Sperren immer testen)."""

import pytest
from django.urls import reverse

from parameter.models import Parameter, erstbestand_sicherstellen
from verfahren.models import AuditEintrag, Verfahrensordnung
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

ZIELE = {
    "parameter:verwaltung_aktion": lambda lage: {"parameter": lage["eintrag"].pk, "wert": "7", "grund": "Probe."},
    "parameter:verwaltung_ordnung_entwurf": lambda lage: {},
    "parameter:verwaltung_ordnung_inkraft": lambda lage: {"ordnung": lage["fassung"].pk, "grund": "Probe."},
}


@pytest.fixture
def lage(ordnung):  # noqa: F811
    erstbestand_sicherstellen()
    Parameter.objects.filter(schluessel="verfahren-abstimmung-tage").update(wert="30")  # Register ≠ Ordnung
    fassung = Verfahrensordnung.objects.create(
        policy_id=ordnung.policy_id, version=2, regeln=ordnung.regeln, aktiv=False
    )
    return {"eintrag": Parameter.objects.get(schluessel="gremien-review-tage"), "fassung": fassung}


def _stand():
    return (
        list(Parameter.objects.order_by("pk").values_list("schluessel", "wert")),
        list(Verfahrensordnung.objects.order_by("pk").values_list("pk", "aktiv")),
        AuditEintrag.objects.count(),
    )


@pytest.mark.parametrize("name", ZIELE)
def test_gast_und_mitglied_bleiben_draussen(client, lage, name):
    vorher = _stand()
    antwort = client.post(reverse(name), ZIELE[name](lage))
    assert antwort.status_code == 302 and antwort.url == reverse("mitglieder:login")

    client.force_login(mitglied_anlegen("mitglied"))
    assert client.post(reverse(name), ZIELE[name](lage)).status_code == 403
    assert _stand() == vorher


def test_admin_aendert_erzeugt_und_setzt_in_kraft(client, lage):
    admin = mitglied_anlegen("admin")
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    zurueck = reverse("parameter:verwaltung")

    antwort = client.post(reverse("parameter:verwaltung_aktion"), ZIELE["parameter:verwaltung_aktion"](lage))
    assert antwort.status_code == 302 and antwort.url == zurueck
    lage["eintrag"].refresh_from_db()
    assert lage["eintrag"].wert == "7"

    zahl = Verfahrensordnung.objects.count()
    antwort = client.post(reverse("parameter:verwaltung_ordnung_entwurf"))
    assert antwort.status_code == 302 and antwort.url == zurueck
    assert Verfahrensordnung.objects.count() == zahl + 1

    antwort = client.post(
        reverse("parameter:verwaltung_ordnung_inkraft"), ZIELE["parameter:verwaltung_ordnung_inkraft"](lage)
    )
    assert antwort.status_code == 302 and antwort.url == zurueck
    lage["fassung"].refresh_from_db()
    assert lage["fassung"].aktiv is True
