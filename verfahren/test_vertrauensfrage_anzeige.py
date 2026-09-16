"""S10c, Cluster R — die Vertrauensfrage (§ 7 Abs 10) in der Anzeige und in den Handlungen:
Unterstützen nur mit Stimmrecht für Personenwahlen am Einbringungstag (lit c), Abstimmen als
Personenwahl (lit e), die Rückgabezusage im Bewerbungsformular (§ 7 Abs 3), die Antragsseite mit
Kopfzeile, Bändern, Anlässen, Stellungnahmen und Legende, das Ergebnis in Satzungsworten
(verloren/gewonnen), Kachel, Feed-Zeile, Übersicht, Archiv — und die Abfragezahl."""

import itertools
import json
from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone

from gremien.test_integritaet import rat
from mandatare import models as mm
from mandatare.models import (
    Aufgabe,
    Mandat,
    Stellungnahme,
    Vertrauensfrage,
    vertrauensfrage_anfechtung_vermerken,
)
from plattform_core import Gegenstand
from plattform_core.eligibility import monate_addieren
from verfahren import archiv as archivkern
from verfahren.models import Antrag, Antragsart, Bewerbung, Unterstuetzung, antrag_einbringen, stimme_abgeben
from verfahren.test_vertrauensfrage import (  # noqa: F401
    _feststellung,
    _verloren,
    abstimmen,
    abweichung,
    altmandat,
    einbringen,
    tage,
    unterstuetzen,
)
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401
from verfahren.views import _regeln_lesbar, vertrauensfrage_unterstuetzen_erlaubt

pytestmark = pytest.mark.django_db

_N = itertools.count(1)
GEMEINDE = "St. Marienkirchen an der Polsenz"  # der Wohnsitz aus `mitglied_anlegen` — für das Regionsband


@pytest.fixture
def mandat_daheim(monkeypatch):
    """Ein Altmandat in der Gemeinde der Testmitglieder — so erscheint die Vertrauensfrage im Regionsband."""
    monkeypatch.setattr(mm, "INKRAFTTRETEN_ABS_10", date(2025, 1, 1))
    return Mandat.objects.create(
        mitglied=mitglied_anlegen(f"daheim{next(_N)}", tage=600),
        bezeichnung="Gemeinderätin",
        ebene="gemeinde",
        gebiet=GEMEINDE,
        angetreten=date(2025, 1, 1),
    )


def _seite(client, antrag):
    return client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()


def _kopf(inhalt):
    return inhalt.split('class="a-kopf"')[1].split("</header>")[0]


# ── Unterstützen (lit c) ───────────────────────────────────────────────────────────────────


def test_unterstuetzen_nur_mit_personenwahl_stimmrecht_am_einbringungstag(client, ordnung, altmandat, settings):  # noqa: F811
    settings.DDOE_UEBERGANGSREGEL = False
    alt = mitglied_anlegen("alt", tage=400)
    jung = mitglied_anlegen("jung", tage=100)  # für Sachfragen stimmberechtigt, für Personenwahlen nicht
    antrag = einbringen(alt, altmandat, ordnung)
    ziel = reverse("verfahren:unterstuetzen", args=[antrag.pk])

    client.force_login(jung)
    antwort = client.post(ziel)
    assert antwort.status_code == 403
    assert "verfahren/vertrauensfrage_nur_stimmberechtigte.html" in [t.name for t in antwort.templates]
    inhalt = antwort.content.decode()
    assert "§ 7 Abs 10 lit c" in inhalt and timezone.localdate(antrag.eingebracht_am).strftime("%d.%m.%Y") in inhalt
    assert not Unterstuetzung.objects.filter(antrag=antrag, mitglied=jung).exists()
    # Auf der Antragsseite: kein Knopf, ein Satz
    seite = _seite(client, antrag)
    assert f'action="{ziel}"' not in seite
    assert "Unterstützen kann nur, wer am Tag der Einbringung" in seite

    client.force_login(alt)
    seite = _seite(client, antrag)
    assert f'action="{ziel}"' in seite and "Diesen Antrag unterstützen" in seite
    antwort = client.post(ziel)
    assert antwort.status_code == 302
    assert Unterstuetzung.objects.filter(antrag=antrag, mitglied=alt, zurueckgezogen_am__isnull=True).exists()

    # Ein Sachantrag bleibt für jedes bestätigte Mitglied unterstützbar (§ 4 Abs 4 lit b)
    sache = antrag_einbringen(alt, **ANTRAG, ordnung=ordnung)
    client.force_login(jung)
    assert client.post(reverse("verfahren:unterstuetzen", args=[sache.pk])).status_code == 302
    assert vertrauensfrage_unterstuetzen_erlaubt(jung, sache) is True


