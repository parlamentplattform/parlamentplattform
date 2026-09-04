"""Ring 0b — das Parameterregister (F-68): öffentlich, mit Herkunft,
Änderungen nur mit veröffentlichtem Grund; der Code liest von hier."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import standard_ende
from gremien.test_werkstatt import (  # noqa: F401
    einreichen,
    mitglied_anlegen,
    ordnung,
    werkstatt_lage,
)
from ki.models import KILauf
from parameter.models import ERSTBESTAND, Parameter, erstbestand_sicherstellen, zahl
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db


def test_erstbestand_wird_angelegt_und_nie_ueberschrieben():
    assert erstbestand_sicherstellen() == len(ERSTBESTAND)
    eintrag = Parameter.objects.get(schluessel="gremien-hoechstrunden")
    eintrag.wert = "5"
    eintrag.save()
    assert erstbestand_sicherstellen() == 0  # idempotent
    eintrag.refresh_from_db()
    assert eintrag.wert == "5"  # das Register gehört den Menschen, nicht dem Code


def test_zahl_liest_register_mit_ehrlichem_rueckfall():
    assert zahl("gremien-review-tage", 99) == 99  # noch kein Eintrag -> Zielwert
    Parameter.objects.create(
        schluessel="gremien-review-tage", wert="7", beschreibung="x", quelle="Test"
    )
    assert zahl("gremien-review-tage", 99) == 7
    Parameter.objects.create(schluessel="kaputt", wert="viele", beschreibung="x", quelle="Test")
    assert zahl("kaputt", 42) == 42  # unlesbarer Wert -> Zielwert


def test_oeffentliche_seite_und_json_export(client):
    antwort = client.get(reverse("parameter:liste"))
    inhalt = antwort.content.decode()
    assert "gremien-review-tage" in inhalt and "§ 5 Abs 12" in inhalt  # Erstbestand + Quelle
    daten = client.get(reverse("parameter:export")).json()
    schluessel = {p["schluessel"] for p in daten["parameter"]}
    assert {"gremien-hoechstrunden", "ki-monatstokens"} <= schluessel


def test_verwaltung_aendert_nur_mit_grund(client):
    admin = mitglied_anlegen("admin")
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    client.get(reverse("parameter:verwaltung"))  # legt Erstbestand an
    eintrag = Parameter.objects.get(schluessel="gremien-review-tage")
    client.post(
        reverse("parameter:verwaltung_aktion"), {"parameter": eintrag.pk, "wert": "7", "grund": ""}
    )
    eintrag.refresh_from_db()
    assert eintrag.wert == "14"  # ohne Grund keine Änderung
    client.post(
        reverse("parameter:verwaltung_aktion"),
        {"parameter": eintrag.pk, "wert": "7", "grund": "Alpha-Erprobung: kürzere Schleife."},
    )
    eintrag.refresh_from_db()
    assert eintrag.wert == "7"
    audit = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis["typ"] == "parameter_geaendert"]
    assert audit and audit[0]["alt"] == "14" and audit[0]["neu"] == "7"


def test_gaeste_sehen_das_register_aber_nicht_die_verwaltung(client):
    assert client.get(reverse("parameter:liste")).status_code == 200
    antwort = client.get(reverse("parameter:verwaltung"))
    assert antwort.status_code in (302, 403)  # Login-Umleitung bzw. kein Zugang


def test_schleife_liest_ihre_frist_aus_dem_register(client, ordnung):  # noqa: F811
    Parameter.objects.create(
        schluessel="gremien-review-tage", wert="3", beschreibung="x", quelle="Test"
    )
    antrag, _, er = werkstatt_lage(ordnung)
    entwurf = einreichen(client, antrag, er)
    rest = entwurf.review_frist - timezone.now()
    assert timedelta(days=2, hours=23) < rest <= timedelta(days=3)


def test_rollen_dauer_aus_dem_register():
    Parameter.objects.create(
        schluessel="gremien-rollen-dauer-tage", wert="10", beschreibung="x", quelle="Test"
    )
    assert standard_ende() == timezone.localdate() + timedelta(days=10)


def test_ki_budget_aus_dem_register(settings):
    settings.DDOE_KI_MONATSTOKENS = 555
    assert KILauf.monatsbudget() == 555  # Rückfall auf die Umgebung
    Parameter.objects.create(schluessel="ki-monatstokens", wert="777", beschreibung="x", quelle="Test")
    assert KILauf.monatsbudget() == 777  # das Register führt

def _admin(client):
    admin = mitglied_anlegen("admin")
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    client.get(reverse("parameter:verwaltung"))  # legt den Erstbestand an
    return admin


def test_aenderung_steht_am_wert_selbst(client):
    """FB-J2: Wer wissen will, warum eine Frist heute so lang ist, soll es am Wert sehen.

    Im Audit-Log stand die Begründung immer schon — fälschungssicher, aber unauffindbar."""
    _admin(client)
    eintrag = Parameter.objects.get(schluessel="gremien-review-tage")
    client.post(
        reverse("parameter:verwaltung_aktion"),
        {"parameter": eintrag.pk, "wert": "7", "grund": "Alpha-Erprobung: kürzere Schleife."},
    )
    historie = list(eintrag.historie.all())
    assert len(historie) == 1
    assert (historie[0].alter_wert, historie[0].neuer_wert) == ("14", "7")
    assert "Alpha" in historie[0].grund
    assert "Alpha" in client.get(reverse("parameter:liste")).content.decode()


def test_neue_fassung_entsteht_aus_dem_register_gilt_aber_nicht_sofort(client, ordnung):  # noqa: F811
    """FB-J1: Erzeugen ist eine Rechnung, In-Kraft-Setzen eine Entscheidung.

    Beides in einem Knopf zusammenzufassen wäre bequem und falsch: Eine Verwaltung, die eine
    Zahl im Register korrigiert, hätte damit ungewollt die Regeln künftiger Verfahren geändert."""
    from verfahren.models import Verfahrensordnung

    _admin(client)
    Parameter.objects.filter(schluessel="verfahren-abstimmung-tage").update(wert="30")
    client.post(reverse("parameter:verwaltung_ordnung_entwurf"))
    erzeugt = Verfahrensordnung.objects.order_by("-version").first()
    assert erzeugt.regeln["abstimmung_tage"] == 30
    assert erzeugt.aktiv is False  # eine Rechnung, noch keine Ordnung

    client.post(reverse("parameter:verwaltung_ordnung_inkraft"), {"ordnung": erzeugt.pk, "grund": ""})
    erzeugt.refresh_from_db()
    assert erzeugt.aktiv is False  # ohne Grund gilt nichts

    client.post(
        reverse("parameter:verwaltung_ordnung_inkraft"),
        {"ordnung": erzeugt.pk, "grund": "Beschluss der Mitgliederversammlung vom 4.9.2026."},
    )
    erzeugt.refresh_from_db()
    assert erzeugt.aktiv is True and erzeugt.beschlossen_am is not None
    audit = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis["typ"] == "verfahrensordnung_in_kraft"]
    assert audit and "Mitgliederversammlung" in audit[0]["grund"]


def test_die_abgeloeste_fassung_bleibt_bestehen(client, ordnung):  # noqa: F811
    """Grundregel 7: Sonst wäre später nicht mehr nachvollziehbar, nach welchen Regeln ein
    abgeschlossenes Verfahren gelaufen ist."""
    from verfahren.models import Verfahrensordnung

    _admin(client)
    vorher = Verfahrensordnung.objects.filter(aktiv=True).first()
    Parameter.objects.filter(schluessel="verfahren-abstimmung-tage").update(wert="30")
    client.post(reverse("parameter:verwaltung_ordnung_entwurf"))
    neu = Verfahrensordnung.objects.order_by("-version").first()
    client.post(reverse("parameter:verwaltung_ordnung_inkraft"), {"ordnung": neu.pk, "grund": "Test."})
    if vorher is not None:
        vorher.refresh_from_db()
        assert vorher.aktiv is False  # abgelöst, nicht gelöscht
        assert Verfahrensordnung.objects.filter(pk=vorher.pk).exists()


def test_satzungswidriger_registerwert_erzeugt_keine_fassung(client, ordnung):  # noqa: F811
    """Die Satzungsminima stehen im Code, nicht im Register (§ 5 Abs 3 lit c/d).

    Sonst könnte die Verwaltung sie über eine Stellgröße aushebeln — und niemand sähe es."""
    from verfahren.models import Verfahrensordnung

    _admin(client)
    vorher = Verfahrensordnung.objects.count()
    Parameter.objects.filter(schluessel="expertenrat-erstvorschlag-tage").update(wert="10")
    antwort = client.post(reverse("parameter:verwaltung_ordnung_entwurf"), follow=True)
    assert Verfahrensordnung.objects.count() == vorher
    assert "Satzungsminimum" in antwort.content.decode()


def test_ohne_abweichung_entsteht_keine_leere_fassung(client, ordnung):  # noqa: F811
    """Eine Fassung, die dasselbe sagt wie die geltende, wäre nur eine Nummer mehr."""
    from verfahren.models import Verfahrensordnung

    _admin(client)
    client.post(reverse("parameter:verwaltung_ordnung_entwurf"))
    stand = Verfahrensordnung.objects.count()
    client.post(reverse("parameter:verwaltung_ordnung_entwurf"))
    assert Verfahrensordnung.objects.count() == stand


def test_die_registerseite_ordnet_nach_gruppen(client):
    """FB-J2: 32 Zeilen in einer Liste sind vollständig und trotzdem unbrauchbar."""
    inhalt = client.get(reverse("parameter:liste")).content.decode()
    for gruppe in ("Verfahren", "Gremien", "WeicherFilter", "Zukunftswerkstatt"):
        assert f">{gruppe}</h2>" in inhalt, f"Gruppenkarte fehlt: {gruppe}"
    assert 'id="g-verfahren"' in inhalt and 'id="g-ki"' in inhalt  # Sprungmarken
    # Die Stellgroessen, aus denen die Verfahrensordnung gebaut wird, sind als solche kenntlich
    assert inhalt.count("Verfahrensordnung</span>") >= 6


def test_quellen_nennen_keine_internen_kennungen():
    """Entscheidung vom 4.9.2026: keine Kürzel interner Dokumente in öffentlichen Texten.

    Der Wächter in verfahren/test_vorlagen.py prüft Vorlagen — die Quellenangaben des Registers
    stehen aber in Daten und sind ihm dadurch entgangen. Auf der Seite stand „ADR-007"."""
    import re

    muster = re.compile(r"\b(F-\d+|FB-[A-Z]\d+|A0-\d+|ADR-\d+|Ring 0[ab]|L\d)\b")
    treffer = [
        f"{e['schluessel']}: {e['quelle']}" for e in ERSTBESTAND if muster.search(e["quelle"])
    ]
    assert not treffer, "Interne Kennung in der Quellenangabe: " + "; ".join(treffer)


