"""Die Übergangsregel nach § 4 Abs 4 lit d wird beim Einbringen eingefroren (Bestandsaufnahme A5, 0.51.0).

Bis 0.50 lasen Zählung, Einzelprüfung, Bewerbung und Unterstützung der Vertrauensfrage die Einstellung
`DDOE_UEBERGANGSREGEL` bei jedem Schritt neu — ein Umschalten mitten in einer Abstimmung ließ Nenner und
Einzelprüfung nach verschiedenen Regeln rechnen (§ 5 Abs 5: „Ein Verstoß macht die betroffene Abstimmung
ungültig“). Jetzt steht der Wert in der Ordnung des Antrags (Fassung 5); die Einstellung gilt nur für
Anträge, die danach eingebracht werden."""

from pathlib import Path

import pytest
from django.urls import reverse

from plattform_core.policy import Policy
from verfahren.models import (
    Antrag,
    AuditEintrag,
    Stimmabgabe,
    antrag_einbringen,
    uebergangsregel_fuer,
)
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def _jung(name="jung"):
    """Ein geprüftes Mitglied mit zehn Tagen Mitgliedschaft — stimmberechtigt nur mit Übergangsregel."""
    return mitglied_anlegen(name, tage=10)


def _in_abstimmung(antrag):
    in_abstimmung_bringen(antrag, [mitglied_anlegen(f"u{antrag.pk}-{i}") for i in range(3)])
    antrag.refresh_from_db()
    return antrag


def _mit_unterstuetzung(antrag):
    return antrag


def test_ein_alter_schnappschuss_ohne_feld_liest_gilt():
    daten = Policy(
        id="p", version=1, unterstuetzung_schwelle=1, unterstuetzung_frist_tage=1, beratung_tage=21,
        abstimmung_tage=7, mindestbeteiligung=0.05,
    ).als_dict()
    daten.pop("uebergangsregel")
    assert Policy.aus_dict(daten).uebergangsregel is True
    assert Policy.aus_dict({**daten, "uebergangsregel": False}).uebergangsregel is False


def test_das_einbringen_friert_den_wert_ein_und_auditiert_ihn(ordnung, settings):  # noqa: F811
    settings.DDOE_UEBERGANGSREGEL = False
    antrag = antrag_einbringen(mitglied_anlegen("steller"), **ANTRAG, ordnung=ordnung)
    assert antrag.policy_snapshot["uebergangsregel"] is False and uebergangsregel_fuer(antrag) is False
    ereignis = AuditEintrag.objects.filter(ereignis__typ="antrag_eingebracht").last().ereignis
    assert ereignis["uebergangsregel"] is False and "mitglied" not in ereignis


def test_umschalten_nach_dem_einbringen_aendert_das_laufende_verfahren_nicht(client, ordnung, settings):  # noqa: F811
    """Eingebracht mit Übergangsregel, dann abgeschaltet: Das junge Mitglied zählt im Nenner und darf stimmen."""
    settings.DDOE_UEBERGANGSREGEL = True
    jung = _jung()
    antrag = _mit_unterstuetzung(antrag_einbringen(mitglied_anlegen("steller"), **ANTRAG, ordnung=ordnung))
    settings.DDOE_UEBERGANGSREGEL = False
    antrag = _in_abstimmung(antrag)
    assert antrag.phase == "abstimmung"
    from mitglieder.models import stimmberechtigte_zaehlen
    from plattform_core import Gegenstand

    stichtag = antrag.stichtag_der_stimmberechtigung()
    assert antrag.stimmberechtigte_anzahl == stimmberechtigte_zaehlen(Gegenstand.SACHFRAGE, stichtag, uebergang=True)
    assert antrag.stimmberechtigte_anzahl > stimmberechtigte_zaehlen(Gegenstand.SACHFRAGE, stichtag, uebergang=False)
    client.force_login(jung)
    client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "ja"})
    assert Stimmabgabe.objects.filter(antrag=antrag).count() == 1


def test_umgekehrt_ohne_uebergangsregel_eingebracht_bleibt_sie_aus(client, ordnung, settings):  # noqa: F811
    settings.DDOE_UEBERGANGSREGEL = False
    jung = _jung()
    antrag = _mit_unterstuetzung(antrag_einbringen(mitglied_anlegen("steller"), **ANTRAG, ordnung=ordnung))
    settings.DDOE_UEBERGANGSREGEL = True
    antrag = _in_abstimmung(antrag)
    client.force_login(jung)
    antwort = client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "ja"})
    assert antwort.status_code in (302, 403)
    assert not Stimmabgabe.objects.filter(antrag=antrag).exists()
    # Die Kachel liest dieselbe eingefrorene Regel: „nicht stimmberechtigt“ statt Stimmknöpfen
    from verfahren.hinweise import handlungslage

    assert handlungslage(jung).stimmsperre(jung, antrag) == "nicht_stimmberechtigt"


