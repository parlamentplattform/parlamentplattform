"""Die Auslosung im Verfahren (FB-I1, § 6 Abs 7) — verankert, gebunden, nachrechenbar.

Bis 0.43 galt eine Rolle parteiweit: Wer in Gruppe 1 berufen war, schrieb an jedem Entwurf.
§ 6 Abs 7 will das Gegenteil — „für die Beratung zu **einzelnen Anträgen**". Diese Tests prüfen
die drei Stellen, an denen das hängt: dass gelost wird, dass die Ziehung nachrechenbar ist, und
dass eine für Antrag A geloste Fachkraft an Antrag B nichts zu suchen hat.
"""

from __future__ import annotations

import itertools

import pytest
from django.urls import reverse

from gremien.models import Auslosung, Fachliste, Gremium, Rolle
from gremien.test_werkstatt import (  # noqa: F401
    in_beratung_bringen,
    mitglied_anlegen,
    ordnung,
    rolle_geben,
)
from plattform_core.losziehung import loswert
from verfahren.models import AuditEintrag, Kategorie, antrag_einbringen

pytestmark = pytest.mark.django_db

_ZAEHLER = itertools.count()

ANTRAG = {
    "titel": "Radwege entlang der Hauptstraße",
    "wortlaut": "Die Gemeinde legt entlang der Hauptstraße durchgehende Radwege an.",
    "begruendung": "Wer sicher fahren kann, fährt.",
}


def fachliste_fuellen(anzahl: int = 10) -> list[Fachliste]:
    eintraege = []
    for _ in range(anzahl):
        mitglied = mitglied_anlegen(f"fach{next(_ZAEHLER)}")
        eintraege.append(Fachliste.objects.create(mitglied=mitglied))
    return eintraege


def antrag_in_beratung(ordnung, unterstuetzer=2):  # noqa: F811
    antrag = antrag_einbringen(
        mitglied_anlegen(f"stellerin{next(_ZAEHLER)}"), **ANTRAG, ordnung=ordnung
    )
    return in_beratung_bringen(
        antrag, [mitglied_anlegen(f"u{next(_ZAEHLER)}") for _ in range(unterstuetzer)]
    )


def test_zu_beratungsbeginn_wird_gelost(client, ordnung):  # noqa: F811
    """§ 6 Abs 7 — und erst jetzt, denn erst jetzt steht fest, dass beraten wird."""
    fachliste_fuellen(10)
    antrag = antrag_in_beratung(ordnung)
    auslosung = Auslosung.objects.get(antrag=antrag)
    assert len(auslosung.plaetze) == 3  # eine Gruppe, Größe aus der Ordnung
    rollen = Rolle.objects.filter(antrag=antrag, gremium=Gremium.EXPERTENRAT_1)
    assert rollen.count() == 3
    assert all(r.auslosung_id == auslosung.pk for r in rollen)
    assert any(e.ereignis["typ"] == "expertenrat_ausgelost" for e in AuditEintrag.objects.all())


def test_die_ziehung_laesst_sich_von_hand_nachrechnen(client, ordnung):  # noqa: F811
    """Alles, was zum Nachrechnen nötig ist, steht am Datensatz: Anker, Lostopf, Loswerte."""
    fachliste_fuellen(9)
    antrag = antrag_in_beratung(ordnung)
    a = Auslosung.objects.get(antrag=antrag)
    assert len(a.anker) == 64 and a.anker_lfd > 0
    for platz in a.plaetze:
        assert platz["loswert"] == loswert(a.anker, platz["schluessel"])
    kleinste = sorted(a.lostopf, key=lambda s: (loswert(a.anker, s), s))[: len(a.plaetze)]
    assert [p["schluessel"] for p in a.plaetze] == kleinste


def test_der_anker_ist_der_kopf_der_audit_kette(client, ordnung):  # noqa: F811
    """Er steht im Augenblick der Ziehung fest und war vorher von niemandem auszurechnen."""
    fachliste_fuellen(9)
    antrag = antrag_in_beratung(ordnung)
    a = Auslosung.objects.get(antrag=antrag)
    eintrag = AuditEintrag.objects.get(lfd=a.anker_lfd)
    assert eintrag.hash == a.anker


def test_ohne_genug_fachleute_wird_nicht_halb_gelost(client, ordnung):  # noqa: F811
    """Eine halb besetzte Gruppe sähe nach Beratung aus und wäre keine."""
    fachliste_fuellen(2)
    antrag = antrag_in_beratung(ordnung)
    assert not Auslosung.objects.filter(antrag=antrag).exists()
    assert not Rolle.objects.filter(antrag=antrag).exists()
    gruende = [
        e.ereignis for e in AuditEintrag.objects.all() if e.ereignis["typ"] == "auslosung_nicht_moeglich"
    ]
    assert gruende and "Lostopf" in gruende[0]["grund"]