def test_grenzfall_anwartschaft_erst_am_tag_nach_der_einbringung(client, ordnung, altmandat, settings):  # noqa: F811
    """lit c zählt am Tag der Einbringung — wer die zwölf Monate einen Tag später voll hat, bleibt draußen,
    auch wenn er heute für Personenwahlen stimmberechtigt wäre."""
    settings.DDOE_UEBERGANGSREGEL = False
    gestern = timezone.now() - tage(1)
    stichtag = timezone.localdate(gestern)
    knapp = mitglied_anlegen("knapp")
    knapp.beitritt = monate_addieren(stichtag, -12) + tage(1)
    knapp.save(update_fields=["beitritt"])
    assert knapp.ist_stimmberechtigt(Gegenstand.PERSONENWAHL, timezone.localdate()) is True
    assert knapp.ist_stimmberechtigt(Gegenstand.PERSONENWAHL, stichtag) is False
    antrag = einbringen(mitglied_anlegen("alt", tage=400), altmandat, ordnung, jetzt=gestern)

    assert vertrauensfrage_unterstuetzen_erlaubt(knapp, antrag) is False
    client.force_login(knapp)
    assert client.post(reverse("verfahren:unterstuetzen", args=[antrag.pk])).status_code == 403
    assert Unterstuetzung.objects.filter(antrag=antrag).count() == 0


def test_uebergangsregel_laesst_nur_am_einbringungstag_bestehende_mitglieder_zu(client, ordnung, altmandat, settings):  # noqa: F811
    settings.DDOE_UEBERGANGSREGEL = True
    antrag = einbringen(mitglied_anlegen("alt", tage=400), altmandat, ordnung, jetzt=timezone.now() - tage(2))
    neu = mitglied_anlegen("neu", tage=0)  # beigetreten nach der Einbringung
    client.force_login(neu)
    assert client.post(reverse("verfahren:unterstuetzen", args=[antrag.pk])).status_code == 403
    dabei = mitglied_anlegen("dabei", tage=5)
    client.force_login(dabei)
    assert client.post(reverse("verfahren:unterstuetzen", args=[antrag.pk])).status_code == 302


def test_gast_bekommt_die_anmeldung_und_der_bestaetigungsantrag_keine_unterstuetzung(client, ordnung, altmandat):  # noqa: F811
    antrag, ende = _verloren(ordnung, altmandat)
    ich = altmandat.mitglied
    from verfahren.models import vertrauensfrage_einbringen

    b = vertrauensfrage_einbringen(ich, altmandat, "", [], [], ordnung, jetzt=ende + tage(200), art="bestaetigung")
    antwort = client.post(reverse("verfahren:unterstuetzen", args=[b.pk]))
    assert antwort.status_code == 302 and "/anmelden/" in antwort["Location"]
    client.force_login(mitglied_anlegen("x", tage=400))
    antwort = client.post(reverse("verfahren:unterstuetzen", args=[b.pk]), follow=True)
    assert "Ein Bestätigungsantrag wird nicht unterstützt" in antwort.content.decode()
    assert Unterstuetzung.objects.filter(antrag=b).count() == 0
    seite = _seite(client, b)
    assert "Bestätigungsantrag von" in _kopf(seite) and "Bestätigung (§ 7 Abs 10)" in seite
    assert "Der Antrag gilt als unterstützt; die Abstimmung beginnt am" in seite
    assert "Diesen Antrag unterstützen" not in seite
    regeln = dict(_regeln_lesbar(b.policy(), b.art, b.vertrauensfrage))
    assert regeln["Unterstützungsschwelle"].startswith("keine — der Bestätigungsantrag")
    assert "am 7. Tag nach Einbringung" in regeln["Abstimmungsbeginn"]


# ── Abstimmen (lit e) ──────────────────────────────────────────────────────────────────────


def _zeitraffer_in_die_abstimmung(antrag, unterstuetzer):
    """Eine laufende Vertrauensfrage acht Tage zurückdatieren und mit erreichter Schwelle fortschreiben."""
    unterstuetzen(antrag, unterstuetzer, timezone.now())
    vor_acht_tagen = timezone.now() - tage(8)
    Antrag.objects.filter(pk=antrag.pk).update(eingebracht_am=vor_acht_tagen, phase_beginn=vor_acht_tagen)
    Vertrauensfrage.objects.filter(antrag=antrag).update(schwelle_erreicht_am=timezone.now() - tage(7))
    antrag.refresh_from_db()
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase == "abstimmung"


def _in_abstimmung(ordnung, altmandat, leute):  # noqa: F811
    t0 = timezone.now() - tage(8)
    antrag = einbringen(leute[0], altmandat, ordnung, jetzt=t0)
    unterstuetzen(antrag, leute[1:2], t0 + tage(1))
    antrag.fortschreiben(t0 + tage(7))
    antrag.refresh_from_db()
    assert antrag.phase == "abstimmung"
    return antrag


