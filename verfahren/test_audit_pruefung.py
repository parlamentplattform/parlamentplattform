"""Die Audit-Kette wird nachgerechnet (Bestandsaufnahme A7, Schritt 2 · 0.52.0): täglich stückweise,
regelmäßig von vorn, als Befehl für CI und Wiederherstellungsprobe — und das Ergebnis ist öffentlich."""

from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.utils import timezone

from verfahren.audit_pruefung import LAUF, gemerkter_stand, lauf, pruefen
from verfahren.hintergrund import LAEUFE, ausfuehren
from verfahren.models import AuditEintrag, Hintergrundlauf

pytestmark = pytest.mark.django_db


def kette(n=3):
    return [AuditEintrag.anhaengen({"typ": "probe", "nr": i}) for i in range(n)]


def verfaelschen(eintrag, **aenderung):
    """Wie jemand mit Datenbankzugriff: den Inhalt ändern, ohne den Hash nachzurechnen."""
    AuditEintrag.objects.filter(pk=eintrag.pk).update(ereignis={**eintrag.ereignis, **aenderung})


def test_die_leere_kette_ist_intakt():
    stand = pruefen()
    assert stand["intakt"] and stand["eintraege"] == 0 and stand["geprueft"] == 0 and stand["voll"]


def test_eine_unveraenderte_kette_ist_intakt_und_nennt_ihren_kopf():
    eintraege = kette()
    stand = pruefen()
    assert stand["intakt"] and stand["geprueft"] == 3 and stand["kopf"] == eintraege[-1].hash
    assert stand["geprueft_bis"] == eintraege[-1].lfd and stand["bruch"] is None


def test_ein_veraenderter_eintrag_wird_mit_seiner_nummer_gefunden():
    eintraege = kette(4)
    verfaelschen(eintraege[1], nr=99)
    stand = pruefen(voll=True)
    assert not stand["intakt"] and stand["bruch"] == eintraege[1].lfd and stand["grund"] == "hash"
    assert stand["geprueft_bis"] == eintraege[0].lfd


def test_ein_geloeschter_eintrag_bricht_die_kette():
    eintraege = kette(3)
    AuditEintrag.objects.filter(pk=eintraege[1].pk).delete()  # nur im Test: der Admin kann es nicht
    stand = pruefen(voll=True)
    assert not stand["intakt"] and stand["bruch"] == eintraege[2].lfd and stand["grund"] == "vorgaenger"


def test_die_pruefung_setzt_stueckweise_fort():
    kette(3)
    erster = pruefen()
    neu = kette(2)
    zweiter = pruefen(stand=erster)
    assert zweiter["intakt"] and not zweiter["voll"] and zweiter["geprueft"] == 2
    assert zweiter["kopf"] == neu[-1].hash and zweiter["eintraege"] == 5


def test_ein_veraenderter_anker_faellt_auch_stueckweise_auf():
    eintraege = kette(3)
    erster = pruefen()
    verfaelschen(eintraege[-1], nr=42)
    stand = pruefen(stand=erster)
    assert not stand["intakt"] and stand["grund"] == "anker" and stand["bruch"] == eintraege[-1].lfd


def test_eine_aenderung_vor_dem_anker_findet_die_vollpruefung():
    """Stückweise sieht nur neue Einträge und den Anker — die Vollprüfung nach `audit-vollpruefung-tage`
    rechnet von vorn und findet die Änderung an einem alten Eintrag."""
    eintraege = kette(4)
    erster = pruefen()
    verfaelschen(eintraege[0], nr=7)
    assert pruefen(stand=erster)["intakt"]  # stückweise nicht zu sehen
    spaeter = timezone.now() + timedelta(days=8)
    stand = pruefen(stand=erster, jetzt=spaeter)
    assert stand["voll"] and not stand["intakt"] and stand["bruch"] == eintraege[0].lfd


def test_der_hintergrundlauf_merkt_sich_den_stand():
    kette(2)
    audit = next(la for la in LAEUFE if la.name == LAUF)
    assert audit.takt_minuten() == 24 * 60
    assert ausfuehren(audit)
    stand = gemerkter_stand()
    assert stand["intakt"] and stand["eintraege"] == 2
    kette(1)
    Hintergrundlauf.objects.filter(name=LAUF).update(zuletzt_begonnen=timezone.now() - timedelta(days=2))
    assert ausfuehren(audit)
    assert gemerkter_stand()["geprueft"] == 1  # nur der neue
    assert lauf()["intakt"]


def test_der_befehl_meldet_intakt_und_bricht_mit_fehlercode_ab(capsys):
    eintraege = kette(3)
    call_command("audit_pruefen", "--voll")
    assert "Audit-Kette intakt: 3 Einträge vollständig geprüft" in capsys.readouterr().out
    verfaelschen(eintraege[2], nr=0)
    with pytest.raises(CommandError, match=f"gebrochen bei Eintrag {eintraege[2].lfd}"):
        call_command("audit_pruefen", "--voll")


def test_die_kennzahlen_nennen_ergebnis_und_kopf_ohne_personenbezug(client):
    from plattform_core.schema import pruefe_export

    assert "audit.head" not in client.get("/kennzahlen.json").content.decode()  # nie geprüft: nichts
    eintraege = kette(2)
    audit = next(la for la in LAEUFE if la.name == LAUF)
    ausfuehren(audit)
    daten = client.get("/kennzahlen.json").json()
    werte = {k["schema_key"]: k["wert"] for k in daten["kennzahlen"]}
    assert werte["audit.chain_intact"] == 1 and werte["audit.entries"] == 2
    assert werte["audit.head"] == eintraege[-1].hash and werte["audit.verified_at"]
    assert pruefe_export(daten) == []
