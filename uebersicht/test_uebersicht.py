"""Übersichtsseite (F-50) und datensparsame Besuchszählung (F-52)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from uebersicht.models import AntragAufruf, TagesBesucher, TagesZahl
from verfahren.models import antrag_einbringen, stimme_abgeben
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db

BROWSER = {"HTTP_USER_AGENT": "Mozilla/5.0 (X11; Linux x86_64; rv:128.0) Gecko/20100101 Firefox/128.0"}


def test_besuche_werden_als_tagessummen_gezaehlt(client):
    client.get("/", **BROWSER)
    client.get("/", **BROWSER)
    assert TagesZahl.objects.get().aufrufe == 2
    assert TagesBesucher.objects.count() == 1  # gleiche Person, gleiche Tageskennung
    client.get("/", HTTP_USER_AGENT="Mozilla/5.0 (iPhone; CPU iPhone OS 17_0) Safari/604.1")
    assert TagesBesucher.objects.count() == 2  # anderes Gerät, neue Kennung — nie eine IP gespeichert


def test_die_seite_nennt_die_gespeicherte_tageskennung_nicht_fluechtig(client):
    """Die Tageskennung steht je Tag in der Datenbank (TagesBesucher) und wird nicht gelöscht; die
    Datenschutzerklärung sagt das. Die Übersicht darf sie nicht „flüchtig“ nennen."""
    client.get("/", **BROWSER)
    assert TagesBesucher.objects.count() == 1
    inhalt = client.get(reverse("uebersicht:index")).content.decode()
    assert "Tageskennung" in inhalt and "flüchtig" not in inhalt


def test_maschinen_und_technikpfade_zaehlen_nicht(client):
    client.get("/", HTTP_USER_AGENT="Mozilla/5.0 (compatible; Googlebot/2.1)")
    client.get("/", HTTP_USER_AGENT="python-requests/2.32")
    client.get("/")  # ohne Browserkennung
    client.get("/gesund/", **BROWSER)
    assert TagesZahl.objects.count() == 0


def test_aufrufe_je_antrag(client, ordnung):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen(), **ANTRAG, ordnung=ordnung)
    client.get(f"/antrag/{antrag.pk}/", **BROWSER)
    client.get(f"/antrag/{antrag.pk}/", **BROWSER)
    eintrag = AntragAufruf.objects.get()
    assert (eintrag.antrag_id, eintrag.aufrufe) == (antrag.pk, 2)


def _entscheiden(antrag):
    """Zeitraffer: Abstimmungsfrist (7 Tage) verstreichen lassen und auszählen."""
    antrag.phase_beginn = timezone.now() - timedelta(days=8)
    antrag.save(update_fields=["phase_beginn"])
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase in ("angenommen", "abgelehnt")
    return antrag


def test_uebersichtsseite_zeigt_kennzahlen_ergebnisse_und_diagramme(client, ordnung):  # noqa: F811
    """Laufend: nur Beteiligung, Tendenz verdeckt (F-15, § 5 Abs 3 lit e) — wie Kachel und Export.
    Erst nach dem Fristende stehen Ja/Nein/Enthaltung samt Ergebnisbalken auf der Seite."""
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:])
    for person, wahl in zip(leute, ["ja", "ja", "nein"], strict=True):
        stimme_abgeben(antrag, person, wahl)
    client.get(f"/antrag/{antrag.pk}/", **BROWSER)

    antwort = client.get(reverse("uebersicht:index"))
    inhalt = antwort.content.decode()
    assert antwort.status_code == 200
    assert antwort.context["mitglieder_gesamt"] == 3
    assert antwort.context["antraege_aktiv"] == 1
    assert "Abstimmung läuft" in inhalt and "Tendenz verdeckt bis Fristende" in inhalt
    assert "3 von 3 Stimmberechtigten" in inhalt and "100 % Beteiligung" in inhalt
    assert "Ja 2" not in inhalt and "Nein 1" not in inhalt, "kein Zwischenstand vor dem Fristende"
    zeile = antwort.context["abstimmungen"][0]
    assert zeile["laeuft"] and zeile["ja"] is None and zeile["nein"] is None and zeile["balken"] == ""
    assert inhalt.count("<svg") >= 2  # Verlaufs- und Balkendiagramme — kein Ergebnisbalken
    assert ANTRAG["titel"] in inhalt  # meistgelesener Antrag mit Aufrufzahl
    assert "ohne Speicherung" in inhalt  # Datenschutz-Erklärung der Zählung

    _entscheiden(antrag)
    inhalt = client.get(reverse("uebersicht:index")).content.decode()
    assert "angenommen" in inhalt and "Abstimmung läuft" not in inhalt
    assert "Ja 2" in inhalt and "Nein 1" in inhalt  # Summen je Abstimmung — nie Einzelstimmen
    assert "3 von 3 Stimmberechtigten" in inhalt and "100 % Beteiligung" in inhalt
    assert inhalt.count("<svg") >= 3  # jetzt mit Ergebnisbalken


def test_entschiedene_personenwahl_zaehlt_ihre_waehler(client, ordnung):  # noqa: F811
    """Eine Kandidatur hat keine Stimmabgaben — ihre Stimmen sind Zustimmungen (§ 7 Abs 1).
    Übersicht und Kennzahl `votes.turnout_mean` müssen die Wähler zählen, nicht 0."""
    from parameter.kennzahlen import werte
    from verfahren.models import bewerbung_einreichen, bewerbung_zustimmen
    from verfahren.test_kandidatur import _in_abstimmung, _kandidatur

    autor, anna, bernd = mitglied_anlegen("autor"), mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    antrag = _kandidatur(ordnung, autor)
    b = bewerbung_einreichen(antrag, anna, "Ich trete an.")
    _in_abstimmung(antrag, [anna, bernd])
    bewerbung_zustimmen(antrag, bernd, b)
    bewerbung_zustimmen(antrag, autor, b)

    inhalt = client.get(reverse("uebersicht:index")).content.decode()
    assert "Personenwahl" in inhalt and "2 von 3 Stimmberechtigten" in inhalt
    assert "Tendenz verdeckt bis Fristende" in inhalt and "Gewählt" not in inhalt

    _entscheiden(antrag)
    antwort = client.get(reverse("uebersicht:index"))
    inhalt = antwort.content.decode()
    assert "angenommen" in inhalt and "2 von 3 Stimmberechtigten" in inhalt and "67 % Beteiligung" in inhalt
    assert f"Gewählt: {anna.anzeigename} mit 2 Zustimmungen" in inhalt  # „Mitglied n“ — nie der Anmeldename
    assert "Ja " not in inhalt.split("Abstimmungen: Ergebnisse")[1].split("KI-Verbrauch")[0]
    assert "0 von 3" not in inhalt
    kennzahlen = werte()
    assert kennzahlen["votes.completed"] == 1 and kennzahlen["votes.turnout_mean"] == round(2 / 3, 4)


def test_uebersicht_begrenzt_entscheidungen_und_fragt_nicht_je_antrag_ab(client, ordnung):  # noqa: F811
    """Entschiedenes verschwindet nie (Grundregel 7) — die öffentliche Seite zieht darum selbst
    eine Grenze (Registerwert) und holt die Stimmen aller gezeigten Anträge mit einer Abfrage,
    statt je Antrag eine zu stellen."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    from parameter.models import Parameter

    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]

    def abgestimmt():
        a = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:])
        stimme_abgeben(a, leute[1], "ja")
        return a

    laufend = abgestimmt()
    _entscheiden(abgestimmt())
    with CaptureQueriesContext(connection) as eine:
        client.get(reverse("uebersicht:index"))
    for _ in range(3):
        _entscheiden(abgestimmt())
    with CaptureQueriesContext(connection) as vier:
        antwort = client.get(reverse("uebersicht:index"))
    assert len(vier) == len(eine), "die Zahl der Abfragen wächst nicht mit den Anträgen"
    assert len(antwort.context["abstimmungen"]) == 5 and antwort.context["abstimmungen_weitere"] == 0

    Parameter.objects.create(schluessel="uebersicht-abstimmungen", wert="2", beschreibung="x", quelle="Test")
    antwort = client.get(reverse("uebersicht:index"))
    zeilen = antwort.context["abstimmungen"]
    assert [z["antrag"].pk for z in zeilen][0] == laufend.pk  # laufende immer, zuerst
    assert len(zeilen) == 3 and antwort.context["abstimmungen_weitere"] == 2
    inhalt = antwort.content.decode()
    assert "2 ältere Entscheidungen sind hier nicht mehr aufgeführt" in inhalt
    assert reverse("verfahren:umsetzung") in inhalt