def test_ohne_fachliste_laeuft_das_verfahren_wie_bisher(client, ordnung):  # noqa: F811
    """Verfahren, die es vor der Auslosung schon gab, werden nicht mitten im Lauf umgestellt."""
    berufene = mitglied_anlegen("berufene")
    rolle_geben(berufene, Gremium.EXPERTENRAT_1)
    antrag = antrag_in_beratung(ordnung)
    assert not Auslosung.objects.filter(antrag=antrag).exists()
    assert Rolle.hat_fuer(berufene, Gremium.EXPERTENRAT_1, antrag) is True


def test_wer_fuer_einen_anderen_antrag_gelost_ist_schreibt_hier_nicht(client, ordnung):  # noqa: F811
    """Sonst wäre die Auslosung eine Anzeige statt einer Zuständigkeit."""
    fachliste_fuellen(12)
    erster = antrag_in_beratung(ordnung)
    zweiter = antrag_in_beratung(ordnung)
    # Wer auf der Fachliste steht, kann für mehrere Anträge gelost werden — das ist richtig so.
    # Für diesen Test brauchen wir jemanden, der nur beim ersten dabei ist.
    beim_zweiten = set(
        Rolle.objects.filter(antrag=zweiter).values_list("mitglied_id", flat=True)
    )
    fuer_ersten = (
        Rolle.objects.filter(antrag=erster, gremium=Gremium.EXPERTENRAT_1)
        .exclude(mitglied_id__in=beim_zweiten)
        .first()
    )
    assert fuer_ersten is not None, "bei zwölf Fachleuten und je drei Plätzen praktisch sicher"
    assert Rolle.hat_fuer(fuer_ersten.mitglied, Gremium.EXPERTENRAT_1, erster) is True
    assert Rolle.hat_fuer(fuer_ersten.mitglied, Gremium.EXPERTENRAT_1, zweiter) is False

    # Und die Sperre wirkt auch am Formular, nicht nur in der Abfrage.
    client.force_login(fuer_ersten.mitglied)
    client.post(reverse("gremien:fenster_aktion", args=[zweiter.pk]), {"aktion": "oeffnen"})
    from gremien.models import Entwurf

    assert not Entwurf.objects.filter(antrag=zweiter).exists()
    client.post(reverse("gremien:fenster_aktion", args=[erster.pk]), {"aktion": "oeffnen"})
    assert Entwurf.objects.filter(antrag=erster).exists()


def test_das_quorum_zaehlt_nur_die_fuer_diese_sache_gelosten(client, ordnung):  # noqa: F811
    """Sonst zählte ein Beschluss zu Antrag A alle Rollen der Partei — und wäre nie
    beschlussfähig, sobald die Plattform mehrere Verfahren zugleich führt."""
    from gremien.models import GremienBeschluss

    fachliste_fuellen(14)
    erster = antrag_in_beratung(ordnung)
    antrag_in_beratung(ordnung)  # ein zweites Verfahren mit eigenen Gelosten
    assert Rolle.aktive(Gremium.EXPERTENRAT_1).count() == 6
    beschluss = GremienBeschluss.objects.create(
        gremium=Gremium.EXPERTENRAT_1,
        gegenstand="Probe",
        optionen=[{"wert": "dafuer", "name": "dafür"}],
        antrag=erster,
        angelegt_von=Rolle.objects.filter(antrag=erster).first().mitglied,
    )
    assert beschluss.aktive_rollen() == 3


def test_die_groessen_kommen_aus_der_eingefrorenen_ordnung(client, ordnung):  # noqa: F811
    """§ 5 Abs 5: Eine Registeränderung darf einen laufenden Antrag nicht mehr erreichen."""
    from parameter.models import Parameter

    fachliste_fuellen(12)
    antrag = antrag_einbringen(mitglied_anlegen("stellerin-x"), **ANTRAG, ordnung=ordnung)
    Parameter.objects.update_or_create(
        schluessel="expertenrat-gruppe1-groesse",
        defaults={"wert": "7", "beschreibung": "x", "quelle": "Test"},
    )
    in_beratung_bringen(antrag, [mitglied_anlegen("uu1"), mitglied_anlegen("uu2")])
    auslosung = Auslosung.objects.get(antrag=antrag)
    assert auslosung.groessen == [antrag.policy().expertenrat_gruppe1] == [3]


