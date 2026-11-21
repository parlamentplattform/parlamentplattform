"""Zweite Behebungsrunde nach der Gesamtprüfung (0.115): Parlament und Listen.

Je Befund ein Abschnitt; die Kennung steht im Testnamen. Großbestände entstehen mit
`bulk_create` als Kopien eines regulär eingebrachten Antrags (dieselbe eingefrorene Ordnung)."""

import copy
import re
from datetime import timedelta

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from verfahren.models import Antrag, antrag_einbringen
from verfahren.test_oertliche_teilnahme import menschen  # noqa: F401
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def _kopien(vorlage, anzahl, phase, jetzt, titel="Lastprobe", **extra):
    """`anzahl` Kopien der Vorlage in `phase`, je eine Minute später begonnen — ein Zeitpunkt für alle."""
    neue = []
    for i in range(anzahl):
        a = Antrag(
            titel=f"{titel} {phase} {i:04d}", art=vorlage.art, phase=phase,
            eingebracht_von_id=vorlage.eingebracht_von_id,
            eingebracht_am=jetzt - timedelta(days=3, minutes=i),
            phase_beginn=jetzt - timedelta(days=1, minutes=i),
            policy_snapshot=copy.deepcopy(vorlage.policy_snapshot), ebene=vorlage.ebene, gebiet=vorlage.gebiet,
            **extra,
        )
        if phase in ("abstimmung", "angenommen", "abgelehnt"):
            a.stimmberechtigte_anzahl = 10
            a.stimmberechtigung_stichtag = timezone.localdate(a.phase_beginn)
        neue.append(a)
    Antrag.objects.bulk_create(neue, batch_size=300)
    return list(Antrag.objects.filter(titel__startswith=f"{titel} {phase} ").order_by("pk"))


def _bestand(ordnung, je_phase, abgeschlossen=0):  # noqa: F811
    person = mitglied_anlegen("lastperson")
    vorlage = antrag_einbringen(person, **ANTRAG, ordnung=ordnung)
    jetzt = timezone.now()
    for phase in ("unterstuetzung", "beratung", "abstimmung"):
        _kopien(vorlage, je_phase, phase, jetzt)
    if abgeschlossen:
        _kopien(vorlage, abgeschlossen, "angenommen", jetzt)
    return person, vorlage


def _feld(html, name):
    return html.split(f'id="feld-{name}"')[1].split("</section>")[0]


# ── GP-051: Parlament wächst ungebremst (D-B1a) ────────────────────────────────────────────────


def test_gp051_parlament_bleibt_bei_2000_verfahren_klein(client, ordnung):  # noqa: F811
    _bestand(ordnung, 667, abgeschlossen=26)
    antwort = client.get(reverse("verfahren:parlament"))
    groesse = len(antwort.content)
    assert groesse < 400 * 1024, f"{groesse // 1024} KiB"
    feld = _feld(antwort.content.decode(), "filter")
    # Jede Gruppe nennt die Gesamtzahl und führt ohne JavaScript weiter
    for schluessel in ("abstimmung", "beratung", "unterstuetzung"):
        assert f'href="?mehr={schluessel}#feld-filter"' in feld
    assert feld.count('class="fz') <= 3 * 60 + 20
    # Auch für ein Mitglied mit Handlungsknöpfen in jeder Zeile
    client.force_login(mitglied_anlegen("zweite"))
    groesse = len(client.get(reverse("verfahren:parlament")).content)
    assert groesse < 400 * 1024, f"{groesse // 1024} KiB"


def test_gp051_abfragezahl_waechst_nicht_mit_dem_bestand(client, ordnung):  # noqa: F811
    person, vorlage = _bestand(ordnung, 3, abgeschlossen=21)
    with CaptureQueriesContext(connection) as klein:
        client.get(reverse("verfahren:parlament"))
    jetzt = timezone.now()
    for phase in ("unterstuetzung", "beratung", "abstimmung"):
        _kopien(vorlage, 80, phase, jetzt, titel="Nachschub")
    _kopien(vorlage, 40, "angenommen", jetzt, titel="Nachschub")
    with CaptureQueriesContext(connection) as gross:
        client.get(reverse("verfahren:parlament"))
    assert len(gross.captured_queries) == len(klein.captured_queries)


