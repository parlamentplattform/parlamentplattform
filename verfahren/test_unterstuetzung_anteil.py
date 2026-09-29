"""Die Unterstützungsschwelle als Anteil der Stimmberechtigten (Ordnung Fassung 4, 29.9.2026):
beim Einbringen gerechnet, samt Grundgesamtheit eingefroren, auf der Antragsseite offengelegt."""

from datetime import date

import pytest
from django.urls import reverse

from mitglieder.models import Identitaetsstufe, Mitglied, Mitgliedsstatus
from parameter.models import Parameter, erstbestand_sicherstellen
from verfahren.models import Antragsart, AuditEintrag, Verfahrensordnung, antrag_einbringen

pytestmark = pytest.mark.django_db

REGELN = {
    "id": "sachantrag-standard",
    "version": 4,
    "unterstuetzung_schwelle": 3,
    "unterstuetzung_anteil": 0.5,
    "unterstuetzung_frist_tage": 60,
    "beratung_tage": 21,
    "abstimmung_tage": 28,
    "mindestbeteiligung": 0.05,
    "mehrheitsbasis": "ja_nein",
}


def _mitglieder(n: int, ab: int = 0) -> list[Mitglied]:
    leute = []
    for i in range(ab, ab + n):
        leute.append(
            Mitglied.objects.create(
                username=f"m{i}",
                email=f"m{i}@example.org",
                beitritt=date(2025, 1, 1),
                geprueft_seit=date(2025, 1, 1),
                identitaetsstufe=Identitaetsstufe.GEPRUEFT,
                status=Mitgliedsstatus.AKTIV,
            )
        )
    return leute


@pytest.fixture
def ordnung():
    return Verfahrensordnung.objects.create(policy_id="sachantrag-standard", version=4, regeln=REGELN, aktiv=True)


def test_schwelle_wird_beim_einbringen_aus_dem_anteil_gerechnet_und_eingefroren(ordnung):
    leute = _mitglieder(50)
    antrag = antrag_einbringen(leute[0], "Anteil", "Wortlaut", "Grund", ordnung)
    policy = antrag.policy()
    assert policy.unterstuetzung_schwelle == 25
    assert policy.unterstuetzung_grundgesamtheit == 50 and policy.unterstuetzung_mindestzahl == 3
    _mitglieder(1, ab=50)  # ein Mitglied mehr ändert den eingefrorenen Antrag nicht
    assert antrag.policy().unterstuetzung_schwelle == 25
    letzter = AuditEintrag.objects.order_by("-lfd").first()
    assert letzter.ereignis["unterstuetzung_schwelle"] == 25 and letzter.ereignis["stimmberechtigte"] == 50


def test_mindestzahl_gilt_bei_wenigen_stimmberechtigten(ordnung):
    leute = _mitglieder(4)  # 50 % von 4 = 2 — aber mindestens 3
    antrag = antrag_einbringen(leute[0], "Klein", "Wortlaut", "Grund", ordnung)
    assert antrag.policy().unterstuetzung_schwelle == 3


def test_ohne_anteil_bleibt_die_alte_zahl(ordnung):
    Verfahrensordnung.objects.filter(pk=ordnung.pk).update(regeln={**REGELN, "unterstuetzung_anteil": 0})
    ordnung.refresh_from_db()
    leute = _mitglieder(50)
    antrag = antrag_einbringen(leute[0], "Alt", "Wortlaut", "Grund", ordnung)
    policy = antrag.policy()
    assert policy.unterstuetzung_schwelle == 3 and policy.unterstuetzung_grundgesamtheit == 0


def test_kandidatur_rechnet_mit_den_fuer_personenwahlen_stimmberechtigten(ordnung, settings):
    settings.DDOE_UEBERGANGSREGEL = False
    leute = _mitglieder(10)  # Beitritt 1.1.2025: für Sachfragen ja, für Personenwahlen (12 Monate) erst ab 1.1.2026
    antrag = antrag_einbringen(leute[0], "Wahl", "Wortlaut", "Grund", ordnung, art=Antragsart.MANDAT)
    assert antrag.policy().unterstuetzung_grundgesamtheit == 10  # 2026: die zwölf Monate sind um
    antrag2 = antrag_einbringen(leute[0], "Sache", "Wortlaut", "Grund", ordnung)
    assert antrag2.policy().unterstuetzung_grundgesamtheit == 10


def test_antragsseite_legt_die_herkunft_der_schwelle_offen(client, ordnung):
    leute = _mitglieder(50)
    antrag = antrag_einbringen(leute[0], "Offen", "Wortlaut", "Grund", ordnung)
    html = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "25 Unterstützungen" in html and "50 % der 50 am Einbringungstag Stimmberechtigten, mindestens 3" in html


def test_register_fuehrt_den_anteil_mit_erstbestand_50():
    erstbestand_sicherstellen()
    eintrag = Parameter.objects.get(schluessel="verfahren-unterstuetzung-anteil-prozent")
    assert eintrag.wert == "50" and eintrag.schema_key == "support.threshold_share_percent"


def test_ordnung_aus_dem_register_traegt_den_anteil(client, ordnung):
    """Der Verwaltungsweg (§ 5 Abs 7, D-J3g): Registerwerte → neue Fassung → in Kraft."""
    from parameter.views import _register_werte
    from plattform_core.policy import aus_register

    erstbestand_sicherstellen()
    neu = aus_register(_register_werte(), "sachantrag-standard", 5)
    assert neu.unterstuetzung_anteil == 0.5 and neu.unterstuetzung_schwelle == 3
