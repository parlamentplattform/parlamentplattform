"""Die Ansichten des Parlaments und der Antragsseite — Behebung der Gesamtprüfung (0.45.0):
Fristen mit der Hemmung durch Aussetzungen (Befund #24, #30), neutrale Grundordnung nach dem
Fristende (Befund #70), Abfragezahl unabhängig von der Zahl der Anträge (Befund #39, #40) und
die Grenzen aus dem Parameterregister (Befund #45)."""

from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from parameter.models import Parameter
from verfahren.models import Antrag, Kategorie, Verfahrensordnung, antrag_einbringen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    REGELN,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def _register(schluessel: str, wert: int) -> None:
    Parameter.objects.update_or_create(
        schluessel=schluessel, defaults={"wert": str(wert), "beschreibung": "Test", "quelle": "Test"}
    )


def _aussetzung(antrag, beginn, beendet_am=None):
    """Eine Aussetzung nach § 6 Abs 3 lit d samt dem Beschluss, der sie trägt."""
    from gremien.models import Anlass, Aussetzung, GremienBeschluss, Gremium

    beschluss = GremienBeschluss.objects.create(
        gremium=Gremium.INTEGRITAETSRAT,
        anlass=Anlass.AUSSETZUNG,
        gegenstand="Abstimmung aussetzen",
        beschreibung="Begründeter Verdacht auf Manipulation.",
        optionen=[{"wert": "dafuer", "name": "dafür"}, {"wert": "dagegen", "name": "dagegen"}],
        antrag=antrag,
        ergebnis="dafuer",
        angelegt_von=mitglied_anlegen("ir-vorsitz"),
    )
    return Aussetzung.objects.create(
        antrag=antrag,
        gegenstand=Aussetzung.Gegenstand.ABSTIMMUNG,
        beschluss=beschluss,
        begruendung=beschluss.beschreibung,
        beginn=beginn,
        beendet_am=beendet_am,
        beendet_grund="von selbst geendet" if beendet_am else "",
    )


def _abstimmung(ordnung, unterstuetzer):  # noqa: F811
    antrag = antrag_einbringen(unterstuetzer[0], **ANTRAG, ordnung=ordnung)
    return in_abstimmung_bringen(antrag, unterstuetzer[1:])


# ── Fristen mit Aussetzung (Befund #24, #30) ─────────────────────────────────


def test_frist_auf_der_antragsseite_rechnet_die_aussetzung_ein(client, ordnung):  # noqa: F811
    """Phasenautomat und Stimmzulässigkeit rechnen mit `wirksamer_phase_beginn`, die Anzeige
    rechnete mit dem rohen `phase_beginn`: Nach einer Aussetzung stand am Antrag ein Fristende,
    das um deren Dauer zu früh lag, während die Abstimmung weiterlief — wer dem glaubte, verlor
    Stimmrecht (§ 6 Abs 3 lit d)."""
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = _abstimmung(ordnung, leute)
    jetzt = timezone.now()
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=jetzt - timedelta(days=4))
    antrag.refresh_from_db()
    ohne = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    frist_roh = antrag.phase_beginn + timedelta(days=REGELN["abstimmung_tage"])  # in drei Tagen
    assert f"Frist {frist_roh:%d.%m.%Y}" in ohne

    # Drei Tage Stillstand innerhalb der Phase, von selbst geendet (kein Antrag ans Schiedsgericht)
    _aussetzung(antrag, beginn=jetzt - timedelta(days=3, hours=12), beendet_am=jetzt - timedelta(hours=12))
    mit = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert f"Frist {frist_roh + timedelta(days=3):%d.%m.%Y}" in mit, "die Hemmung verschiebt das angezeigte Ende"
    assert f"Frist {frist_roh:%d.%m.%Y}" not in mit
    assert "aussetzung-band" not in mit, "eine beendete Aussetzung braucht kein Band mehr"


def test_laufende_aussetzung_steht_am_antrag(client, ordnung):  # noqa: F811
    """Die Satzung verlangt die Veröffentlichung der Aussetzung; bisher war sie nur unter
    /gremien/beschluesse/ zu finden, am Antrag selbst stand nichts (Befund #30)."""
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = _abstimmung(ordnung, leute)
    aussetzung = _aussetzung(antrag, beginn=timezone.now() - timedelta(days=1))
    inhalt = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "aussetzung-band" in inhalt
    assert f"durch Beschluss {aussetzung.beschluss.nummer} des Integritätsrats" in inhalt
    assert "die Frist ruht" in inhalt
    assert reverse("gremien:beschluss", args=[aussetzung.beschluss.nummer]) in inhalt