def vollzugsbezug_setzen(client, antrag):
    """Der erreichbare Weg: Ein Mitglied der gelosten Gruppe 1 öffnet das Fenster und setzt den Bezug."""
    rat = Rolle.objects.filter(antrag=antrag, gremium=Gremium.EXPERTENRAT_1).first().mitglied
    client.force_login(rat)
    aktion = reverse("gremien:fenster_aktion", args=[antrag.pk])
    client.post(aktion, {"aktion": "oeffnen"})
    client.post(aktion, {"aktion": "vollzugsbezug", "vollzugsbezug": "ja"})


def test_ein_vollzugsbezug_zieht_die_zweite_gruppe_nach(client, ordnung):  # noqa: F811
    """Befund #14/#37: Zu Beratungsbeginn gibt es keinen Entwurf — der Vollzugsbezug wird erst
    in der Werkstatt gesetzt. Bis 0.45 wurde Gruppe 2 deshalb im Echtbetrieb nie gelost.
    Jetzt zieht das Setzen des Bezugs eine zweite Runde nur für Gruppe 2 — aus dem Rest des
    Lostopfs, mit eigenem Anker, ohne Gruppe 1 anzutasten (§ 6 Abs 7)."""
    fachliste_fuellen(12)
    antrag = antrag_in_beratung(ordnung)
    erste = Auslosung.objects.get(antrag=antrag)
    gruppe_1 = set(Rolle.objects.filter(antrag=antrag, gremium=Gremium.EXPERTENRAT_1).values_list("pk", flat=True))
    assert len(gruppe_1) == 3 and not Rolle.objects.filter(antrag=antrag, gremium=Gremium.EXPERTENRAT_2).exists()

    vollzugsbezug_setzen(client, antrag)

    zweite = Auslosung.objects.get(antrag=antrag, runde=2)
    assert zweite.groessen == [antrag.policy().expertenrat_gruppe2] == [3]
    assert [p["gruppe"] for p in zweite.plaetze] == [2, 2, 2], "der Platz nennt die tatsächliche Gruppe"
    assert zweite.anker != erste.anker and zweite.anker_lfd > erste.anker_lfd
    gruppe_2 = Rolle.objects.filter(antrag=antrag, gremium=Gremium.EXPERTENRAT_2)
    assert gruppe_2.count() == 3 and all(r.auslosung_id == zweite.pk for r in gruppe_2)
    # Gruppe 1 bleibt, wie sie war — und niemand sitzt in beiden.
    assert set(Rolle.objects.filter(antrag=antrag, gremium=Gremium.EXPERTENRAT_1).values_list("pk", flat=True)) == gruppe_1
    leute_1 = set(Rolle.objects.filter(pk__in=gruppe_1).values_list("mitglied_id", flat=True))
    assert not (leute_1 & set(gruppe_2.values_list("mitglied_id", flat=True))), "§ 6 Abs 7: unabhängig besetzt"
    ausgeschlossen = {schluessel for schluessel, _grund in zweite.ausgeschlossen}
    assert {p["schluessel"] for p in erste.plaetze} <= ausgeschlossen
    audit = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis["typ"] == "expertenrat_ausgelost"]
    assert audit[-1]["gruppen"] == [2] and all(g == 2 for g, _s in audit[-1]["plaetze"])


def test_gruppe_2_wird_nur_einmal_nachgezogen(client, ordnung):  # noqa: F811
    """Den Bezug zweimal setzen — oder ihn setzen und dann einreichen — lost keine dritte Gruppe."""
    fachliste_fuellen(12)
    antrag = antrag_in_beratung(ordnung)
    vollzugsbezug_setzen(client, antrag)
    vollzugsbezug_setzen(client, antrag)
    assert Auslosung.objects.filter(antrag=antrag).count() == 2
    from gremien.models import Entwurf

    Entwurf.objects.get(antrag=antrag).einreichen()
    assert Auslosung.objects.filter(antrag=antrag).count() == 2
    assert Rolle.objects.filter(antrag=antrag, gremium=Gremium.EXPERTENRAT_2).count() == 3


