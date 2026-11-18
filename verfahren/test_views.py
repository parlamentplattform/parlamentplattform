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
    frist_roh = timezone.localtime(antrag.phase_beginn + timedelta(days=REGELN["abstimmung_tage"]))  # in drei Tagen, Ortszeit wie die Seite
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
    # Frist in drei Tagen — gezählt in Wiener Kalendertagen (GP-175)
    assert "noch <strong>3</strong> Tage" in vorher

    _aussetzung(antrag, beginn=jetzt - timedelta(days=3, hours=12), beendet_am=jetzt - timedelta(hours=12))
    nachher = client.get("/parlament/").content.decode()
    assert "noch <strong>6</strong> Tage" in nachher
    assert "noch <strong>3</strong> Tage" not in nachher


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


def test_startseite_nennt_die_rundenzahl_der_aktiven_ordnung(client, ordnung):  # noqa: F811
    """Eine vorgemerkte Registeränderung darf keine neue Verfahrensordnung vortäuschen."""
    _register("gremien-hoechstrunden", 2)
    inhalt = client.get("/").content.decode()
    assert f"höchstens {ordnung.als_policy().hoechstrunden} Runden" in inhalt
    assert "höchstens 2 Runden" not in inhalt


def test_gp076_willkommensseite_behauptet_keine_pruefung_die_nicht_stattfand(client):
    """GP-076 (OCR-13): Die Zahl auf der Willkommensseite zählt jedes aktive Parteikonto — auch
    ungeprüfte und pausierte. Ihr Etikett darf darum keine bestätigten Mitglieder behaupten."""
    import re

    from mitglieder.models import Identitaetsstufe

    def zahl_und_etikett():
        inhalt = client.get('/').content.decode()
        treffer = re.search(r'<div class="zahl"><strong>(\d+)</strong><span>([^<]+)</span>', inhalt)
        return int(treffer.group(1)), treffer.group(2)

    mitglied_anlegen('anna')
    vorher, _etikett = zahl_und_etikett()
    mitglied_anlegen('neu', stufe=Identitaetsstufe.UNGEPRUEFT)
    nachher, etikett = zahl_und_etikett()
    if 'bestätigt' in etikett:
        assert nachher == vorher
    else:
        assert etikett == 'Mitglieder'


@pytest.mark.parametrize('weg', ['einreihen', 'einbettung'])
def test_gp178_fehler_im_nachlauf_haelt_das_einbringen_nicht_auf(client, ordnung, monkeypatch, weg):  # noqa: F811
    """GP-178 (ZWA-20): Warf der Vektor-Auftrag nach dem Speichern eine Ausnahme, sah das Mitglied eine
    Fehlerseite, obwohl der Antrag stand — und ein erneutes Absenden brachte ihn ein zweites Mal ein."""
    from types import SimpleNamespace

    import ki.warteschlange
    import verfahren.aehnlichkeit
    from verfahren import views_aktionen
    from verfahren.test_views_aktionen import ANTRAG as EINGABE

    def kaputt(*args, **kwargs):
        raise RuntimeError('Vektor-Auftrag kaputt')

    if weg == 'einreihen':
        monkeypatch.setattr(views_aktionen, 'anbieter_waehlen', lambda *a, **k: SimpleNamespace(name='Test'))
        monkeypatch.setattr(ki.warteschlange, 'einreihen', kaputt)
    else:
        monkeypatch.setattr(verfahren.aehnlichkeit, 'einbettung_speichern', kaputt)
        echt = views_aktionen.aehnliche_antraege

        def mit_vektor(*args, **kwargs):
            ergebnis = echt(*args, **kwargs)
            ergebnis.neuer_vektor, ergebnis.bedeutungsmodell = [0.1, 0.2], 'test-modell'
            return ergebnis

        monkeypatch.setattr(views_aktionen, 'aehnliche_antraege', mit_vektor)
    client.force_login(mitglied_anlegen('anna'))
    antwort = client.post(reverse('verfahren:einbringen'), EINGABE)
    assert Antrag.objects.count() == 1
    antrag = Antrag.objects.get()
    assert antwort.status_code == 302
    assert antwort['Location'].startswith(reverse('verfahren:antrag', args=[antrag.pk]))


def test_gp180_phase_zurueckgezogen_hat_einen_anzeigenamen():
    """GP-180 (AF-14): Ohne Eintrag stand der rohe Bezeichner „zurueckgezogen“ im Badge."""
    from django.utils import translation

    from plattform_core import Phase
    from verfahren.templatetags.phasen import NAMEN, phase_name

    assert phase_name(Phase.ZURUECKGEZOGEN.value) == 'zurückgezogen'
    assert {phase.value for phase in Phase} <= set(NAMEN)  # jede Phase hat einen Anzeigenamen
    with translation.override('en'):
        assert phase_name(Phase.ZURUECKGEZOGEN.value) not in ('zurueckgezogen', '')