def test_abstimmen_prueft_das_stimmrecht_fuer_personenwahlen(client, ordnung, altmandat, settings):  # noqa: F811
    settings.DDOE_UEBERGANGSREGEL = False
    alt = [mitglied_anlegen(f"alt{i}", tage=400) for i in range(3)]
    jung = mitglied_anlegen("jung", tage=100)
    antrag = _in_abstimmung(ordnung, altmandat, alt)

    client.force_login(jung)
    antwort = client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "ja"})
    assert antwort.status_code == 403 and antrag.stimmabgaben.count() == 0
    client.force_login(alt[2])
    antwort = client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "nein"})
    assert antwort.status_code == 302 and antrag.stimmabgaben.count() == 1

    # Legende auf der Antragsseite, keine KI-Zone, Chip
    seite = _seite(client, antrag)
    abstimmen_karte = seite.split('id="abstimmen"')[1].split("</div>")[0]
    assert "Ja = Vertrauen versagen · Nein = Vertrauen aussprechen" in abstimmen_karte
    assert 'id="zone-einschaetzung"' not in seite
    assert ">Vertrauensfrage</span>" in _kopf(seite)


# ── Bewerben mit Rückgabezusage (§ 7 Abs 3) ────────────────────────────────────────────────


def test_bewerben_verlangt_die_rueckgabezusage(client, ordnung):  # noqa: F811
    anna, bert = mitglied_anlegen("anna", tage=400), mitglied_anlegen("bert", tage=400)
    kandidatur = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung, art=Antragsart.MANDAT)
    ziel = reverse("verfahren:bewerben", args=[kandidatur.pk])
    client.force_login(anna)
    seite = _seite(client, kandidatur)
    form = seite.split('class="bewerbungsform"')[1].split("</form>")[0]
    assert 'name="rueckgabezusage" value="abgegeben" required' in form
    assert 'name="rueckgabezusage" value="nicht_abgegeben" required' in form
    assert "freiwillig und nicht einklagbar" in form and "öffentlich ausgewiesen" in form

    antwort = client.post(ziel, {"vorstellung": "Ich.", "waehlbar": "1"}, follow=True)
    assert "Bitte erklären Sie, ob Sie die Rückgabezusage abgeben oder nicht abgeben" in antwort.content.decode()
    assert Bewerbung.objects.count() == 0
    antwort = client.post(ziel, {"vorstellung": "Ich.", "waehlbar": "1", "rueckgabezusage": "vielleicht"})
    assert antwort.status_code == 302 and Bewerbung.objects.count() == 0

    client.post(ziel, {"vorstellung": "Ich.", "waehlbar": "1", "rueckgabezusage": "nicht_abgegeben"})
    assert Bewerbung.objects.get(mitglied=anna).rueckgabezusage == "nicht_abgegeben"
    client.force_login(bert)
    client.post(ziel, {"vorstellung": "Er.", "waehlbar": "1", "rueckgabezusage": "abgegeben"})
    assert Bewerbung.objects.get(mitglied=bert).rueckgabezusage == "abgegeben"
    seite = _seite(client, kandidatur)
    assert "Rückgabezusage: nicht abgegeben" in seite and "Rückgabezusage: abgegeben" in seite


def test_nach_verlorener_vertrauensfrage_sagt_die_bewerbung_warum_nicht(client, ordnung, altmandat):  # noqa: F811
    _verloren(ordnung, altmandat)
    kandidatur = antrag_einbringen(mitglied_anlegen("k", tage=400), **ANTRAG, ordnung=ordnung, art=Antragsart.MANDAT)
    client.force_login(altmandat.mitglied)
    antwort = client.post(
        reverse("verfahren:bewerben", args=[kandidatur.pk]),
        {"vorstellung": "Ich.", "waehlbar": "1", "rueckgabezusage": "abgegeben"},
        follow=True,
    )
    assert "§ 7 Abs 10 lit f Z 3" in antwort.content.decode() and Bewerbung.objects.count() == 0


# ── Antragsseite ───────────────────────────────────────────────────────────────────────────