def test_gp051_mehr_blaettert_ohne_javascript(client, ordnung):  # noqa: F811
    _bestand(ordnung, 130)
    seite1 = _feld(client.get(reverse("verfahren:parlament") + "?mehr=abstimmung").content.decode(), "filter")
    assert seite1.count('class="fz') == 60
    assert "130" in seite1
    weiter = re.search(r'href="(\?mehr=abstimmung&amp;seite=2)#feld-filter"', seite1)
    assert weiter, seite1[:2000]
    seite2 = _feld(client.get(reverse("verfahren:parlament") + "?mehr=abstimmung&seite=2").content.decode(), "filter")
    seite3 = _feld(client.get(reverse("verfahren:parlament") + "?mehr=abstimmung&seite=3").content.decode(), "filter")
    assert seite2.count('class="fz') == 60 and seite3.count('class="fz') == 10
    titel = set()
    for teil in (seite1, seite2, seite3):
        titel |= set(re.findall(r"Lastprobe abstimmung \d{4}", teil))
    assert len(titel) == 130
    # Unbekannte Gruppe oder Seite: die gewöhnliche Übersicht, kein Fehler
    for adresse in ("?mehr=xyz", "?mehr=abstimmung&seite=99", "?mehr=abstimmung&seite=²"):
        assert client.get(reverse("verfahren:parlament") + adresse).status_code == 200


def test_gp051_beendete_verfahren_mit_zwei_klicks(client, ordnung):  # noqa: F811
    _bestand(ordnung, 1, abgeschlossen=26)
    feld = _feld(client.get(reverse("verfahren:parlament")).content.decode(), "filter")
    assert 'href="?mehr=abgeschlossen#feld-filter"' in feld  # erster Klick
    mehr = _feld(client.get(reverse("verfahren:parlament") + "?mehr=abgeschlossen").content.decode(), "filter")
    for a in Antrag.objects.filter(phase="angenommen"):
        assert reverse("verfahren:antrag", args=[a.pk]) in mehr  # zweiter Klick


def test_gp051_mehr_wirkt_auch_mit_eigener_reihung(client, ordnung):  # noqa: F811
    """Mit gestellten Reglern fehlt die Gruppe „Abgeschlossen“ im Feed — ?mehr= erreicht sie trotzdem."""
    from verfahren.models import FilterProfil

    person, _vorlage = _bestand(ordnung, 1, abgeschlossen=3)
    FilterProfil.objects.create(mitglied=person, name="Eigen", aktiv=True, regler={"chronologisch": 60})
    client.force_login(person)
    mehr = _feld(client.get(reverse("verfahren:parlament") + "?mehr=abgeschlossen").content.decode(), "filter")
    assert mehr.count("Lastprobe angenommen") == 3


# ── GP-052: Der Stern nennt einen Ort, den es gibt ──────────────────────────────────────────────


def test_gp052_gemerkter_antrag_auf_rang_601_ist_einen_klick_entfernt(client, ordnung):  # noqa: F811
    person, vorlage = _bestand(ordnung, 0)
    sammelnd = _kopien(vorlage, 650, "unterstuetzung", timezone.now(), titel="Tief")
    ziel = sammelnd[49]  # je kleiner i, desto später die Frist: Rang 601 von 650
    leser = mitglied_anlegen("leserin")
    client.force_login(leser)
    antwort = client.post(
        reverse("verfahren:favorisieren", args=[ziel.pk]), {"weiter": "/parlament/"}, follow=True
    )
    meldung = " ".join(str(m) for m in antwort.context["messages"])
    assert "Startseite" not in meldung
    assert "★ Gemerkt" in meldung
    feld = _feld(antwort.content.decode(), "filter")
    assert 'href="?mehr=gemerkt#feld-filter"' in feld and "★ Gemerkt · 1" in feld  # der eine Klick
    assert reverse("verfahren:antrag", args=[ziel.pk]) not in feld  # Rang 601: nicht in der ersten Seite
    gemerkt = _feld(client.get(reverse("verfahren:parlament") + "?mehr=gemerkt").content.decode(), "filter")
    assert reverse("verfahren:antrag", args=[ziel.pk]) in gemerkt
    assert gemerkt.count('class="fz') == 1
    # Ein Gast hat keine gemerkten Anträge: ?mehr=gemerkt zeigt die gewöhnliche Übersicht
    client.logout()
    gast = _feld(client.get(reverse("verfahren:parlament") + "?mehr=gemerkt").content.decode(), "filter")
    assert "Gemerkt" not in gast