def test_gp174_archiv_export_kennt_nur_json_und_md(client, ordnung):  # noqa: F811
    """GP-174 (ASR-26): Jede Endung lieferte Nutzertext unter ihrem Dateinamen (etwa archiv.html)."""
    antrag = antrag_einbringen(mitglied_anlegen('anna'), **ANTRAG, ordnung=ordnung)
    for art in ('json', 'md'):
        antwort = client.get(reverse('verfahren:archiv_export', args=[antrag.pk, art]))
        assert antwort.status_code == 200
        assert antwort['Content-Disposition'].endswith(f'archiv.{art}"')
    for art in ('html', 'svg', 'exe', 'JSON'):
        assert client.get(f'/antrag/{antrag.pk}/archiv.{art}').status_code == 404


def test_gp179_rechtsfolgenformat_nur_lesend(client):
    """GP-179 (ZWA-24): Das Schema nahm jede HTTP-Methode an — wie das Antwortformat nur GET und HEAD."""
    ziel = reverse('verfahren:rechtsfolgenformat')
    assert client.get(ziel).status_code == 200
    assert client.post(ziel).status_code == 405


@pytest.mark.parametrize('anfrage', ['', '?fokus=region', '?suche=Wohnen'])
@pytest.mark.parametrize('angemeldet', [False, True])
def test_gp063_parlament_hat_genau_eine_h1(client, ordnung, anfrage, angemeldet):  # noqa: F811
    """GP-063 (ZB-07, GAST-17): Das Parlament hatte in keiner Rolle und Variante eine h1."""
    if angemeldet:
        client.force_login(mitglied_anlegen('anna'))
    seite = client.get(reverse('verfahren:parlament') + anfrage).content.decode()
    assert seite.count('<h1') == 1
    assert '>Parlament</h1>' in seite


def test_gp081_englische_startseite_uebersetzt_wer_darf_was(client):
    """GP-081 (GAST-09): Der Block „Wer darf was“ der Startseite gab Namen und Fähigkeiten der Rollen
    ohne Übersetzung aus."""
    seite = client.get('/', HTTP_ACCEPT_LANGUAGE='en').content.decode()
    teil = seite[seite.index('id="rollen"'):]
    assert 'Guest' in teil
    assert 'Das Parlament ansehen' not in teil
    assert 'Alles zu' not in teil


def test_gp170_veraltetes_einbringformular_landet_nicht_in_der_neuen_gemeinde(client, ordnung):  # noqa: F811
    """GP-170 (OW-13): Ein vor dem Umzug geöffnetes Formular brachte den Antrag ohne Rückfrage in
    der neuen Gemeinde ein; die Erfolgsmeldung nannte kein Gebiet."""
    from mitglieder.models import Gemeinde, Mitglied, Wohnsitzart

    alt = Gemeinde.objects.create(kennziffer='40510', name='Altort', bezirk='Eferding', bundesland='oberoesterreich')
    neu = Gemeinde.objects.create(kennziffer='41419', name='Neuort', bezirk='Schärding', bundesland='oberoesterreich')
    autor = mitglied_anlegen('autor', tage=800)
    autor.wohnsitz, autor.wohnsitz_art = alt, Wohnsitzart.OESTERREICH
    autor.save(update_fields=['wohnsitz', 'wohnsitz_art'])
    client.force_login(autor)
    url = reverse('verfahren:einbringen')
    formular = client.get(url).content.decode()
    assert 'name="gebiet_kennung" value="gemeinde:40510"' in formular

    Mitglied.objects.filter(pk=autor.pk).update(wohnsitz=neu)
    eingabe = {**ANTRAG, 'ebene': 'gemeinde', 'trotzdem': '1', 'gebiet_kennung': 'gemeinde:40510'}
    antwort = client.post(url, eingabe)
    assert antwort.status_code == 200
    assert not Antrag.objects.exists()
    assert 'Das Gebiet hat sich geändert' in str(antwort.context['form'].errors['ebene'])
    assert 'name="gebiet_kennung" value="gemeinde:41419"' in antwort.content.decode()

    antwort = client.post(url, {**eingabe, 'gebiet_kennung': 'gemeinde:41419'}, follow=True)
    antrag = Antrag.objects.get()
    assert antrag.gebiet == 'Neuort'
    assert any('Neuort' in str(m) for m in antwort.context['messages'])


