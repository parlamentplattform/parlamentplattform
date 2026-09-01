"""P5 — der WeicherFilter im Parlament: Profile, Regler, offene Reihung."""

import pytest
from django.urls import reverse

from verfahren.models import FilterProfil, antrag_einbringen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def _lage(ordnung):  # noqa: F811
    """Zwei laufende Verfahren: eines in Unterstützung, eines in Abstimmung."""
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    unterstuetzung = antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung)
    abstimmung = in_abstimmung_bringen(
        antrag_einbringen(leute[0], "Zweiter Antrag zur Abstimmung", "Wortlaut.", "", ordnung),
        leute[1:],
    )
    return leute, unterstuetzung, abstimmung


def test_voreinstellung_bleibt_streng_neutral(client, ordnung):  # noqa: F811
    leute, *_ = _lage(ordnung)
    client.force_login(leute[2])
    inhalt = client.get("/parlament/").content.decode()
    assert "Voreinstellung: neutral" in inhalt
    assert "filter-leiste" in inhalt and "r_chronologisch" in inhalt  # Regler stehen bereit
    assert "punkte" not in inhalt.split('id="feld-filter"')[1].split("</section>")[0]


def test_regler_anwenden_reiht_offen_und_nachrechenbar(client, ordnung):  # noqa: F811
    leute, unterstuetzung, abstimmung = _lage(ordnung)
    client.force_login(leute[2])
    antwort = client.post(
        reverse("verfahren:filter_anwenden"),
        {"r_unterstuetzungsphase": "80", "weiter": "/parlament/"},
    )
    assert antwort.url == "/parlament/"
    profil = leute[2].filterprofile.get()
    assert profil.aktiv and profil.regler["unterstuetzungsphase"] == 80

    feld = client.get("/parlament/").content.decode().split('id="feld-filter"')[1].split("</section>")[0]
    assert "Profil:" in feld
    # Der Unterstützungs-Antrag steht jetzt VOR der Abstimmung — mit offener Rechnung.
    assert feld.index(unterstuetzung.titel) < feld.index(abstimmung.titel)
    assert "80&nbsp;P" in feld and "Mehr Unterstützungsphase 80" in feld


def test_neutral_chip_stellt_die_grundordnung_wieder_her(client, ordnung):  # noqa: F811
    leute, unterstuetzung, abstimmung = _lage(ordnung)
    client.force_login(leute[2])
    client.post(reverse("verfahren:filter_anwenden"), {"r_unterstuetzungsphase": "80"})
    client.post(reverse("verfahren:filter_neutral"), {})
    feld = client.get("/parlament/").content.decode().split('id="feld-filter"')[1].split("</section>")[0]
    assert "Voreinstellung: neutral" in feld
    assert feld.index(abstimmung.titel) < feld.index(unterstuetzung.titel)  # Grundordnung


def test_hoechstens_fuenf_profile(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    client.force_login(anna)
    for i in range(5):
        client.post(
            reverse("verfahren:filter_anwenden"),
            {"r_chronologisch": "10", "als_neues": "1", "profilname": f"Profil {i}"},
        )
    assert anna.filterprofile.count() == 5
    client.post(
        reverse("verfahren:filter_anwenden"),
        {"r_chronologisch": "10", "als_neues": "1", "profilname": "Zuviel"},
    )
    assert anna.filterprofile.count() == 5  # abgelehnt
    # Überschreiben eines bestehenden Namens bleibt erlaubt:
    client.post(
        reverse("verfahren:filter_anwenden"),
        {"r_chronologisch": "90", "als_neues": "1", "profilname": "Profil 0"},
    )
    assert anna.filterprofile.get(name="Profil 0").regler["chronologisch"] == 90


def test_profil_waehlen_und_loeschen(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    client.force_login(anna)
    client.post(reverse("verfahren:filter_anwenden"),
                {"r_abstimmungen": "50", "als_neues": "1", "profilname": "Abstimmen"})
    client.post(reverse("verfahren:filter_anwenden"),
                {"r_chronologisch": "50", "als_neues": "1", "profilname": "Neues"})
    erst = anna.filterprofile.get(name="Abstimmen")
    assert not erst.aktiv  # das zweite Profil hat übernommen
    client.post(reverse("verfahren:filter_waehlen", args=[erst.pk]), {})
    erst.refresh_from_db()
    assert erst.aktiv
    client.post(reverse("verfahren:filter_loeschen", args=[erst.pk]), {})
    assert not anna.filterprofile.filter(name="Abstimmen").exists()


def test_fremde_profile_sind_unantastbar(client, ordnung):  # noqa: F811
    anna, bernd = mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    profil = FilterProfil.objects.create(mitglied=anna, name="Annas", regler={"abstimmungen": 10})
    client.force_login(bernd)
    assert client.post(reverse("verfahren:filter_waehlen", args=[profil.pk]), {}).status_code == 404
    assert client.post(reverse("verfahren:filter_loeschen", args=[profil.pk]), {}).status_code == 404


def test_gaeste_sehen_keine_leiste(client, ordnung):  # noqa: F811
    _lage(ordnung)
    inhalt = client.get("/parlament/").content.decode()
    assert 'class="filter-leiste"' not in inhalt
    assert "Voreinstellung: neutral" in inhalt
