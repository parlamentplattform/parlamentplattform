"""D-L6g und E2: Nach dem Ende der Vertretung (§ 7 Abs 10 lit f Z 8) trägt die Verwaltung Abstimmungen nach
öffentlichen Quellen nach, und die frühere Mandatsperson kann eine freiwillige Begründung daneben stellen.
Dazu das Register als JSON mit Sitzungen, Punkten und Nachträgen."""

import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from mandatare.models import FreiwilligeBegruendung, Mandat, Rechenschaft
from mandatare.sitzung import meldung_abgeben, sitzung_beginnen
from mandatare.test_mandatare import mandat_anlegen
from mandatare.test_sitzung_modelle import sitzungstag
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

VERWALTUNG = reverse("mandatare:verwaltung_aktion")
AKTION = reverse("mandatare:mein_aktion")


@pytest.fixture
def admin(client):
    a = mitglied_anlegen("admin")
    a.ist_admin = True
    a.is_staff = True
    a.save()
    client.force_login(a)
    return a


@pytest.fixture
def ausgeschieden():
    """Ein Mandat, dessen Vertretung vor 40 Tagen endete — die Nachfrist ist lange vorbei."""
    mandat = mandat_anlegen(mitglied_anlegen("anna"))
    Mandat.objects.filter(pk=mandat.pk).update(vertretung_beendet_am=timezone.localdate() - timedelta(days=40))
    mandat.refresh_from_db()
    return mandat


def nachtrag(client, mandat, **extra):
    daten = {
        "aktion": "rechenschaft_nachtragen",
        "mandat": mandat.pk,
        "sitzung_am": (timezone.localdate() - timedelta(days=3)).isoformat(),
        "gegenstand": "Budget 2027",
        "stimme": "dagegen",
        "quelle": "https://www.gemeinde.example.org/protokoll-2027",
        **extra,
    }
    return client.post(VERWALTUNG, daten, follow=True)


def test_verwaltung_traegt_nach(client, admin, ausgeschieden):
    antwort = nachtrag(client, ausgeschieden)
    assert "Nachgetragen" in antwort.content.decode()
    eintrag = Rechenschaft.objects.get()
    assert eintrag.nachgetragen and eintrag.begruendung == "" and eintrag.quelle.startswith("https://")
    ereignis = AuditEintrag.objects.get(ereignis__typ="rechenschaft_nachgetragen").ereignis
    assert ereignis["rechenschaft"] == eintrag.pk and ereignis["durch"] == "verwaltung" and "quelle" not in ereignis
    register = client.get(reverse("mandatare:rechenschaft_mandat", args=[ausgeschieden.pk])).content.decode()
    assert "nachgetragen von der Verwaltung am" in register and "Begründung nicht mehr geschuldet" in register


@pytest.mark.parametrize(
    "extra",
    [
        {"quelle": ""},
        {"stimme": "vielleicht"},
        {"sitzung_am": "kaputt"},
        {"sitzung_am": (timezone.localdate() + timedelta(days=1)).isoformat()},  # Zukunft
        {"sitzung_am": (timezone.localdate() - timedelta(days=41)).isoformat()},  # vor dem Ende: die Person schuldet selbst
        {"sitzung_am": (timezone.localdate() - timedelta(days=40)).isoformat()},  # der Endtag zählt noch zur Pflicht
        {"antrag": "999999"},
    ],
)
def test_nachtrag_pruefungen(client, admin, ausgeschieden, extra):
    nachtrag(client, ausgeschieden, **extra)
    assert not Rechenschaft.objects.exists()


def test_nachtrag_nur_nach_dem_ende_der_vertretung(client, admin):
    aktiv = mandat_anlegen(mitglied_anlegen("bernd"))
    antwort = nachtrag(client, aktiv)
    assert "nur nach dem Ende der Vertretung" in antwort.content.decode() and not Rechenschaft.objects.exists()


def test_nachtrag_nicht_nach_dem_mandatsende(client, admin, ausgeschieden):
    Mandat.objects.filter(pk=ausgeschieden.pk).update(beendet=timezone.localdate() - timedelta(days=5))
    nachtrag(client, ausgeschieden)  # Sitzung vor 3 Tagen, Mandat endete vor 5
    assert not Rechenschaft.objects.exists()


def test_nachtrag_nur_fuer_die_verwaltung(client, ausgeschieden):
    client.force_login(mitglied_anlegen("cora"))
    assert nachtrag(client, ausgeschieden).status_code == 403
    assert not Rechenschaft.objects.exists()


def test_freiwillige_begruendung_nach_der_nachfrist(client, admin, ausgeschieden):
    nachtrag(client, ausgeschieden)
    eintrag = Rechenschaft.objects.get()
    client.force_login(ausgeschieden.mitglied)
    html = client.get(reverse("mandatare:mein")).content.decode()
    assert 'value="freiwillige_begruendung"' in html and "Nachtrag der Verwaltung" in html
    client.post(AKTION, {"aktion": "freiwillige_begruendung", "mandat": ausgeschieden.pk, "rechenschaft": eintrag.pk,
                         "text": "Ich habe dagegen gestimmt, weil der Beschluss der Mitglieder anders lautete."})
    f = FreiwilligeBegruendung.objects.get()
    assert f.rechenschaft == eintrag
    eintrag.refresh_from_db()
    assert eintrag.begruendung == ""  # der Eintrag selbst bleibt
    antwort = client.post(AKTION, {"aktion": "freiwillige_begruendung", "mandat": ausgeschieden.pk,
                                   "rechenschaft": eintrag.pk, "text": "zweiter Versuch"}, follow=True)
    assert "schon eine freiwillige Begründung" in antwort.content.decode() and FreiwilligeBegruendung.objects.count() == 1
    register = client.get(reverse("mandatare:rechenschaft_mandat", args=[ausgeschieden.pk])).content.decode()
    assert "Freiwillige Begründung vom" in register and "anders lautete" in register
    assert AuditEintrag.objects.filter(ereignis__typ="freiwillige_begruendung").count() == 1