def _umzug_lage(ordnung):  # noqa: F811
    """Ein Mitglied bringt in Altort einen Gemeindeantrag ein und zieht dann nach Neuort."""
    from mitglieder.models import Gemeinde, Mitglied, Wohnsitzart

    alt = Gemeinde.objects.create(kennziffer='40510', name='Altort', bezirk='Eferding', bundesland='oberoesterreich')
    neu = Gemeinde.objects.create(kennziffer='41419', name='Neuort', bezirk='Schärding', bundesland='oberoesterreich')
    m = mitglied_anlegen('wanderin', tage=800, gemeinde='Altort')
    m.wohnsitz, m.wohnsitz_art = alt, Wohnsitzart.OESTERREICH
    m.save(update_fields=['wohnsitz', 'wohnsitz_art'])
    antrag = antrag_einbringen(m, **ANTRAG, ordnung=ordnung, ebene='gemeinde', neuer_teilnehmerkreis=True)
    Mitglied.objects.filter(pk=m.pk).update(wohnsitz=neu, gemeinde='Neuort')
    m.refresh_from_db()
    return m, antrag


def _region(client) -> str:
    seite = client.get(reverse('verfahren:parlament')).content.decode()
    return seite.split('id="feld-region"', 1)[1].split('</section>', 1)[0]


def test_gp054_region_nennt_den_ort_einer_kachel_aus_dem_alten_wohnort(client, ordnung):  # noqa: F811
    """GP-054 (OW-02): Nach dem Umzug stand der Antrag des alten Wohnorts ohne Ortsangabe unter
    dem Kopf „Gemeinde · Neuort“."""
    m, antrag = _umzug_lage(ordnung)
    assert antrag.gebiet == 'Altort'
    client.force_login(m)
    region = _region(client)
    assert 'Gemeinde · Neuort' in region
    kachel = region.split(f'href="/antrag/{antrag.pk}/"', 1)[1].split('</article>', 1)[0]
    assert '<span class="rest ort">Altort</span>' in kachel
    assert 'Teilnehmerkreis vom' in kachel


def test_gp054_kachel_im_eigenen_ort_bleibt_ohne_ortsangabe(client, ordnung):  # noqa: F811
    from mitglieder.models import Gemeinde, Wohnsitzart

    ort = Gemeinde.objects.create(kennziffer='40510', name='Altort', bezirk='Eferding', bundesland='oberoesterreich')
    m = mitglied_anlegen('sesshaft', tage=800, gemeinde='Altort')
    m.wohnsitz, m.wohnsitz_art = ort, Wohnsitzart.OESTERREICH
    m.save(update_fields=['wohnsitz', 'wohnsitz_art'])
    antrag = antrag_einbringen(m, **ANTRAG, ordnung=ordnung, ebene='gemeinde', neuer_teilnehmerkreis=True)
    client.force_login(m)
    kachel = _region(client).split(f'href="/antrag/{antrag.pk}/"', 1)[1].split('</article>', 1)[0]
    assert 'class="rest ort"' not in kachel


def test_gp055_altkonto_mit_gemeindetext_wird_zum_verzeichnis_gefuehrt(client, ordnung):  # noqa: F811
    """GP-055 (OW-03): Konten mit Gemeinde nur als Freitext sahen „Noch nichts in Ihrer Gemeinde“
    unter dem eigenen Ortsnamen, aber keinen Weg zum Gemeindeverzeichnis."""
    m = mitglied_anlegen('altkonto', tage=800)  # Gemeindetext und Bundesland, kein Verzeichnisverweis
    assert m.gemeinde and not m.wohnsitz_id
    client.force_login(m)
    ziel = reverse('mitglieder:profil') + '#wohnsitz'
    region = _region(client)
    assert 'Noch nichts in Ihrer Gemeinde' not in region
    assert f'href="{ziel}"' in region and 'Hauptwohnsitz aus dem Gemeindeverzeichnis' in region
    assert f'Gemeinde · {m.gemeinde}' not in region
    formular = client.get(reverse('verfahren:einbringen')).content.decode()
    assert f'href="{ziel}"' in formular and 'Hauptwohnsitz aus dem Gemeindeverzeichnis' in formular


def _fremder_gemeindeantrag(ordnung):  # noqa: F811
    from mitglieder.models import Gemeinde, Wohnsitzart

    ort = Gemeinde.objects.create(kennziffer='40510', name='Altort', bezirk='Eferding', bundesland='oberoesterreich')
    autor = mitglied_anlegen('autor', tage=800, gemeinde='Altort')
    autor.wohnsitz, autor.wohnsitz_art = ort, Wohnsitzart.OESTERREICH
    autor.save(update_fields=['wohnsitz', 'wohnsitz_art'])
    return antrag_einbringen(autor, **ANTRAG, ordnung=ordnung, ebene='gemeinde', neuer_teilnehmerkreis=True)


