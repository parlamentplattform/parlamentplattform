"""Die Vertrauensfrage (§ 7 Abs 10, S10c) — Fachoperation und Verlauf.

`vertrauensfrage_einbringen`: Ordnung aus Satzungswerten und Register eingefroren (§ 5 Abs 5), Zahlen am
Einbringungstag, Anlass als Formerfordernis, Sperren als Hinweis statt Abweisung; Unterstützung bis zur
Schwelle, Abstimmung frühestens am siebten Tag, „angenommen“ heißt verloren — mit den Wirkungen in zwei
Stufen; gewonnen lässt alles, wie es ist; Bestätigungsantrag nach lit f Z 3; Feststellung des
Integritätsrats nach lit b; Nachrechnen wie eine Sachfrage."""

import itertools
from datetime import date, timedelta

import pytest
from django.core import mail
from django.utils import timezone

from gremien.models import (
    Anlass,
    BeschlussStatus,
    GremienBeschluss,
    Gremium,
    Hinweis,
    Rolle,
    wirkung_anwenden,
)
from gremien.test_integritaet import rat
from gremien.test_werkstatt import rolle_geben
from mandatare import models as mm
from mandatare.models import (
    Aufgabe,
    Beschluss,
    Mandat,
    Rechenschaft,
    Stimmverhalten,
    Vertrauensfrage,
    VertrauensfrageFehler,
    vertrauensfrage_anfechtung_vermerken,
    vertrauensfrage_entscheidung_vermerken,
    vertrauensfragen_fortschreiben,
)
from parameter.models import Parameter
from plattform_core import Gegenstand, Phase
from verfahren.models import (
    Antrag,
    Antragsart,
    AuditEintrag,
    Bewerbung,
    BewerbungsFehler,
    Rueckgabezusage,
    antrag_einbringen,
    bewerbung_einreichen,
    gegenstand_fuer,
    stimme_abgeben,
    vertrauensfrage_einbringen,
)
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    _nachrechnen_laden,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db

_N = itertools.count(1)


def tage(n):
    return timedelta(days=n)


def audit(typ):
    return [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis.get("typ") == typ]


@pytest.fixture
def altmandat(monkeypatch):
    """Ein Mandat außerhalb der Schonfrist: Absatz 10 gilt hier seit 2025, das Mandat besteht seit 2025."""
    monkeypatch.setattr(mm, "INKRAFTTRETEN_ABS_10", date(2025, 1, 1))
    mandatar = mitglied_anlegen(f"mandatar{next(_N)}", tage=600)
    return Mandat.objects.create(
        mitglied=mandatar, bezeichnung="Gemeinderätin", ebene="gemeinde", gebiet="Polsenz", angetreten=date(2025, 1, 1)
    )


def abweichung(mandat, tag=None, gegenstand="Radweg", **extra):
    """Ein Eintrag des Rechenschaftsregisters, in dem die Stimme vom Beschluss abweicht."""
    return Rechenschaft.objects.create(
        mandat=mandat,
        gegenstand=gegenstand,
        sitzung_am=tag or timezone.localdate() - tage(10),
        beschluss_plattform=Beschluss.ANGENOMMEN,
        stimme=Stimmverhalten.DAGEGEN,
        begruendung="Ich sehe das anders.",
        **extra,
    )


def einbringen(mitglied, mandat, ordnung, anlaesse=None, ausstaende=(), jetzt=None, **extra):  # noqa: F811
    if anlaesse is None:
        anlaesse = [abweichung(mandat)]
    return vertrauensfrage_einbringen(
        mitglied, mandat, "Die Abweichung wurde nicht erklärt.", anlaesse, ausstaende, ordnung, jetzt=jetzt, **extra
    )


def unterstuetzen(antrag, leute, jetzt):
    for m in leute:
        antrag.unterstuetzungen.create(mitglied=m, erklaert_am=jetzt)
    antrag.fortschreiben(jetzt)


def abstimmen(antrag, leute, stimme, jetzt):
    for m in leute:
        stimme_abgeben(antrag, m, stimme, jetzt=jetzt)


# ── Einbringen ─────────────────────────────────────────────────────────────────────────────