def test_antragsseite_zeigt_kopfzeile_anlaesse_baender_und_stellungnahmen(client, ordnung, altmandat):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}", tage=400) for i in range(4)]  # 5 Stimmberechtigte → Schwelle 1
    Aufgabe.objects.create(mandat=altmandat, titel="Sitzung", frist=timezone.now() - tage(45), sitzungstag=True)
    kennungen = sorted(a["kennung"] for a in altmandat.anlass_ausstaende())
    anlass = abweichung(altmandat, gegenstand="Radweg an der Bundesstraße")
    t0 = timezone.now() - tage(2)
    antrag = einbringen(leute[0], altmandat, ordnung, anlaesse=[anlass], ausstaende=kennungen, jetzt=t0)
    vf = antrag.vertrauensfrage
    Stellungnahme.objects.create(vertrauensfrage=vf, text="Ich habe aus Gewissensgründen anders gestimmt.")

    client.force_login(leute[1])
    seite = _seite(client, antrag)
    assert not any(rest in seite for rest in ("{#", "#}", "{%", "{{", "endcomment", "endblocktranslate"))
    kopf = _kopf(seite)
    assert "Vertrauensfrage zu" in kopf and f'href="/mandatare/{altmandat.pk}/"' in kopf
    assert altmandat.mitglied.anzeigename in kopf and "(Gemeinderätin)" in kopf
    assert f"Anlässe: {1 + len(kennungen)}" in kopf and "0 Unterstützungen" in kopf
    assert ">Vertrauensfrage</span>" in kopf.split('class="a-chips"')[1].split("</div>")[0]
    assert "Stimmberechtigte am Einbringungstag: 5 — Schwelle: 1 Unterstützungen (§ 7 Abs 10 lit c)" in kopf
    assert "Der regionale Weg nach § 7 Abs 10 lit c steht offen" in kopf  # Gemeindemandat, keine Gliederungen
    assert "Schwelle erreicht am" not in kopf and "vf-band-sperre" not in kopf

    # Anlässe: Tabelle aus dem Rechenschaftsregister und Zeilen für die Ausstände
    anlaesse = seite.split('id="anlaesse"')[1].split('id="stellungnahme"')[0]
    assert "Radweg an der Bundesstraße" in anlaesse and "angenommen" in anlaesse and "dagegen" in anlaesse
    assert "Ich sehe das anders." in anlaesse
    assert "<th>Beschluss der Plattform</th><th>Stimme</th><th>Begründung des Mandatars</th>" in anlaesse
    assert anlaesse.count('class="vf-ausstand"') == len(kennungen)
    assert "ausständig seit" in anlaesse and f'href="/mandatare/{altmandat.pk}/rechenschaft/"' in anlaesse

    # Stellungnahme in eigener Karte mit Zeitstempel
    karte = seite.split('id="stellungnahme"')[1].split('<div class="karte handlung">')[0]
    assert "Stellungnahme des Mandatsträgers" in karte
    assert "Ich habe aus Gewissensgründen anders gestimmt." in karte
    assert 'class="kommentar stellungnahme"' in karte and timezone.localdate().strftime("%d.%m.%Y") in karte

    # Schwelle erreicht → Band mit Datum und Abstimmungsbeginn; Rückzug ohne Wirkung auf den Fortgang
    client.post(reverse("verfahren:unterstuetzen", args=[antrag.pk]))
    vf.refresh_from_db()
    assert vf.schwelle_erreicht_am is not None
    seite = _seite(client, antrag)
    kopf = _kopf(seite)
    assert "Schwelle erreicht am" in kopf and "Abstimmung ab" in kopf and "(§ 7 Abs 10 lit e)" in kopf
    assert timezone.localtime(t0 + tage(7)).strftime("%d.%m.%Y") in kopf
    assert "ein Rückzug ändert den Fortgang nicht mehr" in seite
    # Die Frist der Kopfzeile ist jetzt der Abstimmungsbeginn — nicht mehr das Ende der Sammelfrist
    # (Prüfung 0.48: „Frist 13.10.“ neben „Abstimmung ab 20.09.“); Kachel und Zeile rechnen gleich.
    assert "Frist " + timezone.localtime(t0 + tage(7)).strftime("%d.%m.%Y") in kopf
    assert timezone.localtime(t0 + tage(30)).strftime("%d.%m.%Y") not in kopf
    html = client.get(reverse("verfahren:parlament")).content.decode()
    zeile = html.split('id="feld-filter"')[1].split('class="fz')[1].split('class="k-erfasst"')[0]
    assert "Abstimmung ab " + timezone.localtime(t0 + tage(7)).strftime("%d.%m.%Y") in zeile
    assert "noch 4 Tage" in zeile or "noch 5 Tage" in zeile
    assert "noch 27 Tage" not in zeile and "noch 28 Tage" not in zeile


def test_regeln_der_vertrauensfrage_nennen_schwelle_prozent_und_fenster(ordnung, altmandat):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(30)]
    antrag = einbringen(leute[0], altmandat, ordnung)
    regeln = _regeln_lesbar(antrag.policy(), antrag.art, antrag.vertrauensfrage)
    namen = [n for n, _w in regeln]
    assert namen == [
        "Unterstützungsschwelle", "Frist zum Unterstützen", "Beratung", "Abstimmungsbeginn",
        "Abstimmung", "Mindestbeteiligung", "Mehrheit", "Verfahrensordnung",
    ]
    werte = dict(regeln)
    assert werte["Unterstützungsschwelle"].startswith("2 Unterstützungen · fünf Prozent der 31 ")
    assert werte["Frist zum Unterstützen"].startswith("30 Tage · höchstens 30 Tage")
    assert werte["Beratung"] == "keine Beratungsphase (§ 7 Abs 10 lit c)"
    assert werte["Abstimmungsbeginn"] == (
        "frühestens am 7. Tag nach Einbringung, spätestens am 3. Tag nach Erreichen der Schwelle (§ 7 Abs 10 lit e)"
    )
    assert werte["Abstimmung"].startswith("7 Tage · mindestens sieben Tage")
    assert "Sperre für Wiedereinbringung" not in werte