def test_gp056_sperrseite_nennt_grund_und_naechsten_schritt(client, ordnung):  # noqa: F811
    """GP-056 (OW-04): Die 403-Seite sagte nur „Sie gehören nicht zum Kreis“ — ohne Grund und Weg."""
    from mitglieder.models import Gemeinde, Wohnsitzart

    antrag = _fremder_gemeindeantrag(ordnung)
    tag = f'{timezone.localtime(antrag.teilnehmerkreis_am):%d.%m.%Y}'
    ohne = mitglied_anlegen('ohne', tage=800)  # kein Verzeichnisverweis
    client.force_login(ohne)
    antwort = client.post(reverse('verfahren:unterstuetzen', args=[antrag.pk]))
    assert antwort.status_code == 403
    seite = antwort.content.decode()
    assert 'keine örtliche Zuordnung' in seite and 'Bundesebene steht Ihnen offen' in seite
    assert 'keine örtliche Zuordnung' in client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()

    woanders = mitglied_anlegen('woanders', tage=800, gemeinde='Neuort')
    woanders.wohnsitz = Gemeinde.objects.create(kennziffer='41419', name='Neuort', bezirk='Schärding', bundesland='oberoesterreich')
    woanders.wohnsitz_art = Wohnsitzart.OESTERREICH
    woanders.save(update_fields=['wohnsitz', 'wohnsitz_art'])
    client.force_login(woanders)
    antwort = client.post(reverse('verfahren:unterstuetzen', args=[antrag.pk]))
    assert antwort.status_code == 403
    seite = antwort.content.decode()
    assert f'Hauptwohnsitz in Altort bei Einbringung am {tag}' in seite
    assert 'keine örtliche Zuordnung' not in seite
    assert reverse('verfahren:parlament') + '?fokus=region' in seite
    antragsseite = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    assert reverse('verfahren:parlament') + '?fokus=region' in antragsseite


def test_gp058_wiener_konto_ohne_bezirk_wird_zum_gemeindebezirk_gefuehrt(client, ordnung):  # noqa: F811
    """GP-058 (OW-07): Wiener Konten ohne Bezirksangabe sahen „Noch nichts in Ihrem Bezirk“, obwohl
    Bezirksverfahren liefen — ohne Hinweis, dass der Gemeindebezirk fehlt."""
    from mitglieder.models import Gemeinde, Wohnsitzart

    wien = Gemeinde.objects.create(kennziffer='90001', name='Wien', bezirk='Wien', bundesland='wien')
    autor = mitglied_anlegen('autorin', tage=800, gemeinde='Wien', bundesland='wien')
    ohne = mitglied_anlegen('ohnebezirk', tage=800, gemeinde='Wien', bundesland='wien')
    for konto in (autor, ohne):
        konto.wohnsitz, konto.wohnsitz_art = wien, Wohnsitzart.OESTERREICH
        konto.save(update_fields=['wohnsitz', 'wohnsitz_art'])
    autor.wiener_bezirk = '922'
    autor.save(update_fields=['wiener_bezirk'])
    antrag = antrag_einbringen(autor, **ANTRAG, ordnung=ordnung, ebene='bezirk', neuer_teilnehmerkreis=True)
    client.force_login(ohne)
    ziel = reverse('mitglieder:profil') + '#wohnsitz'
    region = _region(client)
    assert 'Noch nichts in Ihrem Bezirk' not in region
    assert f'<a href="{ziel}">Gemeindebezirk wählen' in region
    seite = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    assert f'<a href="{ziel}">Gemeindebezirk wählen' in seite


def test_gp088_fehler_im_einbringformular_sind_mit_dem_feld_verknuepft(client, ordnung):  # noqa: F811
    """GP-088 (ZB-03): aria-describedby der fehlerhaften Felder zeigte ins Leere."""
    import re

    client.force_login(mitglied_anlegen('anna'))
    seite = client.post(reverse('verfahren:einbringen'), {'titel': '', 'wortlaut': '', 'ebene': 'gemeinde'}).content.decode()
    felder = [f for f in re.findall(r'<(?:input|textarea|select)[^>]*aria-invalid="true"[^>]*>', seite)
              if 'aria-describedby=' in f]
    assert len(felder) >= 2  # Titel und Wortlaut
    for feld in felder:
        bezug = re.search(r'aria-describedby="([^"]+)"', feld)
        assert any(k.endswith('_error') for k in bezug.group(1).split()), feld
        for kennung in bezug.group(1).split():
            treffer = re.search(rf'id="{kennung}"[^>]*>(.*?)</', seite, flags=re.S)
            assert treffer and treffer.group(1).strip(), (feld, kennung)