def test_einbringen_friert_die_satzungswerte_und_die_zahlen_des_tages_ein(ordnung, altmandat):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(30)]  # 31 Stimmberechtigte mit dem Mandatar
    Parameter.objects.create(schluessel="vertrauensfrage-unterstuetzung-tage", wert="45", beschreibung="x", quelle="T")
    Parameter.objects.create(schluessel="vertrauensfrage-abstimmung-tage", wert="3", beschreibung="x", quelle="T")
    jetzt = timezone.now()

    antrag = einbringen(leute[0], altmandat, ordnung, jetzt=jetzt)

    assert antrag.art == Antragsart.VERTRAUENSFRAGE and antrag.phase == "unterstuetzung"
    assert antrag.titel == "Vertrauensfrage: Gemeinderätin, Polsenz"
    assert antrag.ebene == "gemeinde" and antrag.gebiet == "Polsenz"
    p = antrag.policy()
    assert p.beratung_entfaellt and p.abstimmung_fruehestens_tage == 7 and p.abstimmung_spaetestens_tage_nach_schwelle == 3
    assert p.unterstuetzung_frist_tage == 30  # Register 45, Satzung deckelt auf 30
    assert p.abstimmung_tage == 7  # Register 3, Satzung verlangt 7
    assert p.unterstuetzung_schwelle == 2  # ceil(0.05 * 31)
    vf = antrag.vertrauensfrage
    assert vf.stimmberechtigte_partei_am_einbringungstag == 31 and vf.schwelle_partei == 2
    assert vf.sperrhinweis == "" and vf.schwelle_erreicht_am is None
    assert list(vf.anlaesse.all()) and vf.anlass_ausstaende == []
    fassung = antrag.aktueller_text()
    assert "Versagung des Vertrauens" in fassung.wortlaut and "Radweg" in fassung.wortlaut
    assert "31" in fassung.begruendung and "Unterstützungsschwelle: 2" in fassung.begruendung
    eintrag = audit("vertrauensfrage_eingebracht")[0]
    assert eintrag["mandat"] == altmandat.pk and eintrag["schwelle"] == 2 and eintrag["sperrhinweis"] is False
    assert eintrag["anlaesse"] == [vf.anlaesse.first().pk]
    assert gegenstand_fuer(antrag) is Gegenstand.PERSONENWAHL


def test_der_mandatar_wird_genau_einmal_verstaendigt_ohne_inhalt(ordnung, altmandat, settings):  # noqa: F811
    settings.DDOE_BASIS_URL = "https://parlament.ddoe.at"
    antrag = einbringen(mitglied_anlegen("anna"), altmandat, ordnung)
    assert len(mail.outbox) == 1
    brief = mail.outbox[0]
    assert brief.to == [altmandat.mitglied.email]
    assert f"/antrag/{antrag.pk}/" in brief.body and "Gemeinderätin, Polsenz" in brief.body
    assert "Radweg" not in brief.body and "Die Abweichung wurde nicht erklärt" not in brief.body
    vf = antrag.vertrauensfrage
    assert vf.verstaendigt_am is not None
    from mitglieder.post import vertrauensfrage_senden

    assert vertrauensfrage_senden(altmandat, antrag) is False  # einmal je Antrag
    assert len(mail.outbox) == 1
    post = [e for e in audit("post") if e["art"] == "vertrauensfrage"]
    assert len(post) == 1 and post[0]["mitglied"] == altmandat.mitglied.pk


def test_ohne_anlass_gibt_es_keinen_antrag(ordnung, altmandat):  # noqa: F811
    anna = mitglied_anlegen("anna")
    with pytest.raises(VertrauensfrageFehler, match="mindestens einen Anlass"):
        einbringen(anna, altmandat, ordnung, anlaesse=[])
    treu = Rechenschaft.objects.create(
        mandat=altmandat, gegenstand="Budget", sitzung_am=timezone.localdate(),
        beschluss_plattform=Beschluss.ANGENOMMEN, stimme=Stimmverhalten.DAFUER, begruendung="Wie beschlossen.",
    )
    with pytest.raises(VertrauensfrageFehler, match="abweicht"):
        einbringen(anna, altmandat, ordnung, anlaesse=[treu])
    fremd = Mandat.objects.create(mitglied=mitglied_anlegen("fremd"), bezeichnung="Landtag", ebene="land", gebiet="OÖ")
    with pytest.raises(VertrauensfrageFehler, match="nicht zu diesem Mandat"):
        einbringen(anna, altmandat, ordnung, anlaesse=[abweichung(fremd)])
    with pytest.raises(VertrauensfrageFehler, match="Begründung"):
        vertrauensfrage_einbringen(anna, altmandat, "   ", [abweichung(altmandat)], (), ordnung)
    assert Antrag.objects.count() == 0


def test_ein_ausstand_ueber_30_tage_ist_ein_anlass(ordnung, altmandat):  # noqa: F811
    Aufgabe.objects.create(
        mandat=altmandat, titel="Sitzung", frist=timezone.now() - tage(45), sitzungstag=True
    )
    ausstaende = altmandat.anlass_ausstaende()
    kennungen = {a["kennung"] for a in ausstaende}
    assert any(k.startswith("rechenschaft:") for k in kennungen)
    assert any(k.startswith("sammelbericht:") for k in kennungen)
    assert all(a["tage"] > 30 for a in ausstaende)
    anna = mitglied_anlegen("anna")
    with pytest.raises(VertrauensfrageFehler, match="Ausstand"):
        einbringen(anna, altmandat, ordnung, anlaesse=[], ausstaende=["rechenschaft:999"])
    antrag = einbringen(anna, altmandat, ordnung, anlaesse=[], ausstaende=sorted(kennungen))
    vf = antrag.vertrauensfrage
    assert len(vf.anlass_ausstaende) == len(kennungen)
    assert all(isinstance(a["seit"], str) for a in vf.anlass_ausstaende)
    assert "ausständig seit" in antrag.aktueller_text().wortlaut
    assert audit("vertrauensfrage_eingebracht")[0]["ausstaende"] == len(kennungen)