def test_sperrhinweis_band_in_pruefung_abgelaufen_und_festgestellt(client, ordnung):  # noqa: F811
    leute = rat(3)
    frisch = Mandat.objects.create(mitglied=mitglied_anlegen("neu"), bezeichnung="Gemeinderat", ebene="gemeinde")
    antrag = einbringen(mitglied_anlegen("anna"), frisch, ordnung)
    kopf = _kopf(_seite(client, antrag))
    assert "Der Integritätsrat prüft eine Sperre nach § 7 Abs 10 lit g bis" in kopf
    assert "Schonfrist" in kopf and "bekämpfbar" in kopf

    Antrag.objects.filter(pk=antrag.pk).update(eingebracht_am=timezone.now() - tage(4))
    antrag.refresh_from_db()
    kopf = _kopf(_seite(client, antrag))
    assert "Sperrhinweis ohne Feststellung" in kopf and "gilt als eröffnet" in kopf

    Antrag.objects.filter(pk=antrag.pk).update(eingebracht_am=timezone.now())
    antrag.refresh_from_db()
    beschluss = _feststellung(antrag, leute, timezone.now())
    seite = _seite(client, antrag)
    kopf = _kopf(seite)
    assert f"Nicht eröffnet: Der Integritätsrat hat mit Beschluss {beschluss.nummer}" in kopf
    assert "binnen sieben Tagen beim Parteischiedsgericht bekämpfbar — bis" in kopf
    assert timezone.localtime(antrag.phase_beginn + tage(7)).strftime("%d.%m.%Y") in kopf
    assert "Nicht eröffnet (§ 7 Abs 10 lit b):" in kopf and "Formal zurückgewiesen" not in kopf
    # Nach Ablauf der sieben Tage sagt das Band nicht mehr „ist bekämpfbar“ (lit h)
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - tage(8))
    kopf = _kopf(_seite(client, antrag))
    assert f"Beschluss {beschluss.nummer}" in kopf and "bekämpfbar" not in kopf


def test_ergebnis_heisst_verloren_oder_gewonnen(client, ordnung, altmandat):  # noqa: F811
    antrag, ende = _verloren(ordnung, altmandat)
    seite = _seite(client, antrag)
    assert antrag.phase == "angenommen"
    ergebnis = seite.split("<h3>Ergebnis</h3>")[1].split("</div>")[0]
    assert "<strong>Vertrauensfrage verloren</strong>" in ergebnis and "Auszählung:" in ergebnis
    assert "Ja = Vertrauen versagen" in ergebnis
    kopf = _kopf(seite)
    assert "Vertrauensfrage verloren" in kopf and "bekämpfbar beim Parteischiedsgericht" in kopf
    assert "öffentlich ersucht, das Mandat bis" in kopf
    # lit f Z 4: dieselbe Frist wie das Register (Wiener Kalendertag + 30)
    assert (timezone.localdate(antrag.vertrauensfrage.wirkungen_ab) + tage(30)).strftime("%d.%m.%Y") in kopf
    # Der Phasen-Badge sagt „Vertrauensfrage verloren“, nicht „angenommen“ (V5) — auf Seite, Kachel und Zeile
    assert '<span class="badge b-angenommen">Vertrauensfrage verloren</span>' in kopf
    html = client.get(reverse("verfahren:parlament")).content.decode()
    abgeschlossen = html.split('id="feld-filter"')[1]
    assert '<span class="badge b-angenommen">Vertrauensfrage verloren</span>' in abgeschlossen
    assert '<span class="badge b-angenommen">angenommen</span>' not in abgeschlossen
    vertrauensfrage_anfechtung_vermerken(antrag.vertrauensfrage, "PSG 1/26")
    kopf = _kopf(_seite(client, antrag))
    assert "Rechtsschutz: beim Parteischiedsgericht anhängig" in kopf

    # verfehlte Beteiligung = gewonnen
    leute = [mitglied_anlegen(f"g{i}", tage=400) for i in range(40)]
    mandat = Mandat.objects.create(mitglied=leute[0], bezeichnung="Landtag", ebene="land", gebiet="Oberösterreich")
    t0 = timezone.now()
    zweiter = einbringen(leute[1], mandat, ordnung, anlaesse=[abweichung(mandat)], jetzt=t0)
    unterstuetzen(zweiter, leute[2:5], t0 + tage(1))
    zweiter.fortschreiben(t0 + tage(7))
    abstimmen(zweiter, leute[2:3], "ja", t0 + tage(8))  # 1 von 46: unter der Mindestbeteiligung
    zweiter.fortschreiben(t0 + tage(14))
    zweiter.refresh_from_db()
    assert zweiter.phase == "abgelehnt"
    seite = _seite(client, zweiter)
    assert "<strong>Vertrauensfrage gewonnen</strong>" in seite and "Mindestbeteiligung verfehlt" in seite


# ── Kachel, Feed-Zeile, Übersicht ──────────────────────────────────────────────────────────