def test_uebersichtsseite_funktioniert_auch_leer(client):
    antwort = client.get(reverse("uebersicht:index"))
    assert antwort.status_code == 200
    assert "Noch keine Abstimmungen" in antwort.content.decode()


def test_antragstitel_mit_hochkomma_wird_auf_der_uebersicht_kein_markup(client, ordnung):  # noqa: F811
    """Befund #0 (gespeichertes XSS): Der Titel ist frei wählbar und fließt in das aria-label des
    Ergebnisbalkens, den die Seite mit |safe rendert. Ein Hochkomma darf dort nie ein Attribut
    beenden — sonst feuert `onload` bei jedem Besucher der anmeldefreien Seite."""
    from html import unescape

    leute = [mitglied_anlegen(f"x{i}") for i in range(3)]
    titel = "x' onload='alert(1)' data-x='"
    antrag = in_abstimmung_bringen(
        antrag_einbringen(leute[0], **{**ANTRAG, "titel": titel}, ordnung=ordnung), leute[1:]
    )
    stimme_abgeben(antrag, leute[1], "ja")
    # Laufende Abstimmungen zeigen seit Befund #4 keinen Ergebnisbalken — erst die Entscheidung
    antrag.phase_beginn = timezone.now() - timedelta(days=8)
    antrag.save(update_fields=["phase_beginn"])
    antrag.fortschreiben()
    inhalt = client.get(reverse("uebersicht:index")).content.decode()
    import xml.etree.ElementTree as ET

    assert "onload='alert(1)'" not in inhalt and 'onload="alert(1)"' not in inhalt
    balken = [s[: s.index("</svg>") + 6] for s in inhalt.split("<svg")[1:] if "aria-label='Ergebnis" in s]
    assert balken, "der Ergebnisbalken fehlt auf der Seite"
    for svg in balken:
        wurzel = ET.fromstring("<svg" + svg)  # wohlgeformt — der Titel hat die Struktur nicht verändert
        assert all("onload" not in e.attrib for e in wurzel.iter())
        assert "alert(1)" in unescape(wurzel.get("aria-label"))  # der Titel steht drin — als Text


