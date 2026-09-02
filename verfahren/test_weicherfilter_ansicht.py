"""P5 — der WeicherFilter im Parlament (FB-B1–B6): Favoriten zuerst, neun Regler mit Wortlaut,
Live-Vorschau, Konfigurationen (anlegen, wählen, umbenennen, löschen), Leiste und Overlay,
offene Reihung mit „Warum hier?“."""

import pytest
from django.apps import apps
from django.urls import reverse

from verfahren.models import FilterProfil, Kategorie, KategorieAbo, antrag_einbringen, stimme_abgeben
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db

REGLER_WORTLAUT = [
    "Mehr wie das, wofür ich gestimmt habe",
    "Mehr wie das, wogegen ich gestimmt habe",
    "Mehr wie das, was ich unterstützt habe",
    "Interessantes außerhalb meiner Favoriten",
    "Mehr Unterstützungsanträge",
    "Mehr Abstimmungen",
    "Mehr chronologisch (Neues zuerst)",
    "Nur noch kurz online",
    "Wenig fehlt",
]


def _feld(client):
    return client.get("/parlament/").content.decode().split('id="feld-filter"')[1].split("</section>")[0]


def _lage(ordnung):  # noqa: F811
    """Zwei laufende Verfahren: eines in Unterstützung, eines in Abstimmung."""
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    unterstuetzung = antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung)
    abstimmung = in_abstimmung_bringen(
        antrag_einbringen(leute[0], "Zweiter Antrag zur Abstimmung", "Wortlaut.", "", ordnung),
        leute[1:],
    )
    return leute, unterstuetzung, abstimmung


def test_voreinstellung_bleibt_streng_neutral_mit_neun_reglern(client, ordnung):  # noqa: F811
    leute, *_ = _lage(ordnung)
    client.force_login(leute[2])
    feld = _feld(client)
    assert "Voreinstellung: neutral" in feld
    assert 'id="filter-leiste"' in feld and "r_chronologisch" in feld  # Leiste und Regler stehen bereit
    assert "punkte" not in feld and "Warum hier?" not in feld  # neutral: keine Rechnung
    assert 'class="gruppe"' in feld  # neutral: Gruppen nach Phase
    lagen = [feld.index(wort) for wort in REGLER_WORTLAUT]
    assert lagen == sorted(lagen), "neun Regler in der Reihenfolge des Fahrtenbuchs"
    assert feld.count('type="range"') == 9 and 'aria-valuetext="0 von 100"' in feld


