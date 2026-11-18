"""Gesamtprüfung, zweite Runde (Paket B1): Meldungen erreichen die Verwaltung auf einem sichtbaren
Weg, Meldende sehen den Stand auch im Sitzungs-Chat, die Matrix nennt die Adresse, das öffentliche
Audit stellt keinen folgenlos gemeldeten Beitrag aus (GP-014); der Sitzungs-Chat weist zu lange
Beiträge ab statt sie still zu kürzen (GP-083)."""

import pytest
from django.urls import reverse

from mandatare.sitzung import sitzung_beenden, sitzung_beginnen
from mandatare.test_mandatare import mandat_anlegen
from mandatare.test_sitzung_modelle import sitzungstag
from verfahren import chat as chatkern
from verfahren.models import Meldung
from verfahren.test_views_aktionen import mitglied_anlegen

pytestmark = pytest.mark.django_db


def _verwaltung(name="vera"):
    m = mitglied_anlegen(name)
    m.ist_admin = True
    m.save()
    return m


def _register(schluessel, wert):
    from parameter.models import Parameter

    Parameter.objects.update_or_create(
        schluessel=schluessel, defaults={"wert": str(wert), "beschreibung": "Test", "quelle": "Test"}
    )


@pytest.fixture
def lage():
    anna, bernd = mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    mandat = mandat_anlegen(anna)
    sitzung = sitzung_beginnen(mandat, sitzungstag(mandat))
    return mandat, sitzung, anna, bernd


def _live(client, mandat, sitzung):
    return client.get(reverse("mandatare:live", args=[mandat.pk]) + f"?sitzung={sitzung.pk}").content.decode()


# ── GP-014 (a): Verweis aus der Verwaltung auf die Meldeliste ─────────────────────────────


def test_gp014_verwaltung_verweist_auf_die_meldeliste_mit_der_zahl_offener_meldungen(client, lage):
    mandat, sitzung, anna, bernd = lage
    vera = _verwaltung()
    eins = chatkern.sitzung_beitrag_schreiben(sitzung, anna, "Erster Beitrag.")
    zwei = chatkern.sitzung_beitrag_schreiben(sitzung, anna, "Zweiter Beitrag.")
    Meldung.objects.create(kommentar=eins, mitglied=bernd, grund="recht")
    Meldung.objects.create(kommentar=zwei, mitglied=bernd, grund="recht")
    erledigt = Meldung.objects.create(kommentar=zwei, mitglied=vera, grund="recht")
    Meldung.objects.filter(pk=erledigt.pk).update(erledigt_am=sitzung.beginn, entscheidung="keine_massnahme")

    client.force_login(vera)
    inhalt = client.get(reverse("mitglieder:verwaltung")).content.decode()
    assert f'href="{reverse("verfahren:meldungen")}"' in inhalt
    assert "Gemeldete Beiträge (2 offen)" in inhalt

    # Ohne Verwaltungsrechte: kein Zugang zur Seite und damit auch kein Verweis
    client.force_login(bernd)
    antwort = client.get(reverse("mitglieder:verwaltung"))
    assert antwort.status_code == 403
    assert reverse("verfahren:meldungen") not in antwort.content.decode()


# ── GP-014 (b): Stand der eigenen Meldung am Beitrag im Sitzungs-Chat ─────────────────────


def test_gp014_meldende_sehen_den_stand_am_beitrag_im_sitzungschat_und_im_protokoll(client, lage):
    mandat, sitzung, anna, bernd = lage
    vera = _verwaltung()
    beitrag = chatkern.sitzung_beitrag_schreiben(sitzung, anna, "Eine fragwürdige Behauptung.")
    client.force_login(bernd)
    client.post(
        reverse("mandatare:live_beitrag_aktion", args=[mandat.pk, sitzung.pk, beitrag.pk]),
        {"aktion": "melden", "grund": "recht"},
    )
    assert Meldung.objects.filter(kommentar=beitrag, mitglied=bernd).exists()
    seite = _live(client, mandat, sitzung)
    assert "Ihre Meldung vom" in seite and "liegt der Verwaltung vor" in seite
    # Wer gemeldet hat, bekommt kein zweites Meldeformular für denselben Beitrag
    block = seite.split(f'id="k-{beitrag.pk}"', 1)[1].split("</article>", 1)[0]
    assert 'value="melden"' not in block
    # Andere sehen den Stand fremder Meldungen nicht
    client.force_login(anna)
    assert "Ihre Meldung vom" not in _live(client, mandat, sitzung)

    client.force_login(vera)
    client.post(reverse("verfahren:meldung_entscheiden", args=[beitrag.pk]), {"entscheidung": "keine_massnahme"})
    sitzung_beenden(sitzung)
    client.force_login(bernd)
    protokoll = _live(client, mandat, sitzung)
    assert "Ihre Meldung vom" in protokoll and "entschieden: keine Maßnahme" in protokoll


def test_gp014_stand_ausgeblendet_im_sitzungschat(client, lage):
    mandat, sitzung, anna, bernd = lage
    vera = _verwaltung()
    beitrag = chatkern.sitzung_beitrag_schreiben(sitzung, anna, "Beleidigender Satz.")
    Meldung.objects.create(kommentar=beitrag, mitglied=bernd, grund="beleidigung")
    client.force_login(vera)
    client.post(
        reverse("verfahren:meldung_entscheiden", args=[beitrag.pk]),
        {"entscheidung": "ausblenden", "grund": "Herabwürdigung"},
    )
    client.force_login(bernd)
    seite = _live(client, mandat, sitzung)
    assert "entschieden: ausgeblendet" in seite
    assert "von der Verwaltung ausgeblendet: Herabwürdigung" in seite


# ── GP-014 (c): Die Matrix nennt die Adresse der Meldeliste ───────────────────────────────


def test_gp014_die_verwaltungszeile_der_matrix_fuehrt_zur_meldeliste(client):
    from plattform_core.rollen import GRUPPEN, alle_rollen

    verwaltung = next(r for r in alle_rollen(GRUPPEN) if r.schluessel == "verwaltung")
    zeile = next(f for f in verwaltung.faehigkeiten if str(f.titel).startswith("Gemeldete Beiträge"))
    assert zeile.urlname == "verfahren:meldungen"
    assert f'href="{reverse("verfahren:meldungen")}"' in client.get(reverse("verfahren:rollen")).content.decode()


# ── GP-014 (d): Das öffentliche Audit stellt folgenlos gemeldete Beiträge nicht aus ──────


def test_gp014_meldung_ohne_massnahme_nennt_oeffentlich_keinen_beitrag():
    from verfahren.audit_oeffentlich import MASKE, ereignis_oeffentlich

    sichtbar, geschwaerzt = ereignis_oeffentlich(
        {"typ": "meldung_ohne_massnahme", "beitrag": 9, "meldungen": 2, "antrag": 3}
    )
    assert geschwaerzt and sichtbar["beitrag"] == MASKE
    assert sichtbar["antrag"] == 3 and sichtbar["meldungen"] == 2
    # Das Ausblenden ist öffentlich: Der Vermerk steht ohnehin am Beitrag
    sichtbar, _ = ereignis_oeffentlich({"typ": "beitrag_ausgeblendet", "beitrag": 9, "meldungen": 1, "antrag": 3})
    assert sichtbar["beitrag"] == 9