def test_z3_die_seite_liest_reihung_und_hoechstzahl_aus_der_kernregel(client, ordnung, monkeypatch):  # noqa: F811
    """Z-3: Die Ansicht rechnete „Meistgelesene Anträge“ selbst (order_by("-gesamt")[:5]), neben der
    Regel in plattform_core/meistgelesen.py. Sie liest jetzt deren Konstanten — ändert sich die Regel,
    ändert sich die Seite mit, und Verzeichnis und Seite können nicht auseinanderlaufen."""
    from plattform_core import meistgelesen

    autor = mitglied_anlegen("autor")
    heute = timezone.localdate()
    for nummer, aufrufe in enumerate([4, 9, 1, 7]):
        antrag = antrag_einbringen(autor, **{**ANTRAG, "titel": f"Antrag {nummer}"}, ordnung=ordnung)
        AntragAufruf.objects.create(antrag=antrag, datum=heute - timedelta(days=1), aufrufe=aufrufe)

    def gezeigt():
        return [z["aufrufe"] for z in client.get(reverse("uebersicht:index")).context["meistgelesen"]]

    assert gezeigt() == [9, 7, 4, 1]  # Verhalten unverändert: Summe absteigend, höchstens fünf
    monkeypatch.setattr(meistgelesen, "HOECHSTZAHL", 2)
    assert gezeigt() == [9, 7]
    monkeypatch.setattr(meistgelesen, "REIHUNG", ("gesamt",))
    assert gezeigt() == [1, 4]