def test_gp051_seitenrechnung_der_regel():
    from plattform_core.parlamentlisten import nach_fristende, neutral, seite

    s = seite(130, 60, 3)
    assert (s.nummer, s.seiten, s.von, s.bis, s.zurueck, s.weiter) == (3, 3, 121, 130, 2, None)
    assert seite(130, 60, 99).nummer == 3 and seite(130, 60, None).nummer == 1 and seite(130, 60, 0).nummer == 1
    leer = seite(0, 60, 1)
    assert (leer.seiten, leer.von, leer.bis, leer.weiter) == (1, 1, 0, None)
    alles = seite(7, 0, 1)
    assert (alles.seiten, alles.bis) == (1, 7)
    jetzt = timezone.now()
    frueh, spaet = jetzt, jetzt + timedelta(days=1)
    assert sorted([neutral("unterstuetzung", frueh, jetzt, 1), neutral("abstimmung", spaet, jetzt, 2)])[0][0] == 0
    assert neutral("angenommen", None, jetzt, 3) == (9, jetzt, 3)
    assert nach_fristende(None, jetzt, 4) < nach_fristende(spaet, jetzt, 1)


# ── GP-073: Wichtige Abstimmungen nach Fristende, mit Regel und Gesamtzahl ─────────────────────


def test_gp073_hervorhebungen_nach_fristende_mit_regel_und_gesamtzahl(client, ordnung):  # noqa: F811
    person, vorlage = _bestand(ordnung, 0)
    jetzt = timezone.now()
    # Drei ältere Anträge in Beratung (Frist in elf Tagen), zwei jüngere Abstimmungen (Frist in sechs Tagen)
    beratung = _kopien(vorlage, 3, "beratung", jetzt, titel="Alt", hervorgehoben=True)
    Antrag.objects.filter(pk__in=[a.pk for a in beratung]).update(phase_beginn=jetzt - timedelta(days=10))
    abstimmung = _kopien(vorlage, 2, "abstimmung", jetzt, titel="Neu", hervorgehoben=True)
    for feld_url in (reverse("verfahren:parlament"), "/"):
        html = client.get(feld_url).content.decode()
        teil = _feld(html, "wichtig") if feld_url != "/" else html.split('class="willkommen-wichtig')[1]
        reihe = [int(n) for n in re.findall(r'href="/antrag/(\d+)/', teil)]
        reihe = list(dict.fromkeys(reihe))
        assert reihe[:2] == [a.pk for a in sorted(abstimmung, key=lambda a: a.phase_beginn)], feld_url
    kopf = _feld(client.get(reverse("verfahren:parlament")).content.decode(), "wichtig").split("</div>")[0]
    assert "3 von 5" in kopf
    assert f'href="{reverse("parameter:regeln")}#regel-parlamentlisten"' in kopf
    assert "nach Fristende" in kopf
    # Alle fünf gezeigt: die ganze Reihe folgt dem Fristende (gleiche Frist: kleinere Antragsnummer zuerst)
    from parameter.models import Parameter
    from verfahren.views import _frist_fuer

    Parameter.objects.update_or_create(schluessel="kacheln-hervorgehoben", defaults={"wert": "5"})
    teil = _feld(client.get(reverse("verfahren:parlament")).content.decode(), "wichtig")
    reihe = list(dict.fromkeys(int(n) for n in re.findall(r'href="/antrag/(\d+)/', teil)))
    alle = Antrag.objects.filter(pk__in=[a.pk for a in beratung + abstimmung])
    erwartet = sorted(alle, key=lambda a: (_frist_fuer(a, a.policy()), a.pk))
    assert reihe == [a.pk for a in erwartet]


# ── GP-075: Vom Lebensbereich zu seinen Anträgen, Suche über den Titel ─────────────────────────


def _ast():
    from verfahren.models import Kategorie

    wurzel = Kategorie.objects.filter(eltern__isnull=True).first() or Kategorie.objects.create(slug="gp-wurzel", name="W")
    oben = Kategorie.objects.create(slug="gp-verkehr", name="Verkehrswesen", eltern=wurzel)
    unten = Kategorie.objects.create(slug="gp-radwege", name="Radwegenetz", eltern=oben)
    fremd = Kategorie.objects.create(slug="gp-kultur", name="Kulturförderung", eltern=wurzel)
    return oben, unten, fremd