def test_eine_sperre_wird_als_hinweis_eroeffnet_nicht_abgewiesen(ordnung):  # noqa: F811
    """lit b und g: Die Software weist nicht ab — sie schreibt den Hinweis, der Integritätsrat stellt fest."""
    frisch = Mandat.objects.create(
        mitglied=mitglied_anlegen("neu"), bezeichnung="Gemeinderat", ebene="gemeinde", angetreten=date(2026, 1, 1)
    )
    antrag = einbringen(mitglied_anlegen("anna"), frisch, ordnung)
    vf = antrag.vertrauensfrage
    assert antrag.phase == "unterstuetzung"
    assert "Schonfrist" in vf.sperrhinweis and "lit j" in vf.sperrhinweis  # Altmandat: ab Inkrafttreten
    assert audit("vertrauensfrage_eingebracht")[0]["sperrhinweis"] is True
    assert list(Vertrauensfrage.offene_mit_sperrhinweis()) == [vf]
    assert vf.sperrfrist_ende == antrag.eingebracht_am + tage(3)


# ── Verlauf: Unterstützung, Abstimmung, Ergebnis ───────────────────────────────────────────


def test_schwelle_wird_veroeffentlicht_und_die_abstimmung_beginnt_am_siebten_tag(ordnung, altmandat):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(4)]  # 5 Stimmberechtigte → Schwelle 1
    t0 = timezone.now()
    antrag = einbringen(leute[0], altmandat, ordnung, jetzt=t0)
    assert antrag.policy().unterstuetzung_schwelle == 1
    unterstuetzen(antrag, [leute[1]], t0 + tage(2))
    antrag.refresh_from_db()
    vf = antrag.vertrauensfrage
    assert antrag.phase == "unterstuetzung"  # Tag 2: Schwelle steht, aber frühestens Tag 7
    assert vf.schwelle_erreicht_am == t0 + tage(2)
    assert audit("schwelle_erreicht")[0]["unterstuetzungen"] == 1
    assert antrag.fortschreiben(t0 + tage(6)) is False
    assert antrag.fortschreiben(t0 + tage(9)) is True
    antrag.refresh_from_db()
    assert antrag.phase == "abstimmung" and antrag.phase_beginn == t0 + tage(7)
    assert antrag.stimmberechtigung_stichtag == timezone.localdate(t0 + tage(7))
    assert antrag.stimmberechtigte_anzahl == 5
    wechsel = audit("phasenwechsel")[-1]
    assert wechsel["neue_phase"] == "abstimmung" and "§ 7 Abs 10" in wechsel["grund"]
    assert audit("schwelle_erreicht").__len__() == 1  # nicht noch einmal


def test_ein_rueckzug_nach_der_veroeffentlichten_schwelle_laesst_den_antrag_nicht_verfallen(ordnung, altmandat):  # noqa: F811
    """lit c: Das Erreichen ist veröffentlicht, lit h: ab da läuft die Anfechtungsfrist — ein späterer
    Rückzug (Grundregel 7: gestempelt, nicht gelöscht) nimmt dem Antrag die Abstimmung nicht."""
    leute = [mitglied_anlegen(f"m{i}") for i in range(4)]  # Schwelle 1
    t0 = timezone.now()
    antrag = einbringen(leute[0], altmandat, ordnung, jetzt=t0)
    unterstuetzen(antrag, [leute[1]], t0 + tage(2))
    eintrag = antrag.unterstuetzungen.get(mitglied=leute[1])
    eintrag.zurueckgezogen_am = t0 + tage(3)
    eintrag.save(update_fields=["zurueckgezogen_am"])
    assert antrag.fortschreiben(t0 + tage(7)) is True
    antrag.refresh_from_db()
    assert antrag.phase == "abstimmung" and antrag.phase_beginn == t0 + tage(7)


def test_zaehler_und_nenner_rechnen_beide_mit_der_personenwahl(ordnung, altmandat, settings):  # noqa: F811
    settings.DDOE_UEBERGANGSREGEL = False
    alt = [mitglied_anlegen(f"alt{i}", tage=400) for i in range(3)]
    mitglied_anlegen("jung", tage=100)  # nur für Sachfragen stimmberechtigt
    t0 = timezone.now()
    antrag = einbringen(alt[0], altmandat, ordnung, jetzt=t0)
    vf = antrag.vertrauensfrage
    assert vf.stimmberechtigte_partei_am_einbringungstag == 4  # drei plus der Mandatar (600 Tage)
    unterstuetzen(antrag, alt[1:2], t0 + tage(1))
    antrag.fortschreiben(t0 + tage(7))
    antrag.refresh_from_db()
    assert antrag.phase == "abstimmung" and antrag.stimmberechtigte_anzahl == 4