def test_gp134_gleichstand_steht_nach_antragsnummer_und_die_liste_verlinkt_die_regel(client, ordnung):  # noqa: F811
    """GP-134 (RVA-24, RVB-12): Bei gleicher Summe stand vorn, was die Datenbank lieferte. Jetzt
    steht der Antrag mit der kleineren Nummer vorn — auch wenn seine Tageszahlen später angelegt
    wurden —, und die Liste nennt ihre Regel."""
    autor = mitglied_anlegen("autor")
    heute = timezone.localdate()
    antraege = [antrag_einbringen(autor, **{**ANTRAG, "titel": f"Antrag {n}"}, ordnung=ordnung) for n in range(4)]
    # Tageszahlen in umgekehrter Reihenfolge anlegen: Die Einfügereihenfolge darf nicht entscheiden.
    for antrag, aufrufe in reversed(list(zip(antraege, [6, 6, 9, 6], strict=True))):
        AntragAufruf.objects.create(antrag=antrag, datum=heute, aufrufe=aufrufe)
    seite = client.get(reverse("uebersicht:index"))
    gezeigt = [(z["antrag"].pk, z["aufrufe"]) for z in seite.context["meistgelesen"]]
    assert gezeigt == [(antraege[2].pk, 9), (antraege[0].pk, 6), (antraege[1].pk, 6), (antraege[3].pk, 6)]
    assert f'href="{reverse("parameter:regeln")}#regel-meistgelesen"' in seite.content.decode()


def test_gp126_die_phasenaufstellung_summiert_auf_die_gesamtzahl(client, ordnung):  # noqa: F811
    '''GP-126 (GAST-12, RVB-13): Die Phasenzeile kannte nur fünf Phasen; verfallene, zurückgezogene
    und zurückgewiesene Anträge steckten in „insgesamt“, fehlten aber in der Aufstellung. Mit je
    einem Antrag jeder Phase ergeben die Teile die Gesamtzahl.'''
    from plattform_core import Phase
    from verfahren.models import Antrag

    autor = mitglied_anlegen('autor')
    for phase in Phase:
        a = antrag_einbringen(autor, **ANTRAG, ordnung=ordnung)
        Antrag.objects.filter(pk=a.pk).update(phase=phase.value)
    antwort = client.get(reverse('uebersicht:index'))
    teile = [anzahl for _name, anzahl in antwort.context['je_phase']]
    assert antwort.context['antraege_gesamt'] == len(Phase) == sum(teile)
    assert all(anzahl == 1 for anzahl in teile)
    inhalt = antwort.content.decode()
    for wort in ('verfallen', 'zurückgezogen', 'zurückgewiesen'):
        assert wort in inhalt, wort


def test_gp191_vierhundert_laufende_abstimmungen_blaettern_ohne_javascript(client, ordnung):  # noqa: F811
    '''GP-191 (SU-09): Die Übersicht zeigte jede laufende Abstimmung auf einer Seite; die Antwort
    wuchs mit dem Bestand. Bei 400 laufenden bleibt jede Seite unter 150 KiB, nennt die Gesamtzahl
    und verweist mit einem gewöhnlichen Link auf die nächste Seite.'''
    import re

    from verfahren.models import Antrag

    autor = mitglied_anlegen('autor')
    vorlage = antrag_einbringen(autor, **ANTRAG, ordnung=ordnung)
    Antrag.objects.filter(pk=vorlage.pk).update(phase='abstimmung', stimmberechtigte_anzahl=5)
    vorlage.refresh_from_db()
    kopien = []
    for i in range(399):
        kopie = Antrag.objects.get(pk=vorlage.pk)
        kopie.pk = None
        kopie.titel = f'Abstimmung {i:03d}'
        kopien.append(kopie)
    Antrag.objects.bulk_create(kopien)
    assert Antrag.objects.filter(phase='abstimmung').count() == 400

    adresse = reverse('uebersicht:index')
    gesehen = set()
    seiten = 0
    while adresse:
        antwort = client.get(adresse)
        assert antwort.status_code == 200
        assert len(antwort.content) < 150 * 1024, len(antwort.content)
        inhalt = antwort.content.decode()
        assert '400 laufende Abstimmungen' in inhalt
        gesehen |= {z['antrag'].pk for z in antwort.context['abstimmungen']}
        weiter = re.search(r'<a href="(\?seite=\d+)">ältere →</a>', inhalt)
        adresse = reverse('uebersicht:index') + weiter.group(1) if weiter else None
        seiten += 1
        assert seiten < 20
    assert seiten > 1 and len(gesehen) == 400