def test_alte_quellen_werden_nachgezogen():
    """Ein Eintrag, der schon in der Datenbank steht, behält seinen Wert — aber nicht seine
    veraltete Quellenangabe. Genau daran ist ADR-007 monatelang stehen geblieben."""
    erstbestand_sicherstellen()
    eintrag = Parameter.objects.get(schluessel="kategorien-regel")
    eintrag.quelle = "§ 2 Abs 6 · ADR-007"
    eintrag.wert = "9"
    eintrag.save()
    erstbestand_sicherstellen()
    eintrag.refresh_from_db()
    assert "ADR" not in eintrag.quelle
    assert eintrag.wert == "9"  # der Wert gehört den Menschen, nicht dem Code


def test_kein_wechsel_auf_eine_fremde_ordnungsreihe(client, ordnung):  # noqa: F811
    """Der Knopf entwickelt die geltende Ordnung weiter — er wechselt nicht das Regelwerk.

    Sonst könnte ein Formular mit fremder Kennung eine ganz andere Verfahrensordnung in Kraft
    setzen, ohne dass jemand die Werte gesehen hat."""
    from verfahren.models import Verfahrensordnung

    _admin(client)
    fremd = Verfahrensordnung.objects.create(
        policy_id="fremde-ordnung",
        version=1,
        regeln={
            "id": "fremde-ordnung", "version": 1, "unterstuetzung_schwelle": 1,
            "unterstuetzung_frist_tage": 14, "beratung_tage": 21, "abstimmung_tage": 7,
            "mindestbeteiligung": 0.05, "mehrheitsbasis": "ja_nein",
            "wiedereinbringung_sperre_monate": 6,
        },
        aktiv=False,
    )
    client.post(
        reverse("parameter:verwaltung_ordnung_inkraft"), {"ordnung": fremd.pk, "grund": "Versuch."}
    )
    fremd.refresh_from_db()
    ordnung.refresh_from_db()
    assert fremd.aktiv is False and ordnung.aktiv is True