def test_ein_neu_eingebrachter_antrag_traegt_den_neuen_wert(ordnung, settings):  # noqa: F811
    settings.DDOE_UEBERGANGSREGEL = True
    alt = antrag_einbringen(mitglied_anlegen("a"), **ANTRAG, ordnung=ordnung)
    settings.DDOE_UEBERGANGSREGEL = False
    neu = antrag_einbringen(mitglied_anlegen("b"), **ANTRAG, ordnung=ordnung)
    assert uebergangsregel_fuer(alt) is True and uebergangsregel_fuer(neu) is False


def test_die_lesbaren_regeln_nennen_die_anwartschaft(ordnung, settings):  # noqa: F811
    from verfahren.views import _regeln_lesbar

    settings.DDOE_UEBERGANGSREGEL = True
    mit = antrag_einbringen(mitglied_anlegen("a"), **ANTRAG, ordnung=ordnung)
    settings.DDOE_UEBERGANGSREGEL = False
    ohne = antrag_einbringen(mitglied_anlegen("b"), **ANTRAG, ordnung=ordnung)
    assert dict(_regeln_lesbar(mit.policy()))["Anwartschaft"] == "entfällt — Übergangsregel (§ 4 Abs 4 lit d)"
    assert dict(_regeln_lesbar(ohne.policy()))["Anwartschaft"] == "3 Monate (§ 4 Abs 4 lit b)"
    assert dict(_regeln_lesbar(ohne.policy(), "mandat"))["Anwartschaft"] == "12 Monate (§ 4 Abs 4 lit b)"


def test_die_einstellung_liest_nur_noch_eine_stelle():
    """Quelltext-Wächter: Verfahren lesen die Einstellung nur in `uebergangsregel_der_instanz`."""
    wurzel = Path(__file__).resolve().parent.parent
    erlaubt = {"config/settings.py", "mitglieder/post.py", "verfahren/models.py"}
    treffer = set()
    for p in wurzel.rglob("*.py"):
        teile = p.relative_to(wurzel).parts
        if "migrations" in teile or p.name.startswith("test_") or ".claude" in teile:
            continue
        text = p.read_text(encoding="utf-8")
        if "settings.DDOE_UEBERGANGSREGEL" in text or '"DDOE_UEBERGANGSREGEL"' in text:
            treffer.add("/".join(teile))
    assert treffer <= erlaubt, treffer
    models = (wurzel / "verfahren" / "models.py").read_text(encoding="utf-8")
    assert models.count('"DDOE_UEBERGANGSREGEL"') == 1


def test_die_migration_schreibt_nur_auf_einer_instanz_ohne_uebergangsregel(ordnung, settings):  # noqa: F811
    import importlib

    from django.apps import apps as echte_apps
    from django.db import connection

    migration = importlib.import_module("verfahren.migrations.0025_reaktion_zurueckgenommen_und_uebergangsregel")
    antrag = antrag_einbringen(mitglied_anlegen("alt"), **ANTRAG, ordnung=ordnung)
    alt = dict(antrag.policy_snapshot)
    alt.pop("uebergangsregel")
    Antrag.objects.filter(pk=antrag.pk).update(policy_snapshot=alt)

    class Editor:
        pass

    editor = Editor()
    editor.connection = connection
    vorher = AuditEintrag.objects.count()
    settings.DDOE_UEBERGANGSREGEL = True
    assert migration.uebergangsregel_nachtragen(echte_apps, editor) == 0
    assert AuditEintrag.objects.count() == vorher  # nichts geschrieben, kein Eintrag

    settings.DDOE_UEBERGANGSREGEL = False
    assert migration.uebergangsregel_nachtragen(echte_apps, editor) == 1
    antrag.refresh_from_db()
    assert antrag.policy_snapshot["uebergangsregel"] is False
    eintrag = AuditEintrag.objects.order_by("-lfd").first().ereignis
    assert eintrag["typ"] == "uebergangsregel_nachgetragen" and eintrag["antraege"] == 1
    assert migration.uebergangsregel_nachtragen(echte_apps, editor) == 0  # idempotent