def test_favoriten_zuerst_in_der_voreinstellung_und_abschaltbar(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    energie = Kategorie.objects.create(slug="energie", name="Energie")
    alt = antrag_einbringen(anna, "Älterer Antrag ohne Thema", "W.", "", ordnung)
    neu = antrag_einbringen(anna, "Energie-Antrag", "W.", "", ordnung)
    neu.kategorien.add(energie)
    type(alt).objects.filter(pk=alt.pk).update(phase_beginn=alt.phase_beginn.replace(year=2025))
    KategorieAbo.objects.create(kategorie=energie, mitglied=anna)
    client.force_login(anna)
    feld = _feld(client)
    assert feld.index("Energie-Antrag") < feld.index("Älterer Antrag ohne Thema")  # Favorit zuerst
    assert "★ Favoriten zuerst" in feld and 'aria-pressed="true"' in feld
    antwort = client.post(reverse("verfahren:filter_favoriten"), {"weiter": "/parlament/"})
    assert antwort.url == "/parlament/"
    anna.refresh_from_db()
    assert anna.favoriten_zuerst is False
    feld = _feld(client)
    assert 'aria-pressed="false"' in feld
    assert feld.index("Älterer Antrag ohne Thema") < feld.index("Energie-Antrag")  # reine Grundordnung


def test_regler_anwenden_reiht_offen_und_nachrechenbar(client, ordnung):  # noqa: F811
    leute, unterstuetzung, abstimmung = _lage(ordnung)
    client.force_login(leute[2])
    antwort = client.post(
        reverse("verfahren:filter_anwenden"),
        {"r_unterstuetzungsphase": "80", "favoriten_zuerst": "1", "weiter": "/parlament/"},
    )
    assert antwort.url == "/parlament/"
    profil = leute[2].filterprofile.get()
    assert profil.aktiv and profil.regler["unterstuetzungsphase"] == 80 and profil.favoriten_zuerst
    feld = _feld(client)
    assert "Profil:" in feld and 'class="gruppe"' not in feld  # aktives Profil: EINE Liste
    assert feld.index(unterstuetzung.titel) < feld.index(abstimmung.titel)
    assert "Warum hier?" in feld and "Mehr Unterstützungsanträge <b>80</b>" in feld


def test_wofuer_und_wogegen_gestimmt_sind_getrennte_regler(client, ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    ich = leute[2]
    klima, verkehr = Kategorie.objects.create(slug="klima", name="Klima"), Kategorie.objects.create(slug="verkehr", name="Verkehr")
    dafuer = in_abstimmung_bringen(antrag_einbringen(leute[0], "Klimaschutz jetzt", "W.", "", ordnung), leute[1:])
    dagegen = in_abstimmung_bringen(antrag_einbringen(leute[0], "Mehr Straßen", "W.", "", ordnung), leute[1:])
    dafuer.kategorien.add(klima)
    dagegen.kategorien.add(verkehr)
    stimme_abgeben(dafuer, ich, "ja")
    stimme_abgeben(dagegen, ich, "nein")
    neu_klima = antrag_einbringen(leute[0], "Neuer Klima-Antrag", "W.", "", ordnung)
    neu_verkehr = antrag_einbringen(leute[0], "Neuer Verkehrs-Antrag", "W.", "", ordnung)
    neu_klima.kategorien.add(klima)
    neu_verkehr.kategorien.add(verkehr)
    client.force_login(ich)
    client.post(reverse("verfahren:filter_anwenden"), {"r_ja": "100"})
    feld = _feld(client)
    assert feld.index("Neuer Klima-Antrag") < feld.index("Neuer Verkehrs-Antrag")
    client.post(reverse("verfahren:filter_anwenden"), {"r_nein": "100"})
    feld = _feld(client)
    assert feld.index("Neuer Verkehrs-Antrag") < feld.index("Neuer Klima-Antrag")


def test_live_vorschau_reiht_ohne_zu_speichern(client, ordnung):  # noqa: F811
    leute, unterstuetzung, abstimmung = _lage(ordnung)
    client.force_login(leute[2])
    antwort = client.post(reverse("verfahren:filter_vorschau"), {"r_unterstuetzungsphase": "90"}, HTTP_HX_REQUEST="true")
    assert antwort.status_code == 200
    liste = antwort.content.decode()
    assert liste.lstrip().startswith('<div id="filter-liste">') and 'id="feld-filter"' not in liste
    assert liste.index(unterstuetzung.titel) < liste.index(abstimmung.titel)
    assert "Warum hier?" in liste
    assert not leute[2].filterprofile.exists()  # nichts gespeichert
    assert client.get(reverse("verfahren:filter_vorschau")).status_code == 405


def test_neutral_chip_stellt_die_grundordnung_wieder_her(client, ordnung):  # noqa: F811
    leute, unterstuetzung, abstimmung = _lage(ordnung)
    client.force_login(leute[2])
    client.post(reverse("verfahren:filter_anwenden"), {"r_unterstuetzungsphase": "80"})
    client.post(reverse("verfahren:filter_neutral"), {})
    feld = _feld(client)
    assert "Voreinstellung: neutral" in feld
    assert feld.index(abstimmung.titel) < feld.index(unterstuetzung.titel)  # Grundordnung


def test_hoechstens_fuenf_konfigurationen(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    client.force_login(anna)
    for i in range(5):
        client.post(
            reverse("verfahren:filter_anwenden"),
            {"r_chronologisch": "10", "als_neues": "1", "profilname": f"Profil {i}"},
        )
    assert anna.filterprofile.count() == 5
    feld = _feld(client)
    assert "5 von 5 — eine löschen oder überschreiben" in feld and "Als neue Konfiguration speichern" not in feld
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


def test_konfiguration_waehlen_umbenennen_und_loeschen_mit_rueckfrage(client, ordnung):  # noqa: F811
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
    feld = _feld(client)
    assert "Konfiguration „Abstimmen“ löschen?" in feld and "Ja, löschen" in feld  # Inline-Rückfrage
    assert 'class="umbenennen"' in feld
    client.post(reverse("verfahren:filter_umbenennen", args=[erst.pk]), {"name": "Abend"})
    erst.refresh_from_db()
    assert erst.name == "Abend"
    client.post(reverse("verfahren:filter_umbenennen", args=[erst.pk]), {"name": "Neues"})  # schon vergeben
    erst.refresh_from_db()
    assert erst.name == "Abend"
    client.post(reverse("verfahren:filter_loeschen", args=[erst.pk]), {})
    assert not anna.filterprofile.filter(name="Abend").exists()


def test_fremde_konfigurationen_sind_unantastbar(client, ordnung):  # noqa: F811
    anna, bernd = mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    profil = FilterProfil.objects.create(mitglied=anna, name="Annas", regler={"abstimmungen": 10})
    client.force_login(bernd)
    assert client.post(reverse("verfahren:filter_waehlen", args=[profil.pk]), {}).status_code == 404
    assert client.post(reverse("verfahren:filter_loeschen", args=[profil.pk]), {}).status_code == 404
    assert client.post(reverse("verfahren:filter_umbenennen", args=[profil.pk]), {"name": "X"}).status_code == 404


def test_gaeste_sehen_neutral_ohne_leiste_und_schalter(client, ordnung):  # noqa: F811
    _lage(ordnung)
    feld = _feld(client)
    assert 'id="filter-leiste"' not in feld and "Favoriten zuerst" not in feld
    assert "Voreinstellung: neutral" in feld and "Warum hier?" not in feld
    assert 'class="fz' in feld and ">Anmelden</a>" in feld  # Zeilen mit Anmelde-Hinweis statt Stimmknöpfen


def test_leiste_und_overlay_markup(client, ordnung):  # noqa: F811
    leute, *_ = _lage(ordnung)
    client.force_login(leute[2])
    feld = _feld(client)
    assert 'class="pfeil" x-cloak' in feld and 'aria-controls="filter-leiste"' in feld
    assert 'class="griff" x-cloak' in feld
    assert 'role="dialog" aria-modal="false"' in feld
    assert 'hx-post="/filter/vorschau/"' in feld and "hx-trigger=" in feld and 'hx-target="#filter-liste"' in feld
    assert 'name="favoriten_zuerst"' in feld and 'role="switch"' in feld
    assert 'href="/parameter/#weicherfilter"' in feld and "Regel v2 nachlesen" in feld
    assert 'x-data="klappmenue"' in feld and "oninput" not in feld
    assert "Zurücksetzen" in feld and "Als neue Konfiguration speichern" in feld


def test_zeile_mit_direkt_handlung_je_phase(client, ordnung):  # noqa: F811
    leute, unterstuetzung, abstimmung = _lage(ordnung)
    client.force_login(leute[2])
    feld = _feld(client)
    assert f'action="/antrag/{unterstuetzung.pk}/unterstuetzen/"' in feld and ">Unterstützen<" in feld
    assert 'class="abstimmen"' in feld and 'name="stimme" value="ja"' in feld and "Abstimmen ▸" in feld
    assert 'class="badge b-abstimmung"' in feld and 'class="badge b-unterstuetzung"' in feld
    stimme_abgeben(abstimmung, leute[2], "ja")
    feld = _feld(client)
    assert "Ja ✓ ▸" in feld  # die eigene Stimme steht am Knopf


def test_parameterseite_erklaert_regel_v2(client):
    seite = client.get(reverse("parameter:liste")).content.decode()
    assert 'id="weicherfilter"' in seite and "VERSION 2" in seite
    assert all(wort in seite for wort in REGLER_WORTLAUT)


def test_datenmigration_gestimmt_wird_ja_und_nein():
    import importlib

    modul = importlib.import_module("verfahren.migrations.0011_filterprofil_favoriten_zuerst_regel_v2")
    anna = mitglied_anlegen("anna")
    alt = FilterProfil.objects.create(mitglied=anna, name="Alt", regler={"gestimmt": 40, "ablaufend": 10})
    modul.regler_nach_v2(apps, None)
    alt.refresh_from_db()
    assert alt.regler == {"ablaufend": 10, "ja": 40, "nein": 40}
    modul.regler_nach_v2(apps, None)  # idempotent
    alt.refresh_from_db()
    assert alt.regler == {"ablaufend": 10, "ja": 40, "nein": 40}