def test_gp075_lebensbereich_verlinkt_jeden_laufenden_antrag_des_astes(client, ordnung):  # noqa: F811
    person, vorlage = _bestand(ordnung, 0)
    oben, unten, fremd = _ast()
    jetzt = timezone.now()
    im_ast = _kopien(vorlage, 3, "beratung", jetzt, titel="Ast") + _kopien(vorlage, 2, "abstimmung", jetzt, titel="Ast")
    for i, a in enumerate(im_ast):
        a.kategorien.add(unten if i % 2 else oben)
    daneben = _kopien(vorlage, 1, "beratung", jetzt, titel="Daneben")[0]
    daneben.kategorien.add(fremd)
    beendet = _kopien(vorlage, 1, "angenommen", jetzt, titel="Ast")[0]
    beendet.kategorien.add(oben)
    feld = _feld(client.get(reverse("verfahren:parlament") + "?fach=gp-verkehr").content.decode(), "favoriten")
    for a in im_ast:
        assert f'href="{reverse("verfahren:antrag", args=[a.pk])}"' in feld
    assert reverse("verfahren:antrag", args=[daneben.pk]) not in feld
    assert reverse("verfahren:antrag", args=[beendet.pk]) not in feld
    # Neutrale Ordnung: die Abstimmungen zuerst
    reihe = list(dict.fromkeys(int(n) for n in re.findall(r'href="/antrag/(\d+)/"', feld)))
    assert {reihe[0], reihe[1]} == {a.pk for a in im_ast if a.phase == "abstimmung"}
    # Der Unterbereich zeigt nur seine eigenen
    unter = _feld(client.get(reverse("verfahren:parlament") + "?fach=gp-radwege").content.decode(), "favoriten")
    assert sum(reverse("verfahren:antrag", args=[a.pk]) in unter for a in im_ast) == 2


def test_gp075_suche_findet_den_antrag_ueber_ein_titelwort(client, ordnung):  # noqa: F811
    person, vorlage = _bestand(ordnung, 0)
    jetzt = timezone.now()
    laufend = _kopien(vorlage, 1, "beratung", jetzt, titel="Bürgerhaushalt Zwiebelturm")[0]
    beendet = _kopien(vorlage, 1, "angenommen", jetzt, titel="Bürgerhaushalt Zwiebelturm")[0]
    feld = _feld(client.get(reverse("verfahren:parlament") + "?suche=zwiebelturm").content.decode(), "favoriten")
    assert reverse("verfahren:antrag", args=[laufend.pk]) in feld
    assert reverse("verfahren:antrag", args=[beendet.pk]) in feld
    assert feld.index(reverse("verfahren:antrag", args=[laufend.pk])) < feld.index(
        reverse("verfahren:antrag", args=[beendet.pk])
    )


# ── GP-074: Jede Liste nennt ihre Reihungsregel ────────────────────────────────────────────────


def test_gp074_jedes_feld_mit_mehreren_antraegen_verweist_auf_seine_regel(client, ordnung):  # noqa: F811
    from verfahren.models import FilterProfil

    person = mitglied_anlegen("ortsperson")
    ort = {"ebene": "gemeinde", "gebiet": "St. Marienkirchen an der Polsenz"}
    vorlage = antrag_einbringen(person, **ANTRAG, ordnung=ordnung, **ort)
    jetzt = timezone.now()
    oben, unten, _fremd = _ast()
    sammelnd = _kopien(vorlage, 2, "unterstuetzung", jetzt, titel="Regionsliste", hervorgehoben=True)
    abstimmung = _kopien(vorlage, 1, "abstimmung", jetzt, titel="Regionsliste", hervorgehoben=True)
    for a in sammelnd + abstimmung:
        a.kategorien.add(oben)
    regeln = reverse("parameter:regeln")
    for wer in (None, person):
        if wer is not None:
            client.force_login(wer)
        html = client.get(reverse("verfahren:parlament")).content.decode()
        for feld in ("filter", "wichtig", "region"):
            assert f'href="{regeln}#regel-parlamentlisten"' in _feld(html, feld), (wer, feld)
        for adresse in ("?fach=gp-verkehr", "?suche=Regionsliste"):
            teil = _feld(client.get(reverse("verfahren:parlament") + adresse).content.decode(), "favoriten")
            assert f'href="{regeln}#regel-parlamentlisten"' in teil, (wer, adresse)
        # Meine Region in neutraler Ordnung: die laufende Abstimmung zuerst
        region = _feld(html, "region")
        reihe = list(dict.fromkeys(int(n) for n in re.findall(r'href="/antrag/(\d+)/', region)))
        assert reihe[0] == abstimmung[0].pk, reihe
    # Mit eigenem Profil verweist der Feldkopf auf die Regel des WeicherFilters
    FilterProfil.objects.create(mitglied=person, name="Eigen", aktiv=True, regler={"chronologisch": 60})
    kopf = _feld(client.get(reverse("verfahren:parlament")).content.decode(), "filter")
    assert f'href="{regeln}#regel-weicherfilter"' in kopf