def test_verloren_loest_die_wirkungen_in_zwei_stufen_aus(ordnung, altmandat):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(5)]
    rat(3)
    rolle = rolle_geben(altmandat.mitglied, Gremium.KOORDINATIONSRAT)
    kandidatur = antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung, art=Antragsart.MANDAT)
    t0 = timezone.now()
    antrag = einbringen(leute[0], altmandat, ordnung, jetzt=t0)
    unterstuetzen(antrag, leute[1:2], t0 + tage(1))
    antrag.fortschreiben(t0 + tage(7))
    abstimmen(antrag, leute, "ja", t0 + tage(8))
    ende = t0 + tage(14)
    assert antrag.fortschreiben(ende) is True
    antrag.refresh_from_db()
    altmandat.refresh_from_db()
    vf = antrag.vertrauensfrage
    rolle.refresh_from_db()

    # Stufe 1 — mit der Veröffentlichung des Ergebnisses (lit f Z 3, 4, 7)
    assert antrag.phase == "angenommen" and vf.verloren and vf.ergebnis_wort == "Vertrauensfrage verloren"
    assert vf.wirkungen_ab == ende and vf.ergebnis_am == ende
    assert altmandat.vertrauen_entzogen_am == ende
    assert altmandat.rueckgabe_ersucht_bis == timezone.localdate(ende) + tage(30)
    assert altmandat.beendet is None and altmandat.aktiv  # nichts setzt das Mandatsende
    assert altmandat.kandidatursperre
    assert rolle.ruht_seit == ende and rolle.ruht and not rolle.aktiv
    assert not Rolle.hat(altmandat.mitglied, Gremium.KOORDINATIONSRAT)
    assert Rolle.letzte(altmandat.mitglied, Gremium.KOORDINATIONSRAT) == rolle  # lesen bleibt
    hinweis = Hinweis.objects.get(quelle="vertrauensfrage")
    assert hinweis.antrag == antrag and "Parlamentsklub" in hinweis.text and "Abführungspflicht" in hinweis.text
    verloren = audit("vertrauensfrage_verloren")[0]
    assert verloren["mandat"] == altmandat.pk and verloren["rollen_ruhen"] == [rolle.pk]
    with pytest.raises(BewerbungsFehler, match="§ 7 Abs 10 lit f Z 3"):
        bewerbung_einreichen(kandidatur, altmandat.mitglied, "Ich trete an.", "abgegeben")
    assert altmandat.rueckgabe_vermerk == ""  # die Frist läuft

    # Stufe 2a — sieben Tage später ohne Anfechtung: Ruhen wird zum Ende
    assert vertrauensfragen_fortschreiben(ende + tage(6)) == 0
    assert vertrauensfragen_fortschreiben(ende + tage(7)) == 1
    vf.refresh_from_db()
    rolle.refresh_from_db()
    altmandat.refresh_from_db()
    assert vf.wirkungen_endgueltig_am == ende + tage(7)
    assert rolle.beendet_grund == "Vertrauensfrage (§ 7 Abs 10 lit f)"
    assert altmandat.vertretung_beendet_am is None and altmandat.mitglied.ist_mandatar
    assert vertrauensfragen_fortschreiben(ende + tage(8)) == 0  # idempotent

    # Stufe 2b — 30 Tage nach der Veröffentlichung: Vertretung endet, Mandat bleibt
    assert vertrauensfragen_fortschreiben(ende + tage(30)) == 1
    altmandat.refresh_from_db()
    assert altmandat.vertretung_beendet_am == timezone.localdate(ende + tage(30))
    assert altmandat.mandatsvereinbarung_endet_am is None  # kein lit h vermerkt (lit j)
    assert altmandat.beendet is None and not altmandat.aktiv
    assert not altmandat.mitglied.ist_mandatar
    assert Mandat.aktive_von(altmandat.mitglied).count() == 0
    assert audit("vertretung_beendet")[0]["mandatsvereinbarung_endet"] is False
    assert vertrauensfragen_fortschreiben(ende + tage(40)) == 0


def test_die_mandatsvereinbarung_endet_nur_mit_lit_h(ordnung, altmandat):  # noqa: F811
    altmandat.mandatsvereinbarung_lit_h_am = date(2026, 9, 20)
    altmandat.save()
    leute = [mitglied_anlegen(f"m{i}") for i in range(5)]
    t0 = timezone.now()
    antrag = einbringen(leute[0], altmandat, ordnung, jetzt=t0)
    unterstuetzen(antrag, leute[1:2], t0 + tage(1))
    antrag.fortschreiben(t0 + tage(7))
    abstimmen(antrag, leute, "ja", t0 + tage(8))
    antrag.fortschreiben(t0 + tage(14))
    vertrauensfragen_fortschreiben(t0 + tage(50))
    altmandat.refresh_from_db()
    assert altmandat.mandatsvereinbarung_endet_am == timezone.localdate(t0 + tage(44))
    assert altmandat.vertretung_beendet_am == timezone.localdate(t0 + tage(44))
    assert altmandat.beendet is None