def test_freiwillige_begruendung_nur_zu_nachtraegen_des_eigenen_mandats(client, ausgeschieden):
    eigener = Rechenschaft.objects.create(
        mandat=ausgeschieden, gegenstand="Eigener Eintrag", sitzung_am=timezone.localdate() - timedelta(days=50),
        stimme="dafuer", begruendung="selbst",
    )
    fremd_mandat = mandat_anlegen(mitglied_anlegen("dora"))
    fremd = Rechenschaft.objects.create(
        mandat=fremd_mandat, gegenstand="Fremd", sitzung_am=timezone.localdate(), stimme="dafuer",
        begruendung="", nachgetragen_am=timezone.now(), quelle="x",
    )
    client.force_login(ausgeschieden.mitglied)
    for r in (eigener, fremd):
        client.post(AKTION, {"aktion": "freiwillige_begruendung", "mandat": ausgeschieden.pk, "rechenschaft": r.pk, "text": "x"})
    assert not FreiwilligeBegruendung.objects.exists()


def test_aktives_mandat_hat_keine_freiwillige_begruendung(client):
    m = mitglied_anlegen("emil")
    mandat = mandat_anlegen(m)
    client.force_login(m)
    assert 'value="freiwillige_begruendung"' not in client.get(reverse("mandatare:mein")).content.decode()
    client.post(AKTION, {"aktion": "freiwillige_begruendung", "mandat": mandat.pk, "rechenschaft": 1, "text": "x"})
    assert not FreiwilligeBegruendung.objects.exists()


def test_register_json_mit_sitzungen_und_nachtraegen(client, admin, ausgeschieden):
    nachtrag(client, ausgeschieden)
    aktiv = mandat_anlegen(mitglied_anlegen("bernd"), ebene="land", gebiet="Oberösterreich")
    sitzung = sitzung_beginnen(aktiv, sitzungstag(aktiv), stream="https://tv.example.org", punkte=["Budget"])
    alt = meldung_abgeben(sitzung, "dafür", sitzung.punkte.get(), "dafuer")
    meldung_abgeben(sitzung, "doch dagegen", sitzung.punkte.get(), "dagegen", True, berichtigt=alt)
    daten = client.get(reverse("mandatare:rechenschaft_json")).json()
    eintrag = daten["eintraege"][0]
    assert eintrag["lage"] == "nachgetragen" and eintrag["quelle"].startswith("https://")
    assert eintrag["begruendung"] == "" and eintrag["freiwillige_begruendung"] is None and eintrag["sitzung"] is None
    s = daten["sitzungen"][0]
    assert s["id"] == sitzung.pk and s["punkte"] == [{"nummer": 1, "titel": "Budget", "antrag": None}]
    assert [m["stimme"] for m in s["meldungen"]] == ["dafuer", "dagegen"]
    assert s["meldungen"][1]["berichtigt"] == alt.pk and s["meldungen"][0]["punkt"] == 1
    assert client.get(reverse("mandatare:rechenschaft_json") + "?ebene=gemeinde").json()["sitzungen"] == []


def test_datenexport_nennt_sitzungen(client):
    m = mitglied_anlegen("anna")
    mandat = mandat_anlegen(m)
    sitzung = sitzung_beginnen(mandat, sitzungstag(mandat), punkte=["Budget"])
    meldung_abgeben(sitzung, "Meldung", sitzung.punkte.get(), "dafuer")
    client.force_login(m)
    daten = json.loads(client.get(reverse("mitglieder:profil_export")).content)
    block = daten["mandate"][0]["sitzungen"][0]
    assert block["punkte"][0]["titel"] == "Budget" and block["meldungen"][0]["text"] == "Meldung"


def test_nachtrag_nicht_mit_kandidatur(client, admin, ausgeschieden, ordnung):  # noqa: F811
    """Befund 16: Eine Kandidatur oder Vertrauensfrage ist kein Beschluss der Plattform zu einer Abstimmung."""
    from verfahren.models import antrag_einbringen

    kandidatur = antrag_einbringen(ausgeschieden.mitglied, "Liste", "Reihung.", "", ordnung, art="mandat")
    nachtrag(client, ausgeschieden, antrag=kandidatur.pk)
    assert not Rechenschaft.objects.exists()


def test_freiwillige_begruendung_bleibt_nach_aufhebung(client, admin, ausgeschieden):
    """Befund 13: Hebt das Parteischiedsgericht das Ergebnis auf, bleibt der Nachtrag — und die Person kann
    die Begründung trotzdem daneben stellen."""
    nachtrag(client, ausgeschieden)
    eintrag = Rechenschaft.objects.get()
    Mandat.objects.filter(pk=ausgeschieden.pk).update(vertretung_beendet_am=None)
    client.force_login(ausgeschieden.mitglied)
    assert 'value="freiwillige_begruendung"' in client.get(reverse("mandatare:mein")).content.decode()
    client.post(AKTION, {"aktion": "freiwillige_begruendung", "mandat": ausgeschieden.pk, "rechenschaft": eintrag.pk, "text": "Begründung"})
    assert FreiwilligeBegruendung.objects.filter(rechenschaft=eintrag).exists()