def test_kachel_und_feedzeile_tragen_chip_legende_und_unterstuetzungsrecht(client, ordnung, mandat_daheim, settings):  # noqa: F811
    settings.DDOE_UEBERGANGSREGEL = False
    alt = [mitglied_anlegen(f"alt{i}", tage=400) for i in range(3)]
    jung = mitglied_anlegen("jung", tage=100)
    antrag = einbringen(alt[0], mandat_daheim, ordnung)

    client.force_login(jung)
    html = client.get(reverse("verfahren:parlament")).content.decode()
    feld = html.split('id="feld-filter"')[1].split("</section>")[0]
    zeile = feld.split('class="fz')[1].split('class="k-erfasst"')[0]
    assert '<span class="chip klein">Vertrauensfrage</span>' in zeile
    assert "Unterstützen nur mit Stimmrecht für Personenwahlen" in zeile
    assert f'action="/antrag/{antrag.pk}/unterstuetzen/"' not in zeile
    region = html.split('id="feld-region"')[1].split("</section>")[0]
    assert antrag.titel in region  # Region wie jeder andere Antrag: Ebene und Gebiet vom Mandat
    wichtig = html.split('id="feld-wichtig"')[1].split("</section>")[0] if 'id="feld-wichtig"' in html else ""
    assert antrag.titel not in wichtig  # nie von selbst in Feld D

    client.force_login(alt[1])
    html = client.get(reverse("verfahren:parlament")).content.decode()
    zeile = html.split('id="feld-filter"')[1].split('class="fz')[1].split('class="k-erfasst"')[0]
    assert f'action="/antrag/{antrag.pk}/unterstuetzen/"' in zeile

    _zeitraffer_in_die_abstimmung(antrag, alt[1:2])
    html = client.get(reverse("verfahren:parlament")).content.decode()
    zeile = html.split('id="feld-filter"')[1].split('class="fz')[1].split('class="k-erfasst"')[0]
    assert f'action="/antrag/{antrag.pk}/abstimmen/"' in zeile and 'name="stimme" value="nein"' in zeile
    assert "Ja = Vertrauen versagen · Nein = Vertrauen aussprechen" in zeile
    region = html.split('id="feld-region"')[1].split("</section>")[0]
    kachel = region.split('<article class="kachel"')[1].split("</article>")[0]
    assert '<span class="badge badge--hell">Vertrauensfrage</span>' in kachel
    assert "Ja = Vertrauen versagen · Nein = Vertrauen aussprechen" in kachel
    assert "Personenwahl" not in kachel and "Zur Wahl" not in kachel
    antwort = client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "nein", "weiter": "/parlament/"})
    assert antwort.status_code == 302 and antrag.stimmabgaben.count() == 1


def test_uebersicht_kennzeichnet_die_vertrauensfrage_und_nennt_das_ergebnis(client, ordnung, altmandat):  # noqa: F811
    alt = [mitglied_anlegen(f"alt{i}", tage=400) for i in range(3)]
    antrag = _in_abstimmung(ordnung, altmandat, alt)
    antwort = client.get(reverse("uebersicht:index"))
    inhalt = antwort.content.decode()
    karte = inhalt.split(antrag.titel)[1].split("</div>")[0]
    assert '<span class="badge badge--hell">Vertrauensfrage</span>' in karte
    assert "Ja = Vertrauen versagen · Nein = Vertrauen aussprechen" in karte
    assert "Tendenz verdeckt bis Fristende" in inhalt

    stimme_abgeben(antrag, alt[2], "nein")
    stimme_abgeben(antrag, alt[1], "nein")
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - tage(8))
    antrag.refresh_from_db()
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase == "abgelehnt"
    antwort = client.get(reverse("uebersicht:index"))
    inhalt = antwort.content.decode()
    zeile = next(z for z in antwort.context["abstimmungen"] if z["antrag"].pk == antrag.pk)
    assert zeile["ergebnis_wort"] == "Vertrauensfrage gewonnen" and zeile["personenwahl"] is False
    assert zeile["nein"] == 2 and zeile["ja"] == 0
    karte = inhalt.split(antrag.titel)[1].split("</p>")[0]
    assert ">Vertrauensfrage gewonnen</span>" in karte and ">abgelehnt</span>" not in karte