def test_gewonnen_laesst_alle_rechtspositionen_unveraendert(ordnung, altmandat):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(5)]
    rolle = rolle_geben(altmandat.mitglied, Gremium.KOORDINATIONSRAT)
    t0 = timezone.now()
    antrag = einbringen(leute[0], altmandat, ordnung, jetzt=t0)
    unterstuetzen(antrag, leute[1:2], t0 + tage(1))
    antrag.fortschreiben(t0 + tage(7))
    abstimmen(antrag, leute, "nein", t0 + tage(8))
    antrag.fortschreiben(t0 + tage(14))
    antrag.refresh_from_db()
    altmandat.refresh_from_db()
    rolle.refresh_from_db()
    vf = antrag.vertrauensfrage
    assert antrag.phase == "abgelehnt" and vf.gewonnen and vf.ergebnis_wort == "Vertrauensfrage gewonnen"
    assert vf.wirkungen_ab is None and altmandat.vertrauen_entzogen_am is None and rolle.aktiv
    assert not Hinweis.objects.filter(quelle="vertrauensfrage").exists()
    assert audit("vertrauensfrage_gewonnen") and not audit("vertrauensfrage_verloren")
    assert vertrauensfragen_fortschreiben(t0 + tage(60)) == 0


def test_verfehlte_beteiligung_heisst_gewonnen(ordnung, altmandat):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(40)]
    t0 = timezone.now()
    antrag = einbringen(leute[0], altmandat, ordnung, jetzt=t0)
    unterstuetzen(antrag, leute[1:4], t0 + tage(1))
    antrag.fortschreiben(t0 + tage(7))
    abstimmen(antrag, leute[:1], "ja", t0 + tage(8))  # 1 von 41 — unter fünf Prozent
    antrag.fortschreiben(t0 + tage(14))
    antrag.refresh_from_db()
    assert antrag.phase == "abgelehnt" and antrag.vertrauensfrage.gewonnen


def test_ohne_schwelle_verfaellt_der_antrag_und_sperrt_sechs_monate_ohne_neuen_anlass(ordnung, altmandat):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(40)]
    t0 = timezone.now()
    alt = einbringen(leute[0], altmandat, ordnung, anlaesse=[abweichung(altmandat, eingetragen_am=t0 - tage(5))], jetzt=t0)
    assert alt.fortschreiben(t0 + tage(31)) is True
    alt.refresh_from_db()
    assert alt.phase == "verfallen" and alt.phase_beginn == t0 + tage(30)
    # derselbe alte Anlass: Sperre nach lit g fünfter Fall — als Hinweis
    alter_anlass = alt.vertrauensfrage.anlaesse.first()
    neu = einbringen(leute[1], altmandat, ordnung, anlaesse=[alter_anlass], jetzt=t0 + tage(40))
    assert "fünfter Fall" in neu.vertrauensfrage.sperrhinweis
    assert "zweiter Fall" not in neu.vertrauensfrage.sperrhinweis
    # ein Anlass, der nach der Einbringung des verfallenen Antrags entstand: keine Sperre aus diesem Grund
    frisch = abweichung(altmandat, tag=timezone.localdate(t0 + tage(35)), gegenstand="Kanal", eingetragen_am=t0 + tage(36))
    neu.phase = Phase.ZURUECKGEZOGEN.value
    neu.save(update_fields=["phase"])
    dritter = einbringen(leute[2], altmandat, ordnung, anlaesse=[frisch], jetzt=t0 + tage(41))
    assert "fünfter Fall" not in dritter.vertrauensfrage.sperrhinweis


# ── Rechtsschutz (lit h) ───────────────────────────────────────────────────────────────────


def _verloren(ordnung, mandat, n=5):  # noqa: F811
    leute = [mitglied_anlegen(f"w{next(_N)}") for _ in range(n)]
    t0 = timezone.now()
    antrag = einbringen(leute[0], mandat, ordnung, jetzt=t0)
    unterstuetzen(antrag, leute[1:2], t0 + tage(1))
    antrag.fortschreiben(t0 + tage(7))
    abstimmen(antrag, leute, "ja", t0 + tage(8))
    antrag.fortschreiben(t0 + tage(14))
    antrag.refresh_from_db()
    mandat.refresh_from_db()
    return antrag, t0 + tage(14)