def test_gp074_abgeschnittene_lebensbereichsuche_nennt_die_gesamtzahl(client, ordnung, settings):  # noqa: F811
    from parameter.models import Parameter
    from verfahren.models import Kategorie

    wurzel = Kategorie.objects.filter(eltern__isnull=True).first() or Kategorie.objects.create(slug="gp-w", name="W")
    for i in range(5):
        Kategorie.objects.create(slug=f"gp-wasser-{i}", name=f"Gewässerschutz {i}", eltern=wurzel)
    Parameter.objects.update_or_create(schluessel="suche-treffer-hoechstzahl", defaults={"wert": "2"})
    feld = _feld(client.get(reverse("verfahren:parlament") + "?suche=Gewässerschutz").content.decode(), "favoriten")
    assert feld.count('class="treffer-link"') == 2
    assert "2 von 5" in feld


# ── GP-175 (Rest): Am letzten Tag nennen Kachel und Zeile die Uhrzeit ──────────────────────────


def test_gp175_am_letzten_tag_endet_heute_um_uhrzeit(ordnung):  # noqa: F811
    from datetime import datetime
    from zoneinfo import ZoneInfo

    from django.template.loader import render_to_string
    from django.test import RequestFactory

    from verfahren.views import _kachel

    wien = ZoneInfo("Europe/Vienna")
    person = mitglied_anlegen("fristperson")
    antrag = antrag_einbringen(person, **ANTRAG, ordnung=ordnung)
    tage = antrag.policy().unterstuetzung_frist_tage
    frist = datetime(2026, 11, 19, 12, 41, tzinfo=wien)
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=frist - timedelta(days=tage))
    antrag.refresh_from_db()
    jetzt = datetime(2026, 11, 19, 8, 0, tzinfo=wien)  # ein fester Zeitpunkt am letzten Tag
    k = _kachel(antrag, jetzt, nutzer=person)
    assert k["resttage"] == 0 and k["frist"] == frist
    anfrage = RequestFactory().get("/parlament/")
    anfrage.user = person
    kachel = render_to_string("verfahren/_kachel.html", {"k": k, "user": person}, request=anfrage)
    zeile = render_to_string("verfahren/_filter_zeile.html", {"z": k, "meine_unterstuetzungen": set()}, request=anfrage)
    for teil in (kachel, zeile):
        assert "endet heute um 12:41" in teil


# ── GP-109: Zahlenparameter öffentlicher Ansichten antworten ohne Ausnahme ─────────────────────

SELTSAME_ZAHLEN = ("²", "１２", "9" * 26, "-3", "1.5", "")


@pytest.mark.parametrize("wert", SELTSAME_ZAHLEN)
def test_gp109_zahlenparameter_ohne_serverfehler(client, ordnung, wert):  # noqa: F811
    person, vorlage = _bestand(ordnung, 1)
    _ast()
    seite = reverse("verfahren:antrag", args=[vorlage.pk])
    parlament = reverse("verfahren:parlament")
    adressen = [
        f"{seite}?ab={wert}", f"{seite}?antwort_auf={wert}",
        f"{parlament}?mehr=abstimmung&seite={wert}", f"{parlament}?mehr=gemerkt&seite={wert}",
        f"{parlament}?fach=gp-verkehr&ast_seite={wert}",
    ]
    client.raise_request_exception = False
    for adresse in adressen:
        assert client.get(adresse).status_code == 200, adresse
    client.force_login(person)
    for adresse in adressen + [f"{reverse('verfahren:gespraeche')}?seite={wert}"]:
        assert client.get(adresse).status_code == 200, adresse
    antwort = client.post(
        reverse("verfahren:kommentieren", args=[vorlage.pk]),
        {"text": "Ein Beitrag mit seltsamer Bezugszahl.", "antwort_auf": wert, "bezug_absatz": wert},
    )
    assert antwort.status_code in (200, 302), antwort.status_code


# ── GP-191 (Teil verfahren): Das Umsetzungsregister blättert ───────────────────────────────────