def test_kachel_und_feed_zeile_rechnen_die_aussetzung_ein(client, ordnung):  # noqa: F811
    """Dieselbe Hemmung gilt für Resttage und Ring in Kacheln und Feed-Zeilen (Befund #24)."""
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = _abstimmung(ordnung, leute)
    jetzt = timezone.now()
    Antrag.objects.filter(pk=antrag.pk).update(
        hervorgehoben=True, hervorhebung_begruendung="IR-2026-01.", phase_beginn=jetzt - timedelta(days=4)
    )
    vorher = client.get("/parlament/").content.decode()
    assert "noch <strong>2</strong> Tage" in vorher  # Frist in knapp drei Tagen

    _aussetzung(antrag, beginn=jetzt - timedelta(days=3, hours=12), beendet_am=jetzt - timedelta(hours=12))
    nachher = client.get("/parlament/").content.decode()
    assert "noch <strong>5</strong> Tage" in nachher
    assert "noch <strong>2</strong> Tage" not in nachher


# ── Neutrale Grundordnung nach dem Fristende (Befund #70) ─────────────────────


def test_neutrale_grundordnung_reiht_nach_dem_fristende(client, ordnung):  # noqa: F811
    """§ 5 Abs 10 lit d und das Regelverzeichnis sagen „Phase und Frist“; der Code reihte nach dem
    Phasenbeginn. Mit zwei Ordnungen verschiedener Dauer endet der später begonnene Antrag früher —
    er muss zuerst stehen (Grundregel 6: die offengelegte Regel ist die ausgeführte)."""
    laenger = Verfahrensordnung.objects.create(
        policy_id="test-lang", version=1, regeln={**REGELN, "id": "test-lang", "abstimmung_tage": 14}, aktiv=False
    )
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    lang = antrag_einbringen(leute[0], "Lange Abstimmung", "W.", "", laenger)
    in_abstimmung_bringen(lang, leute[1:])
    Antrag.objects.filter(pk=lang.pk).update(phase_beginn=timezone.now() - timedelta(days=2))  # Frist in 12 Tagen
    spaet = antrag_einbringen(leute[0], "Kurze Abstimmung", "W.", "", ordnung)
    in_abstimmung_bringen(spaet, leute[1:])  # beginnt später, Frist schon in 7 Tagen

    inhalt = client.get("/parlament/").content.decode()
    feld = inhalt.split('id="feld-filter"')[1].split('id="feld-favoriten"')[0]
    assert feld.index("Kurze Abstimmung") < feld.index("Lange Abstimmung"), "früheres Fristende zuerst"


# ── Abfragen wachsen nicht mit der Zahl der Anträge (Befund #39, #40) ─────────


def _baum():
    w = Kategorie.objects.create(slug="leben", name="Leben")
    a = Kategorie.objects.create(slug="zusammenleben", name="Zusammenleben", eltern=w)
    b = Kategorie.objects.create(slug="wohnen", name="Wohnen", eltern=a)
    c = Kategorie.objects.create(slug="bauen", name="Bauen", eltern=b)
    return Kategorie.objects.create(slug="installateur", name="Installateur", eltern=c)


def _antraege(ordnung, n, thema, ab=0):  # noqa: F811
    leute = [mitglied_anlegen(f"z{ab + i}") for i in range(n)]
    for i, m in enumerate(leute):
        a = antrag_einbringen(m, f"Antrag {ab + i}", "Wortlaut.", "", ordnung,
                              ebene="gemeinde" if i % 2 else "bund", gebiet="Wels" if i % 2 else "")
        a.kategorien.add(thema)
        if i % 3 == 0:
            a.unterstuetzungen.create(mitglied=leute[(i + 1) % n])


def _abfragen(client, pfad="/parlament/"):
    with CaptureQueriesContext(connection) as ctx:
        antwort = client.get(pfad)
    assert antwort.status_code == 200
    return len(ctx.captured_queries), [q["sql"] for q in ctx.captured_queries]


@pytest.mark.parametrize("gast", [True, False], ids=["gast", "mitglied"])
def test_parlament_fragt_unabhaengig_von_der_zahl_der_antraege(client, ordnung, gast):  # noqa: F811
    """Vorher zählte jede Kachel und Feed-Zeile dreimal für sich (Unterstützungen, Beiträge,
    Stimmen) und lief für das Tooltip die Elternkette des Lebensbereichs hoch — bei 306 Anträgen
    2.897 Abfragen. Jetzt ist die Zahl der Abfragen von der Zahl der Anträge unabhängig."""
    thema = _baum()
    if not gast:
        client.force_login(mitglied_anlegen("leserin"))
    _antraege(ordnung, 4, thema)
    wenig, sql_wenig = _abfragen(client)
    _antraege(ordnung, 26, thema, ab=100)
    viel, sql_viel = _abfragen(client)
    assert Antrag.objects.count() == 30
    assert viel == wenig, f"{wenig} Abfragen bei 4 Anträgen, {viel} bei 30"
    kategorie_selects = [q for q in sql_viel if 'WHERE "verfahren_kategorie"."id" = ' in q]
    assert not kategorie_selects, "kein Einzel-SELECT je Baumebene mehr"


def test_gaeste_laden_keine_stimmregister(client, ordnung):  # noqa: F811
    """`_meine_stimmen` wertete `list(laufend)` aus, bevor es Gäste abwies (Befund #40)."""
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    _abstimmung(ordnung, leute)
    _n, sql = _abfragen(client)
    assert not [q for q in sql if "verfahren_stimmregister" in q], "Gäste haben kein Stimmregister"