def test_eine_anfechtung_haelt_stufe_zwei_an_und_eine_aufhebung_stellt_alles_wieder_her(ordnung, altmandat):  # noqa: F811
    rolle = rolle_geben(altmandat.mitglied, Gremium.BERICHTSWESENRAT)
    antrag, ende = _verloren(ordnung, altmandat)
    vf = antrag.vertrauensfrage
    vertrauensfrage_anfechtung_vermerken(vf, "PSG 2026/3", jetzt=ende + tage(2))
    vf.refresh_from_db()
    assert vf.rechtsschutz_stand == "beim Parteischiedsgericht anhängig" and vf.aktenkennung == "PSG 2026/3"
    assert vertrauensfragen_fortschreiben(ende + tage(40)) == 0  # wartet auf die Entscheidung
    altmandat.refresh_from_db()
    assert altmandat.vertretung_beendet_am is None
    vertrauensfrage_entscheidung_vermerken(vf, "aufgehoben", jetzt=ende + tage(20))
    vf.refresh_from_db()
    rolle.refresh_from_db()
    altmandat.refresh_from_db()
    assert vf.rechtsschutz_stand == "vom Parteischiedsgericht aufgehoben"
    assert rolle.aktiv and rolle.ruht_seit is None and rolle.ruht_grund == ""
    assert altmandat.vertrauen_entzogen_am is None and not altmandat.kandidatursperre
    assert audit("vertrauensfrage_aufgehoben")[0]["rollen_wiederhergestellt"] == [rolle.pk]
    assert vertrauensfragen_fortschreiben(ende + tage(90)) == 0
    # lit h: Nach einer Aufhebung läuft die Sperre nach lit g dritter Fall nicht
    hinweis = mm.sperren_pruefen(altmandat, ende + tage(21))
    assert "dritter Fall" not in hinweis


def test_eine_bestaetigende_entscheidung_laesst_stufe_zwei_ab_der_entscheidung_laufen(ordnung, altmandat):  # noqa: F811
    rolle = rolle_geben(altmandat.mitglied, Gremium.BERICHTSWESENRAT)
    antrag, ende = _verloren(ordnung, altmandat)
    vf = antrag.vertrauensfrage
    vertrauensfrage_anfechtung_vermerken(vf, jetzt=ende + tage(3))
    vertrauensfrage_entscheidung_vermerken(vf, "bestaetigt", jetzt=ende + tage(35))
    vf.refresh_from_db()
    assert vf.endgueltig_ab() == ende + tage(35)
    assert vertrauensfragen_fortschreiben(ende + tage(34)) == 0
    assert vertrauensfragen_fortschreiben(ende + tage(35)) == 1
    vf.refresh_from_db()
    rolle.refresh_from_db()
    altmandat.refresh_from_db()
    assert vf.wirkungen_endgueltig_am == ende + tage(35) and rolle.beendet_grund
    # Rückgabefrist (30 Tage) war schon um — die Vertretung endet mit der Entscheidung, nicht davor (Z 5)
    assert altmandat.vertretung_beendet_am == timezone.localdate(ende + tage(35))
    with pytest.raises(VertrauensfrageFehler):
        vertrauensfrage_entscheidung_vermerken(vf, "")


# ── Bestätigung (lit f Z 3) ────────────────────────────────────────────────────────────────


def test_bestaetigung_nur_durch_die_person_selbst_und_erst_nach_sechs_monaten(ordnung, altmandat):  # noqa: F811
    antrag, ende = _verloren(ordnung, altmandat)
    ich = altmandat.mitglied
    with pytest.raises(VertrauensfrageFehler, match="betroffene Person"):
        vertrauensfrage_einbringen(mitglied_anlegen("x"), altmandat, "", [], [], ordnung, art="bestaetigung")
    with pytest.raises(VertrauensfrageFehler, match="frühestens"):
        vertrauensfrage_einbringen(ich, altmandat, "", [], [], ordnung, jetzt=ende + tage(100), art="bestaetigung")
    spaeter = ende + tage(200)
    b = vertrauensfrage_einbringen(ich, altmandat, "Seither halte ich mich an jeden Beschluss.", [], [], ordnung, jetzt=spaeter, art="bestaetigung")
    vf = b.vertrauensfrage
    assert b.art == Antragsart.VERTRAUENSFRAGE and vf.art == "bestaetigung" and b.phase == "unterstuetzung"
    assert b.policy().unterstuetzung_schwelle == 0 and vf.schwelle_erreicht_am == spaeter
    assert vf.sperrhinweis == "" and b.titel.startswith("Bestätigung nach § 7 Abs 10")
    assert len(mail.outbox) == 1  # nur die Vertrauensfrage selbst verständigt, nicht der eigene Antrag
    with pytest.raises(VertrauensfrageFehler, match="läuft bereits"):
        vertrauensfrage_einbringen(ich, altmandat, "", [], [], ordnung, jetzt=spaeter + tage(1), art="bestaetigung")
    assert b.fortschreiben(spaeter + tage(6)) is False
    assert b.fortschreiben(spaeter + tage(7)) is True
    b.refresh_from_db()
    assert b.phase == "abstimmung" and b.phase_beginn == spaeter + tage(7)
    leute = [mitglied_anlegen(f"b{i}") for i in range(3)]
    abstimmen(b, leute + [ich], "ja", spaeter + tage(8))
    b.fortschreiben(spaeter + tage(14))
    altmandat.refresh_from_db()
    b.refresh_from_db()
    assert b.phase == "angenommen" and b.vertrauensfrage.ergebnis_wort == "bestätigt"
    assert altmandat.bestaetigt_am == timezone.localdate(spaeter + tage(14)) and not altmandat.kandidatursperre
    assert audit("bestaetigung_angenommen") and audit("vertrauen_bestaetigt")[0]["grund"] == "antrag"
    # eine Bestätigung ist keine Vertrauensfrage — sie löst keine Sperre nach lit g aus
    assert "zweiter Fall" not in mm.sperren_pruefen(altmandat, spaeter + tage(8))
    with pytest.raises(VertrauensfrageFehler, match="keine verlorene"):
        vertrauensfrage_einbringen(ich, altmandat, "", [], [], ordnung, jetzt=spaeter + tage(20), art="bestaetigung")