def test_gp191_umsetzungsregister_mit_400_beschluessen_blaettert(client, ordnung):  # noqa: F811
    from verfahren.views import REGISTER_SEITE

    person, vorlage = _bestand(ordnung, 0)
    beschluesse = _kopien(vorlage, 400, "angenommen", timezone.now(), titel="Beschluss")
    antwort = client.get(reverse("verfahren:umsetzung"))
    html = antwort.content.decode()
    assert len(antwort.content) < 150 * 1024, f"{len(antwort.content) // 1024} KiB"
    assert f"1–{REGISTER_SEITE} von 400" in html
    assert 'href="?seite=2"' in html
    gesehen = set()
    seite = 1
    while True:
        html = client.get(reverse("verfahren:umsetzung") + f"?seite={seite}").content.decode()
        gesehen |= {int(n) for n in re.findall(r'href="/antrag/(\d+)/"><strong>Beschluss', html)}
        if f'href="?seite={seite + 1}"' not in html:
            break
        seite += 1
    assert gesehen == {a.pk for a in beschluesse}
    # Der Filter nach Stand bleibt beim Blättern erhalten
    gefiltert = client.get(reverse("verfahren:umsetzung") + "?status=offen").content.decode()
    assert 'href="?status=offen&amp;seite=2"' in gefiltert


# ── GP-078 (Teil verfahren): Ein Gemeindekonto ist kein Gast ───────────────────────────────────


def _gemeindekonto():
    from mitglieder.models import Mitglied

    return Mitglied.objects.create_user(
        "einwohnerin-gp078@example.org", email="einwohnerin-gp078@example.org", parteikonto=False,
    )


def test_gp078_gemeindekonto_im_parlament_weder_gast_noch_anmeldeverweis(client, ordnung):  # noqa: F811
    person, vorlage = _bestand(ordnung, 2)
    Antrag.objects.filter(phase="abstimmung").update(hervorgehoben=True)
    login = reverse("mitglieder:login")
    # Gegenprobe: Ein Gast wird als Gast angesprochen und zur Anmeldung geführt
    gast = client.get(reverse("verfahren:parlament")).content.decode()
    assert "als Gast" in gast and f'href="{login}' in gast
    client.force_login(_gemeindekonto())
    for adresse in (reverse("verfahren:parlament"), reverse("verfahren:antrag", args=[vorlage.pk])):
        html = client.get(adresse).content.decode()
        assert "als Gast" not in html, adresse
        assert f'href="{login}' not in html, adresse
        assert f'href="{reverse("gemeinde:konto")}"' in html, adresse
    tabs = client.get(reverse("verfahren:parlament")).content.decode().split('class="tabs"')[1].split("</nav>")[0]
    assert reverse("verfahren:einbringen") not in tabs  # kein Plus, das in die Anmeldung führt


# ── Z-5 (E-05): Hinweis beim Einbringen, wenn die Schwelle im Ortskreis nicht erreichbar ist ───


def test_z5_hinweis_wenn_die_schwelle_im_ortskreis_nicht_erreichbar_ist(client, ordnung, menschen):  # noqa: F811
    from mitglieder.models import Identitaetsstufe, Mitglied

    leute, _ort, _fremdort = menschen
    client.force_login(leute["autor"])
    # Gleichort: die einbringende Person und eine zweite, ungeprüfte — unterstützen kann nur eine; Schwelle 2
    Mitglied.objects.filter(pk=leute["ort"].pk).update(identitaetsstufe=Identitaetsstufe.UNGEPRUEFT)
    seite = client.get(reverse("verfahren:einbringen")).content.decode()
    hinweis = seite.split('id="schwelle-hinweis"')[1].split("</div>")[0]
    assert "Gleichort" in hinweis and "Eferding" in hinweis  # Gemeinde und Bezirk
    assert "Oberösterreich" not in hinweis  # im Land unterstützt auch die Person aus Schärding
    assert "2 Unterstützungen" in hinweis
    # Ein Hinweis, keine Sperre: Einbringen bleibt möglich
    antwort = client.post(reverse("verfahren:einbringen"), {**ANTRAG, "ebene": "gemeinde", "art": "sache", "trotzdem": "1"})
    assert antwort.status_code == 302
    # Mit zwei Unterstützungsberechtigten ist die Schwelle erreichbar: kein Hinweis
    Mitglied.objects.filter(pk=leute["ort"].pk).update(identitaetsstufe=Identitaetsstufe.GEPRUEFT)
    assert 'id="schwelle-hinweis"' not in client.get(reverse("verfahren:einbringen")).content.decode()


def test_z5_kein_hinweis_ohne_oertliche_wahl(client, ordnung):  # noqa: F811
    client.force_login(mitglied_anlegen("bundesperson"))
    assert 'id="schwelle-hinweis"' not in client.get(reverse("verfahren:einbringen")).content.decode()