def test_die_geloste_gruppe_2_prueft_den_vorschlag(client, ordnung):  # noqa: F811
    """Die Prüfabstimmung entsteht bei den Gelosten — nicht bei parteiweit berufenen Rollen."""
    from gremien.models import BeschlussStatus, Entwurf, EntwurfsStatus, GremienBeschluss

    berufen = mitglied_anlegen("berufen-e2")
    rolle_geben(berufen, Gremium.EXPERTENRAT_2)  # parteiweit — der alte Rückfall
    fachliste_fuellen(12)
    antrag = antrag_in_beratung(ordnung)
    vollzugsbezug_setzen(client, antrag)
    entwurf = Entwurf.objects.get(antrag=antrag)
    entwurf.einreichen()
    assert entwurf.status == EntwurfsStatus.PRUEFUNG
    beschluss = GremienBeschluss.objects.get(entwurf=entwurf, gremium=Gremium.EXPERTENRAT_2, status=BeschlussStatus.OFFEN)
    assert beschluss.aktive_rollen() == 3
    assert beschluss.angelegt_von != berufen
    assert Rolle.hat_fuer(berufen, Gremium.EXPERTENRAT_2, antrag) is False


def test_spaetestens_das_einreichen_zieht_gruppe_2(client, ordnung):  # noqa: F811
    """Wurde der Bezug ohne die Werkstatt gesetzt, holt das Einreichen die Ziehung nach."""
    from gremien.models import Entwurf

    fachliste_fuellen(12)
    antrag = antrag_in_beratung(ordnung)
    entwurf = Entwurf.objects.create(antrag=antrag, vollzugsbezug=True)
    entwurf.fassungen.create(nummer=1, wortlaut="x", verfasst_von=Rolle.objects.filter(antrag=antrag).first().mitglied)
    entwurf.einreichen()
    assert Rolle.objects.filter(antrag=antrag, gremium=Gremium.EXPERTENRAT_2).count() == 3


def test_ohne_ausreichenden_lostopf_bleibt_der_bisherige_rueckfall(client, ordnung):  # noqa: F811
    """Reicht die Fachliste nur für Gruppe 1, wird Gruppe 2 nicht halb gelost — es bleibt beim
    Rückfall auf parteiweite Rollen, und das Audit sagt, warum."""
    fachliste_fuellen(4)
    antrag = antrag_in_beratung(ordnung)
    vollzugsbezug_setzen(client, antrag)
    assert Auslosung.objects.filter(antrag=antrag).count() == 1
    assert not Rolle.objects.filter(antrag=antrag, gremium=Gremium.EXPERTENRAT_2).exists()
    gruende = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis["typ"] == "auslosung_nicht_moeglich"]
    assert gruende and gruende[-1]["gruppen"] == [2]


def test_nur_fachleute_des_lebensbereichs_werden_gezogen(client, ordnung):  # noqa: F811
    """§ 6 Abs 7 spricht von Fachleuten — wer das Fach nicht führt, lost nicht mit."""
    verkehr, _ = Kategorie.objects.get_or_create(slug="verkehr", defaults={"name": "Verkehr"})
    bildung, _ = Kategorie.objects.get_or_create(slug="bildung", defaults={"name": "Bildung"})
    passend = fachliste_fuellen(5)
    for e in passend:
        e.fachgebiete.add(verkehr)
    for e in fachliste_fuellen(5):
        e.fachgebiete.add(bildung)
    antrag = antrag_einbringen(mitglied_anlegen("stellerin-f"), **ANTRAG, ordnung=ordnung)
    antrag.kategorien.set([verkehr])
    in_beratung_bringen(antrag, [mitglied_anlegen("ff1"), mitglied_anlegen("ff2")])
    auslosung = Auslosung.objects.get(antrag=antrag)
    gezogen = {p["schluessel"] for p in auslosung.plaetze}
    assert gezogen <= {e.schluessel for e in passend}


def test_die_ziehung_steht_oeffentlich_zum_nachrechnen(client, ordnung):  # noqa: F811
    """§ 2 Abs 6: nachrechenbar. Wer prüfen will, ob gelost und nicht ausgesucht wurde,
    braucht Anker, Lostopf und Loswerte — ohne Anmeldung."""
    fachliste_fuellen(9)
    antrag = antrag_in_beratung(ordnung)
    a = Auslosung.objects.get(antrag=antrag)
    inhalt = client.get(reverse("gremien:auslosung", args=[antrag.pk])).content.decode()
    assert a.anker in inhalt
    assert str(a.anker_lfd) in inhalt
    for schluessel in a.lostopf:
        assert schluessel in inhalt
    assert "Anker|Schlüssel" in inhalt or "Anker|Schl" in inhalt


def test_ohne_ziehung_sagt_die_seite_das_auch(client, ordnung):  # noqa: F811
    antrag = antrag_in_beratung(ordnung)
    inhalt = client.get(reverse("gremien:auslosung", args=[antrag.pk])).content.decode()
    assert "nicht gelost" in inhalt