def test_antragsseite_laedt_die_pfade_der_lebensbereiche_ohne_kette(client, ordnung):  # noqa: F811
    thema = _baum()
    antrag = antrag_einbringen(mitglied_anlegen("anna"), **ANTRAG, ordnung=ordnung)
    antrag.kategorien.add(thema)
    _n, sql = _abfragen(client, reverse("verfahren:antrag", args=[antrag.pk]))
    einzeln = [q for q in sql if 'WHERE "verfahren_kategorie"."id" = ' in q]
    assert not einzeln, einzeln


# ── Grenzen aus dem Register (Befund #45) ────────────────────────────────────


def test_hervorgehobene_kacheln_folgen_dem_register(client, ordnung):  # noqa: F811
    """`wichtige` war im Parlament unbegrenzt und auf der Startseite fest `[:3]`; der Registerwert
    `kacheln-hervorgehoben` existierte, wurde aber nirgends gelesen (Befund #45)."""
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    for i in range(4):
        a = antrag_einbringen(leute[0], f"Wichtig {i}", "W.", "", ordnung)
        in_abstimmung_bringen(a, leute[1:])
        Antrag.objects.filter(pk=a.pk).update(hervorgehoben=True, hervorhebung_begruendung="IR.")
    _register("kacheln-hervorgehoben", 2)
    feld = client.get("/parlament/").content.decode().split('id="feld-wichtig"')[1].split('id="feld-region"')[0]
    assert feld.count('class="kachel"') == 2
    start = client.get("/").content.decode()
    assert start.count("Wichtig ") == 2
    _register("kacheln-hervorgehoben", 4)
    feld = client.get("/parlament/").content.decode().split('id="feld-wichtig"')[1].split('id="feld-region"')[0]
    assert feld.count('class="kachel"') == 4


def test_suchtreffer_und_abgeschlossene_folgen_dem_register(client, ordnung):  # noqa: F811
    w = Kategorie.objects.create(slug="leben", name="Leben")
    for i in range(5):
        Kategorie.objects.create(slug=f"wasser-{i}", name=f"Wasser {i}", eltern=w)
    _register("suche-treffer-hoechstzahl", 2)
    inhalt = client.get("/parlament/?suche=wasser").content.decode()
    assert inhalt.count('class="treffer-link"') == 2

    anna = mitglied_anlegen("anna")
    for i in range(3):
        a = antrag_einbringen(anna, f"Erledigt {i}", "W.", "", ordnung)
        Antrag.objects.filter(pk=a.pk).update(phase="angenommen")
    _register("kacheln-abgeschlossen", 1)
    feld = client.get("/parlament/").content.decode().split('id="feld-filter"')[1].split('id="feld-favoriten"')[0]
    assert feld.count("Erledigt ") == 1


# ── Audit-Spur, Sprachwechsel, Startseite (Befund #41, #83, #86) ─────────────


def test_audit_spur_wird_in_der_datenbank_gefiltert(client, ordnung):  # noqa: F811
    """`audit_spur` iterierte das gesamte Audit-Log ohne WHERE und siebte in Python — jeder
    Antragsaufruf zog die Stimm-Ereignisse aller anderen Anträge mit (Befund #41)."""
    from verfahren.models import AuditEintrag

    anna = mitglied_anlegen("anna")
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    for i in range(30):
        AuditEintrag.anhaengen({"typ": "fremd", "antrag": antrag.pk + 1000 + i})
    _n, sql = _abfragen(client, reverse("verfahren:antrag", args=[antrag.pk]))
    audit = [q for q in sql if '"verfahren_auditeintrag"' in q and "SELECT" in q]
    assert audit, "die Spur wird geladen"
    assert all("WHERE" in q for q in audit), audit
    assert [q for q in sql if "archiv-audit-anzeige" in q].__len__() == 1, "der Registerwert wird einmal gelesen"


def test_sprachwechsel_behaelt_die_abfrageparameter(client):
    """Das `next`-Feld trug `request.path`: Fächer-Ast, Suche und Filter gingen beim Wechsel
    verloren (Befund #83)."""
    inhalt = client.get("/parlament/?fach=bildung&suche=kind").content.decode()
    assert 'name="next" value="/parlament/?fach=bildung&amp;suche=kind"' in inhalt
    antwort = client.post(reverse("set_language"), {"language": "en", "next": "/parlament/?fach=bildung&suche=kind"})
    assert antwort.status_code == 302 and antwort["Location"] == "/parlament/?fach=bildung&suche=kind"


def test_startseite_nennt_die_rundenzahl_aus_dem_register(client):
    """Das Diagramm sagte fest „höchstens 3 Runden“, obwohl `fristen.runden` den Registerwert
    lieferte — nach einer Änderung im Register log die erste Seite (Befund #86)."""
    _register("gremien-hoechstrunden", 2)
    inhalt = client.get("/").content.decode()
    assert "höchstens 2 Runden" in inhalt
    assert "höchstens 3 Runden" not in inhalt