def test_aufhebung_steht_an_denselben_stellen_wie_das_ergebnis(client, ordnung, altmandat):  # noqa: F811
    """§ 7 Abs 10 lit h letzter Satz: Die Aufhebung wird an denselben Stellen veröffentlicht wie das
    Ergebnis — Feed-Zeile (Gruppe „Abgeschlossen“) und Übersicht tragen den Rechtsschutzstand als eigenes
    Badge neben „Vertrauensfrage verloren“ (Prüfung 0.48, B13); `ergebnis_wort` bleibt unverändert."""
    from mandatare.models import vertrauensfrage_entscheidung_vermerken

    antrag, ende = _verloren(ordnung, altmandat)
    vf = antrag.vertrauensfrage

    def badges():
        feed = client.get(reverse("verfahren:parlament")).content.decode().split('id="feld-filter"')[1]
        zeile = feed.split(antrag.titel)[1].split('class="zs')[0]
        uebersicht = client.get(reverse("uebersicht:index")).content.decode()
        karte = uebersicht.split(antrag.titel)[1].split("</p>")[0]
        return zeile, karte

    zeile, karte = badges()
    assert "Vertrauensfrage verloren" in zeile and "Vertrauensfrage verloren" in karte
    assert "Parteischiedsgericht" not in zeile and "Parteischiedsgericht" not in karte

    vertrauensfrage_anfechtung_vermerken(vf, "PSG 1/26", jetzt=ende + tage(2))
    zeile, karte = badges()
    assert '<span class="badge badge--hell">beim Parteischiedsgericht anhängig</span>' in zeile
    assert '<span class="badge badge--hell">beim Parteischiedsgericht anhängig</span>' in karte

    vertrauensfrage_entscheidung_vermerken(vf, "aufgehoben", jetzt=ende + tage(10))
    vf.refresh_from_db()
    assert vf.ergebnis_wort == "Vertrauensfrage verloren"  # das Ergebnis bleibt, die Aufhebung tritt daneben
    zeile, karte = badges()
    assert '<span class="badge badge--hell">vom Parteischiedsgericht aufgehoben</span>' in zeile
    assert '<span class="badge badge--hell">vom Parteischiedsgericht aufgehoben</span>' in karte
    assert zeile.count("Vertrauensfrage verloren") == 1 and karte.count("Vertrauensfrage verloren") == 1


def test_bestaetigungsantrag_zeigt_die_wartezeit_statt_einer_unterstuetzungsphase(client, ordnung, mandat_daheim):  # noqa: F811
    """§ 7 Abs 10 lit f Z 3: lit c gilt nicht — der Bestätigungsantrag sammelt keine Unterstützung. Badge auf
    Antragsseite, Kachel und Zeile sagen „Wartezeit bis zur Abstimmung“, im Parlament steht er in einer eigenen
    Gruppe statt unter „Sammeln Unterstützung“, die Archiv-Zeitleiste kennt keinen Unterstützungsblock
    (Prüfung 0.48, B34 / E9)."""
    from verfahren.models import vertrauensfrage_einbringen

    antrag, ende = _verloren(ordnung, mandat_daheim)
    ich = mandat_daheim.mitglied
    b = vertrauensfrage_einbringen(ich, mandat_daheim, "", [], [], ordnung, jetzt=ende + tage(200), art="bestaetigung")
    assert b.phase == "unterstuetzung"

    client.force_login(ich)
    kopf = _kopf(_seite(client, b))
    chips = kopf.split('class="a-chips"')[1].split("</div>")[0]
    assert '<span class="badge b-unterstuetzung">Wartezeit bis zur Abstimmung</span>' in chips
    assert ">Unterstützung</span>" not in chips
    assert "ohne Unterstützungs- und Beratungsphase" in kopf  # das Band und das Badge widersprechen sich nicht mehr

    html = client.get(reverse("verfahren:parlament")).content.decode()
    feld = html.split('id="feld-filter"')[1].split("</section>")[0]
    gruppen = [g.split("<")[0] for g in feld.split('<p class="gruppe">')[1:]]
    assert "Wartezeit bis zur Abstimmung" in gruppen and "Sammeln Unterstützung" not in gruppen
    assert gruppen.index("Wartezeit bis zur Abstimmung") < gruppen.index("Abgeschlossen")
    zeile = feld.split(b.titel)[1].split('class="za"')[0]
    assert '<span class="badge b-unterstuetzung">Wartezeit bis zur Abstimmung</span>' in zeile
    assert ">Unterstützung</span>" not in zeile and "Unterstützen" not in zeile
    region = html.split('id="feld-region"')[1].split("</section>")[0]
    kachel = region.split(b.titel)[0].rsplit('<article class="kachel"', 1)[1] + region.split(b.titel)[1].split("</article>")[0]
    assert '<span class="badge">Wartezeit bis zur Abstimmung</span>' in kachel
    assert '<span class="badge">Unterstützung</span>' not in kachel

    # Archiv: kein Block „Unterstützungsphase“ — solange er wartet, heißt der Block ehrlich
    bloecke = archivkern.zeitleiste(b)
    assert [(x["phase"], x["name"]) for x in bloecke] == [("unterstuetzung", "Wartezeit bis zur Abstimmung")]
    vor_acht_tagen = timezone.now() - tage(8)
    Antrag.objects.filter(pk=b.pk).update(eingebracht_am=vor_acht_tagen, phase_beginn=vor_acht_tagen)
    Vertrauensfrage.objects.filter(antrag=b).update(schwelle_erreicht_am=vor_acht_tagen)
    b.refresh_from_db()
    b.fortschreiben()
    b.refresh_from_db()
    assert b.phase == "abstimmung"
    assert [x["phase"] for x in archivkern.zeitleiste(b)] == ["abstimmung"]
    assert "Unterstützungsphase" not in archivkern.als_markdown(b)
    # Die gewöhnliche Vertrauensfrage behält ihren Unterstützungsblock
    assert [x["name"] for x in archivkern.zeitleiste(antrag)][0] == "Unterstützungsphase"