def test_eine_abgelehnte_bestaetigung_sperrt_weitere_sechs_monate(ordnung, altmandat):  # noqa: F811
    antrag, ende = _verloren(ordnung, altmandat)
    ich = altmandat.mitglied
    t1 = ende + tage(200)
    b = vertrauensfrage_einbringen(ich, altmandat, "", [], [], ordnung, jetzt=t1, art="bestaetigung")
    b.fortschreiben(t1 + tage(7))
    abstimmen(b, [mitglied_anlegen(f"n{i}") for i in range(3)], "nein", t1 + tage(8))
    b.fortschreiben(t1 + tage(14))
    b.refresh_from_db()
    assert b.phase == "abgelehnt" and b.vertrauensfrage.ergebnis_wort == "nicht bestätigt"
    assert audit("bestaetigung_abgelehnt")
    altmandat.refresh_from_db()
    assert altmandat.kandidatursperre
    with pytest.raises(VertrauensfrageFehler, match="frühestens"):
        vertrauensfrage_einbringen(ich, altmandat, "", [], [], ordnung, jetzt=t1 + tage(100), art="bestaetigung")
    assert mm.bestaetigung_zulaessig_ab(altmandat) > timezone.localdate(t1 + tage(100))


def test_eine_wahl_in_ein_organ_gilt_als_bestaetigung(ordnung, altmandat):  # noqa: F811
    _verloren(ordnung, altmandat)
    altmandat.refresh_from_db()
    assert altmandat.kandidatursperre
    assert altmandat.bestaetigen("wahl") is True
    assert altmandat.bestaetigen("wahl") is False
    altmandat.refresh_from_db()
    assert not altmandat.kandidatursperre and audit("vertrauen_bestaetigt")[0]["grund"] == "wahl"


# ── Feststellung des Integritätsrats (lit b) ───────────────────────────────────────────────


def _feststellung(antrag, leute, jetzt):
    beschluss = GremienBeschluss.objects.create(
        gremium=Gremium.INTEGRITAETSRAT,
        anlass=Anlass.VERTRAUENSFRAGE_SPERRE,
        gegenstand="Sperre feststellen",
        beschreibung="Schonfrist nach lit g erster Fall.",
        optionen=[{"wert": "dafuer", "name": "dafür"}, {"wert": "dagegen", "name": "dagegen"}],
        antrag=antrag,
        angelegt_von=leute[0],
        status=BeschlussStatus.ENTSCHIEDEN,
        ergebnis="dafuer",
        entschieden_am=jetzt,
    )
    wirkung_anwenden(beschluss, jetzt)
    beschluss.refresh_from_db()
    antrag.refresh_from_db()
    return beschluss


def test_der_feststellungsbeschluss_setzt_den_antrag_auf_nicht_eroeffnet(ordnung):  # noqa: F811
    leute = rat(3)
    frisch = Mandat.objects.create(mitglied=mitglied_anlegen("neu"), bezeichnung="Gemeinderat", ebene="gemeinde")
    t0 = timezone.now()
    antrag = einbringen(mitglied_anlegen("anna"), frisch, ordnung, jetzt=t0)
    antrag.unterstuetzungen.create(mitglied=leute[0])
    beschluss = _feststellung(antrag, leute, t0 + tage(2))
    vf = Vertrauensfrage.objects.get(antrag=antrag)
    assert antrag.phase == "zurueckgewiesen" and "nicht eröffnet" in antrag.zurueckweisung_begruendung
    assert vf.sperre_beschluss == beschluss and vf.nicht_eroeffnet
    assert antrag.unterstuetzungen.count() == 1  # bleibt gespeichert, zählt nicht mehr
    assert beschluss.zustand_vorher["phase"] == "unterstuetzung"
    assert audit("vertrauensfrage_nicht_eroeffnet")[0]["mandat"] == frisch.pk
    assert not Vertrauensfrage.offene_mit_sperrhinweis().exists()
    assert antrag.fortschreiben(t0 + tage(40)) is False  # Endphase


