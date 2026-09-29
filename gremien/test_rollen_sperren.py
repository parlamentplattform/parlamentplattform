"""Sperrtests der Rollenverwaltung (Prüfung 0.50.0, P-43): Gast → Anmeldung, Mitglied ohne
Adminrecht → 403 ohne Wirkung, Admin → die Berufung geschieht (Sperren immer testen)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import Gremium, Rolle
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


def _berufung(ziel) -> dict:
    return {
        "aktion": "berufen",
        "mitglied": ziel.pk,
        "gremium": Gremium.INTEGRITAETSRAT,
        "endet_am": (timezone.localdate() + timedelta(days=365)).isoformat(),
    }


@pytest.mark.parametrize("name", ["gremien:rollen", "gremien:rollen_aktion"])
def test_gast_und_mitglied_bleiben_draussen(client, name):
    ziel = mitglied_anlegen("ziel")
    senden, daten = (client.get, {}) if name == "gremien:rollen" else (client.post, _berufung(ziel))
    audit = AuditEintrag.objects.count()

    antwort = senden(reverse(name), daten)
    assert antwort.status_code == 302 and antwort.url == reverse("mitglieder:login")

    client.force_login(mitglied_anlegen("mitglied"))
    assert senden(reverse(name), daten).status_code == 403
    assert Rolle.objects.count() == 0 and AuditEintrag.objects.count() == audit


def test_admin_sieht_die_rollen_und_beruft(client):
    ziel = mitglied_anlegen("ziel")
    admin = mitglied_anlegen("admin")
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)

    assert client.get(reverse("gremien:rollen")).status_code == 200
    antwort = client.post(reverse("gremien:rollen_aktion"), _berufung(ziel))
    assert antwort.status_code == 302 and antwort.url == reverse("gremien:rollen")
    assert Rolle.objects.filter(mitglied=ziel, gremium=Gremium.INTEGRITAETSRAT).count() == 1


@pytest.mark.parametrize("aktion", ["bestaetigen", "beenden"])
def test_bestaetigen_und_beenden_sind_ebenso_gesperrt(client, aktion):
    """D-L6d (0.51.0): Die MV-Bestätigung hebt eine Kandidatursperre auf — also auch hier: Gast → Anmeldung,
    Mitglied → 403, ohne Wirkung."""
    rolle = Rolle.objects.create(
        mitglied=mitglied_anlegen("ziel"), gremium=Gremium.INTEGRITAETSRAT,
        endet_am=timezone.localdate() + timedelta(days=365),
    )
    daten = {"aktion": aktion, "rolle": rolle.pk, "grund": "Versuch"}
    audit = AuditEintrag.objects.count()

    antwort = client.post(reverse("gremien:rollen_aktion"), daten)
    assert antwort.status_code == 302 and antwort.url == reverse("mitglieder:login")
    client.force_login(mitglied_anlegen("mitglied"))
    assert client.post(reverse("gremien:rollen_aktion"), daten).status_code == 403

    rolle.refresh_from_db()
    assert not rolle.bestaetigt and not rolle.beendet_grund and AuditEintrag.objects.count() == audit


@pytest.mark.parametrize("kennung", ["abc", "", "1 OR 1"])
@pytest.mark.parametrize("aktion", ["bestaetigen", "beenden"])
def test_eine_verformte_rollenkennung_ist_404(client, aktion, kennung):
    admin = mitglied_anlegen("admin")
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    antwort = client.post(reverse("gremien:rollen_aktion"), {"aktion": aktion, "rolle": kennung, "grund": "x"})
    assert antwort.status_code == 404
