"""M3 — Mandats-Kandidaturen als Anträge (§ 7 Abs 1 E-2.5, F-70):
Bewerben, Zustimmungswahl, Auszählung, Geheimhaltung, Export."""

from datetime import timedelta
from types import SimpleNamespace

import pytest
from django.urls import reverse
from django.utils import timezone

from plattform_core.tally import AuszaehlungsFehler, personenwahl_auszaehlen
from verfahren.models import (
    Antrag,
    Antragsart,
    BewerbungsFehler,
    StimmabgabeFehler,
    antrag_einbringen,
    bewerbung_einreichen,
    bewerbung_zustimmen,
)
from verfahren.test_views_aktionen import (  # noqa: F401
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db

MANDAT = {
    "titel": "Listenreihung Gemeinderat",
    "wortlaut": "Reihung des DDÖ-Wahlvorschlags für die Gemeinderatswahl.",
    "begruendung": "",
}
POLICY = SimpleNamespace(mindestbeteiligung=0.05)


# --- Auszählung (rein, ohne Datenbank) --------------------------------------------


def test_meiste_zustimmung_gewinnt_und_reihung_ergibt_die_liste():
    wahl = personenwahl_auszaehlen(
        [("p1", 2), ("p2", 2), ("p1", 1), ("p3", 2)],
        bewerbungen=[1, 2, 3],
        stimmberechtigte=10,
        policy=POLICY,
    )
    assert [(p.platz, p.bewerbung_id, p.stimmen) for p in wahl.plaetze] == [
        (1, 2, 3),
        (2, 1, 1),
        (3, 3, 0),
    ]
    assert wahl.gewonnen_id == 2 and wahl.angenommen and wahl.beteiligung == 3


def test_gleichstand_geht_an_die_fruehere_bewerbung():
    wahl = personenwahl_auszaehlen(
        [("p1", 7), ("p2", 5)], bewerbungen=[5, 7], stimmberechtigte=10, policy=POLICY
    )
    assert wahl.gewonnen_id == 5  # gleich viele Stimmen — Bewerbung 5 war zuerst da


def test_mindestbeteiligung_gilt_auch_fuer_personenwahlen():
    wahl = personenwahl_auszaehlen([("p1", 1)], bewerbungen=[1], stimmberechtigte=100, policy=POLICY)
    assert not wahl.beteiligung_erreicht and not wahl.angenommen and wahl.gewonnen_id is None


def test_doppelte_zustimmung_ist_ein_fehler():
    with pytest.raises(AuszaehlungsFehler):
        personenwahl_auszaehlen([("p1", 1), ("p1", 1)], bewerbungen=[1], stimmberechtigte=5, policy=POLICY)


def test_ohne_bewerbung_kein_ergebnis():
    wahl = personenwahl_auszaehlen([], bewerbungen=[], stimmberechtigte=5, policy=POLICY)
    assert not wahl.angenommen and wahl.plaetze == ()


# --- Verfahren in der Datenbank ---------------------------------------------------


def _kandidatur(ordnung, autor):  # noqa: F811
    return antrag_einbringen(autor, **MANDAT, ordnung=ordnung, art=Antragsart.MANDAT)


def _in_abstimmung(antrag, unterstuetzer):
    for u in unterstuetzer:
        antrag.unterstuetzungen.create(mitglied=u)
    antrag.fortschreiben()
    antrag.phase_beginn = timezone.now() - timedelta(days=22)
    antrag.save(update_fields=["phase_beginn"])
    antrag.fortschreiben()
    assert antrag.phase == "abstimmung"
    return antrag


def test_bewerben_bis_abstimmungsbeginn_dann_nicht_mehr(ordnung):  # noqa: F811
    autor, anna, bernd = mitglied_anlegen("autor"), mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    antrag = _kandidatur(ordnung, autor)
    b = bewerbung_einreichen(antrag, anna, "Ich stehe für offene Sitzungen.")
    bewerbung_einreichen(antrag, anna, "Aktualisierte Vorstellung.")  # erneuern statt doppelt
    assert antrag.bewerbungen.count() == 1
    b.refresh_from_db()
    assert b.vorstellung == "Aktualisierte Vorstellung."

    _in_abstimmung(antrag, [autor, bernd])
    with pytest.raises(BewerbungsFehler):
        bewerbung_einreichen(antrag, bernd, "Zu spät.")


def test_rueckzug_bleibt_dokumentiert_und_zaehlt_nicht(client, ordnung):  # noqa: F811
    autor, anna = mitglied_anlegen("autor"), mitglied_anlegen("anna")
    antrag = _kandidatur(ordnung, autor)
    bewerbung_einreichen(antrag, anna, "Ich trete an.")
    client.force_login(anna)
    client.post(reverse("verfahren:bewerbung_zurueckziehen", args=[antrag.pk]))
    b = antrag.bewerbungen.get()
    assert b.zurueckgezogen
    inhalt = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "zurückgezogen" in inhalt


def test_zustimmung_ist_umschaltbar_und_pseudonym(ordnung):  # noqa: F811
    autor, anna, bernd = mitglied_anlegen("autor"), mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    antrag = _kandidatur(ordnung, autor)
    b1 = bewerbung_einreichen(antrag, anna, "A")
    b2 = bewerbung_einreichen(antrag, autor, "B")
    _in_abstimmung(antrag, [anna, bernd])

    assert bewerbung_zustimmen(antrag, bernd, b1) is True
    assert bewerbung_zustimmen(antrag, bernd, b2) is True  # Zustimmungswahl: mehrere möglich
    assert bewerbung_zustimmen(antrag, bernd, b2) is False  # Umschalter: zurückgenommen
    assert b1.zustimmungen.count() == 1 and b2.zustimmungen.count() == 0
    zustimmung = b1.zustimmungen.get()
    register = antrag.stimmregister.get(mitglied=bernd)
    assert zustimmung.pseudonym == register.pseudonym  # geheim: nur das Pseudonym steht in der Liste


def test_zurueckgezogene_bewerbung_ist_nicht_waehlbar(ordnung):  # noqa: F811
    autor, anna, bernd = mitglied_anlegen("autor"), mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    antrag = _kandidatur(ordnung, autor)
    b = bewerbung_einreichen(antrag, anna, "A")
    b.zurueckgezogen = True
    b.save(update_fields=["zurueckgezogen"])
    _in_abstimmung(antrag, [anna, bernd])
    with pytest.raises(StimmabgabeFehler):
        bewerbung_zustimmen(antrag, bernd, b)


def test_fristablauf_kuert_die_meiste_zustimmung(ordnung):  # noqa: F811
    autor = mitglied_anlegen("autor")
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = _kandidatur(ordnung, autor)
    b1 = bewerbung_einreichen(antrag, leute[0], "Erste")
    b2 = bewerbung_einreichen(antrag, leute[1], "Zweite")
    _in_abstimmung(antrag, leute[:2])
    for waehler in (autor, leute[2]):
        bewerbung_zustimmen(antrag, waehler, b2)
    bewerbung_zustimmen(antrag, leute[0], b1)

    antrag.phase_beginn = timezone.now() - timedelta(days=8)  # Abstimmungsfrist (7 Tage) vorbei
    antrag.save(update_fields=["phase_beginn"])
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase == "angenommen"
    wahl = antrag.kandidatur_auszaehlen()
    assert wahl.gewonnen_id == b2.pk and wahl.plaetze[0].stimmen == 2


def test_ja_nein_ist_bei_kandidaturen_gesperrt(client, ordnung):  # noqa: F811
    autor, anna, bernd = mitglied_anlegen("autor"), mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    antrag = _kandidatur(ordnung, autor)
    bewerbung_einreichen(antrag, anna, "A")
    _in_abstimmung(antrag, [anna, bernd])
    client.force_login(bernd)
    client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": "ja"})
    assert antrag.stimmabgaben.count() == 0  # keine Sach-Stimme an einer Personenwahl


def test_antragsseite_zeigt_bewerbungen_aber_keine_zwischenstaende(client, ordnung):  # noqa: F811
    autor, anna, bernd = mitglied_anlegen("autor"), mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    antrag = _kandidatur(ordnung, autor)
    b = bewerbung_einreichen(antrag, anna, "Ich stehe für offene Sitzungen.")
    _in_abstimmung(antrag, [anna, bernd])
    bewerbung_zustimmen(antrag, bernd, b)

    client.force_login(bernd)
    inhalt = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    assert "Mandats-Kandidatur" in inhalt and "Ich stehe für offene Sitzungen." in inhalt
    assert "Zugestimmt" in inhalt  # der eigene Stand ist sichtbar
    assert "Platz</th>" not in inhalt  # aber keine Zwischenstands-Tabelle (kein Bandwagon, F-15)
    assert 'name="stimme"' not in inhalt  # kein Ja/Nein-Formular bei Personenwahl


def test_einbringen_formular_kennt_die_antragsart(client, ordnung):  # noqa: F811
    client.force_login(mitglied_anlegen("anna"))
    antwort = client.post(reverse("verfahren:einbringen"), {**MANDAT, "art": "mandat"})
    assert antwort.status_code == 302
    assert Antrag.objects.get().art == Antragsart.MANDAT


def test_export_macht_die_wahl_nachrechenbar(client, ordnung):  # noqa: F811
    autor = mitglied_anlegen("autor")
    leute = [mitglied_anlegen(f"m{i}") for i in range(2)]
    antrag = _kandidatur(ordnung, autor)
    b = bewerbung_einreichen(antrag, leute[0], "A")
    _in_abstimmung(antrag, leute)
    bewerbung_zustimmen(antrag, autor, b)
    antrag.phase_beginn = timezone.now() - timedelta(days=8)
    antrag.save(update_fields=["phase_beginn"])

    daten = client.get(reverse("verfahren:export", args=[antrag.pk])).json()
    assert daten["art"] == "mandat"
    assert daten["bewerbungen"][0]["bewerbung"] == b.pk
    assert daten["zustimmungen"] == [
        {"pseudonym": antrag.stimmregister.get(mitglied=autor).pseudonym.hex, "bewerbung": b.pk}
    ]