def test_nach_drei_tagen_bleibt_der_beschluss_ohne_wirkung(ordnung):  # noqa: F811
    leute = rat(3)
    frisch = Mandat.objects.create(mitglied=mitglied_anlegen("neu"), bezeichnung="Gemeinderat", ebene="gemeinde")
    t0 = timezone.now()
    antrag = einbringen(mitglied_anlegen("anna"), frisch, ordnung, jetzt=t0)
    beschluss = _feststellung(antrag, leute, t0 + tage(3) + timedelta(minutes=1))
    assert antrag.phase == "unterstuetzung"
    assert "verstrichen" in beschluss.umsetzungsvermerk
    assert Vertrauensfrage.objects.get(antrag=antrag).sperre_beschluss is None


def test_ein_beschluss_zu_einem_sachantrag_oder_eines_unterbesetzten_rats_bewirkt_nichts(ordnung):  # noqa: F811
    leute = rat(2)
    sache = antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung)
    beschluss = _feststellung(sache, leute, timezone.now())
    assert "keine Vertrauensfrage" in beschluss.umsetzungsvermerk and sache.phase == "unterstuetzung"
    frisch = Mandat.objects.create(mitglied=mitglied_anlegen("neu"), bezeichnung="Gemeinderat", ebene="gemeinde")
    antrag = einbringen(mitglied_anlegen("anna"), frisch, ordnung)
    beschluss = _feststellung(antrag, leute, timezone.now())
    assert "nicht satzungsgemäß besetzt" in beschluss.umsetzungsvermerk and antrag.phase == "unterstuetzung"


# ── Rückgabezusage an der Bewerbung, Nachrechnen, Ordnung ─────────────────────────────────


def test_die_bewerbung_traegt_die_rueckgabezusage(ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    kandidatur = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung, art=Antragsart.MANDAT)
    b = bewerbung_einreichen(kandidatur, anna, "Ich trete an.", "nicht_abgegeben")
    assert b.rueckgabezusage == Rueckgabezusage.NICHT_ABGEGEBEN
    assert audit("bewerbung")[0]["rueckgabezusage"] == "nicht_abgegeben"
    bewerbung_einreichen(kandidatur, anna, "Neu.", "")  # ohne Angabe bleibt die Erklärung stehen
    b.refresh_from_db()
    assert b.rueckgabezusage == Rueckgabezusage.NICHT_ABGEGEBEN and b.vorstellung == "Neu."
    bewerbung_einreichen(kandidatur, anna, "", "abgegeben")
    b.refresh_from_db()
    assert b.rueckgabezusage == Rueckgabezusage.ABGEGEBEN
    alt = bewerbung_einreichen(kandidatur, mitglied_anlegen("bert"), "Ohne Erklärung.")
    assert alt.rueckgabezusage == "" and Bewerbung.objects.count() == 2
    with pytest.raises(ValueError):
        bewerbung_einreichen(kandidatur, mitglied_anlegen("carla"), "x", "vielleicht")


def test_nachrechnen_kennt_die_vertrauensfrage():
    nachrechnen = _nachrechnen_laden()
    stimmen = [{"pseudonym": f"p{i}", "stimme": "ja"} for i in range(6)] + [{"pseudonym": "n", "stimme": "nein"}]
    export = {"art": "vertrauensfrage", "policy": {"mindestbeteiligung": 0.05, "mehrheitsbasis": "ja_nein"}, "stimmberechtigte": 20, "stimmen": stimmen}
    ergebnis = nachrechnen(export)
    assert ergebnis["art"] == "vertrauensfrage" and ergebnis["angenommen"] is True and ergebnis["vertrauensfrage"] == "verloren"
    export["stimmberechtigte"] = 1000
    assert nachrechnen(export)["vertrauensfrage"] == "gewonnen"


def test_gegenstand_fuer_jede_antragsart(ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    sache = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    mandat = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung, art=Antragsart.MANDAT)
    assert gegenstand_fuer(sache) is Gegenstand.SACHFRAGE
    assert gegenstand_fuer(mandat) is Gegenstand.PERSONENWAHL
    assert sache._vertrauensfrage() is None


def test_alte_ordnungen_laufen_unveraendert(ordnung):  # noqa: F811
    """Ein Snapshot aus 0.47 ohne die neuen Felder wechselt wie bisher in die Beratung."""
    anna = mitglied_anlegen("anna")
    antrag = antrag_einbringen(anna, **ANTRAG, ordnung=ordnung)
    for feld in ("beratung_entfaellt", "abstimmung_fruehestens_tage", "abstimmung_spaetestens_tage_nach_schwelle"):
        antrag.policy_snapshot.pop(feld, None)
    antrag.save(update_fields=["policy_snapshot"])
    for m in (anna, mitglied_anlegen("bert")):
        antrag.unterstuetzungen.create(mitglied=m)
    assert antrag.fortschreiben() is True
    antrag.refresh_from_db()
    assert antrag.phase == "beratung"