# ── Archiv und Export ──────────────────────────────────────────────────────────────────────


def test_archiv_ohne_beratungsblock_und_mit_der_art(client, ordnung, altmandat):  # noqa: F811
    alt = [mitglied_anlegen(f"alt{i}", tage=400) for i in range(3)]
    antrag = einbringen(alt[0], altmandat, ordnung)
    assert [b["phase"] for b in archivkern.zeitleiste(antrag)] == ["unterstuetzung"]
    Stellungnahme.objects.create(vertrauensfrage=antrag.vertrauensfrage, text="Meine Sicht.")

    _zeitraffer_in_die_abstimmung(antrag, alt[1:2])
    phasen = [b["phase"] for b in archivkern.zeitleiste(antrag)]
    assert phasen == ["unterstuetzung", "abstimmung"], phasen

    daten = json.loads(archivkern.als_json(antrag))
    assert daten["antrag"]["art"] == "Vertrauensfrage"
    vf = daten["vertrauensfrage"]
    assert vf["art"] == "Vertrauensfrage" and vf["mandat"] == "Gemeinderätin"
    assert vf["mandatar"] == altmandat.mitglied.anzeigename
    assert vf["stimmberechtigte_am_einbringungstag"] == 4 and vf["schwelle"] == 1
    assert vf["anlaesse"][0]["gegenstand"] == "Radweg" and vf["anlaesse"][0]["stimme"] == "dagegen"
    assert vf["stellungnahmen"][0]["text"] == "Meine Sicht." and vf["ergebnis"] == ""
    assert "beratung" not in [b["phase"] for b in daten["zeitleiste"]]

    text = archivkern.als_markdown(antrag)
    assert " · Vertrauensfrage · " in text and "ohne Beratungsphase (§ 7 Abs 10 lit c)" in text
    assert "Mandatar: " + altmandat.mitglied.anzeigename in text
    assert "## Stellungnahme des Mandatsträgers" in text and "Meine Sicht." in text
    assert "## Beratung" not in text

    antwort = client.get(reverse("verfahren:archiv_export", args=[antrag.pk, "json"]))
    assert antwort.status_code == 200 and json.loads(antwort.content)["vertrauensfrage"]["schwelle"] == 1


def test_export_nennt_die_art_und_nachrechnen_liefert_verloren(client, ordnung, altmandat):  # noqa: F811
    from verfahren.test_views_aktionen import _nachrechnen_laden

    antrag, _ende = _verloren(ordnung, altmandat)
    client.force_login(altmandat.mitglied)
    daten = json.loads(client.get(reverse("verfahren:export", args=[antrag.pk])).content)
    assert daten["art"] == "vertrauensfrage" and daten["vertrauensfrage"]["ergebnis"] == "Vertrauensfrage verloren"
    ergebnis = _nachrechnen_laden()(daten)
    assert ergebnis["vertrauensfrage"] == "verloren" and ergebnis["angenommen"] is True


# ── Abfragezahl ────────────────────────────────────────────────────────────────────────────


def test_parlament_und_uebersicht_bleiben_bei_vielen_vertrauensfragen_bei_konstanter_abfragezahl(client, ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f"q{i}", tage=400) for i in range(6)]

    def vertrauensfragen(von, bis, in_abstimmung):
        """Je Mandat eine Vertrauensfrage — die eine Hälfte sammelt, die andere stimmt schon ab."""
        for i in range(von, bis):
            mandat = Mandat.objects.create(
                mitglied=leute[i], bezeichnung=f"Gemeinderat {i}", ebene="gemeinde", gebiet=GEMEINDE
            )
            antrag = einbringen(leute[5], mandat, ordnung, anlaesse=[abweichung(mandat)])
            if in_abstimmung:
                _zeitraffer_in_die_abstimmung(antrag, [leute[(i + 1) % 5]])

    def messen():
        with CaptureQueriesContext(connection) as parlament:
            assert client.get(reverse("verfahren:parlament")).status_code == 200
        with CaptureQueriesContext(connection) as uebersicht:
            assert client.get(reverse("uebersicht:index")).status_code == 200
        return len(parlament), len(uebersicht)

    client.force_login(leute[5])
    vertrauensfragen(0, 1, in_abstimmung=False)
    vertrauensfragen(1, 2, in_abstimmung=True)
    klein = messen()
    vertrauensfragen(2, 4, in_abstimmung=False)
    vertrauensfragen(4, 5, in_abstimmung=True)
    gross = messen()
    assert gross == klein, (klein, gross)
