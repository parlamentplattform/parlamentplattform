"""Neue regionale Vorgänge verwenden denselben Hauptwohnsitzkreis auf jedem Handlungsweg."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import Entwurf
from mitglieder.models import Gemeinde, Mitglied, Wohnsitzart
from mitglieder.post import region_empfaenger
from parameter.models import NEBENWOHNSITZ_BESCHREIBUNG_ALT, Parameter, erstbestand_sicherstellen
from verfahren.einbringwahl import direkt_unterstuetzen
from verfahren.models import (
    Antrag,
    BewerbungsFehler,
    StimmabgabeFehler,
    antrag_einbringen,
    bewerbung_einreichen,
    bewerbung_zustimmen,
    stimme_abgeben,
)
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)
from verify.nachrechnen import nachrechnen

pytestmark = pytest.mark.django_db


@pytest.fixture
def menschen():
    ort = Gemeinde.objects.create(kennziffer="40510", name="Gleichort", bezirk="Eferding", bundesland="oberoesterreich")
    fremdort = Gemeinde.objects.create(kennziffer="41419", name="Gleichort", bezirk="Schärding", bundesland="oberoesterreich")
    daten = {}
    for name, gemeinde in (("autor", ort), ("ort", ort), ("fremd", fremdort)):
        m = mitglied_anlegen(name, tage=800)
        m.wohnsitz, m.wohnsitz_art = gemeinde, Wohnsitzart.OESTERREICH
        m.nebenwohnsitz = ort if name == "fremd" else None
        m.save(update_fields=["wohnsitz", "wohnsitz_art", "nebenwohnsitz"])
        daten[name] = m
    Mitglied.objects.create_user("gemeindekonto", parteikonto=False, wohnsitz=ort, wohnsitz_art="oesterreich")
    return daten, ort, fremdort


def _einbringen(client, autor, art="sache"):
    client.force_login(autor)
    r = client.post(reverse("verfahren:einbringen"), {**ANTRAG, "ebene": "gemeinde", "art": art, "trotzdem": "1"})
    assert r.status_code == 302
    return Antrag.objects.latest("pk")


def _abstimmung(a, stimmberechtigte=None):
    a.phase = "abstimmung"
    a.phase_beginn = timezone.now()
    a.stimmberechtigung_stichtag = timezone.localdate(a.phase_beginn)
    a.stimmberechtigte_anzahl = stimmberechtigte
    a.save(update_fields=["phase", "phase_beginn", "stimmberechtigung_stichtag", "stimmberechtigte_anzahl"])


def test_hausnummer_oder_nebenwohnsitz_sind_kein_ersatz_fuer_eindeutige_zuordnung(client, menschen, ordnung):  # noqa: F811
    leute, ort, fremdort = menschen
    a = _einbringen(client, leute["autor"])
    assert a.teilnahmegebiet["kennung"] == "gemeinde:40510"
    assert a.teilnehmerkreis_am == a.eingebracht_am
    assert set(a.oertlicher_kreis.values_list("mitglied_id", flat=True)) == {leute["autor"].pk, leute["ort"].pk}
    client.force_login(leute["fremd"])
    seite = client.get(reverse("verfahren:parlament"))
    zeile = next(z for z in seite.context["region_zeilen"] if z["ebene"] == "gemeinde")
    assert not zeile["kacheln"]
    Mitglied.objects.filter(pk=leute["ort"].pk).update(wohnsitz=fremdort)
    Mitglied.objects.filter(pk=leute["fremd"].pk).update(wohnsitz=ort)
    url = reverse("verfahren:unterstuetzen", args=[a.pk])
    client.force_login(leute["fremd"])
    assert client.post(url).status_code == 403
    assert direkt_unterstuetzen(leute["fremd"], a.pk) is None
    client.force_login(leute["ort"])
    assert client.post(url).status_code == 302
    assert list(a.unterstuetzungen.values_list("mitglied_id", flat=True)) == [leute["ort"].pk]
    _abstimmung(a, 2)
    assert stimme_abgeben(a, leute["ort"], "ja").stimme == "ja"
    with pytest.raises(StimmabgabeFehler):
        stimme_abgeben(a, leute["fremd"], "ja")
    client.force_login(leute["fremd"])
    assert client.post(reverse("verfahren:abstimmen", args=[a.pk]), {"stimme": "ja"}).status_code == 403
    assert a.stimmregister.count() == 1


@pytest.mark.parametrize("wohnart", [Wohnsitzart.OHNE_FESTEN_WOHNSITZ, Wohnsitzart.AUSLAND])
def test_wohnsitz_ausserhalb_der_region_laesst_bund_offen(client, menschen, ordnung, wohnart):  # noqa: F811
    leute, _, _ = menschen
    autor = leute["autor"]
    Mitglied.objects.filter(pk=autor.pk).update(wohnsitz_art=wohnart)
    client.force_login(autor)
    url = reverse("verfahren:einbringen")
    assert client.post(url, {**ANTRAG, "ebene": "gemeinde", "trotzdem": "1"}).status_code == 200
    assert not Antrag.objects.exists()
    assert client.post(url, {**ANTRAG, "ebene": "bund", "trotzdem": "1"}).status_code == 302
    a = Antrag.objects.get()
    assert a.teilnahmegebiet["kennung"] == "bund" and not a.oertlicher_kreis.exists()


def test_regionale_post_folgt_festgehaltenem_kreis_und_einwilligung(client, menschen, ordnung):  # noqa: F811
    leute, ort, fremdort = menschen
    Mitglied.objects.filter(pk__in=[m.pk for m in leute.values()]).update(post_einwilligung=True)
    a = _einbringen(client, leute["autor"])
    Mitglied.objects.filter(pk=leute["ort"].pk).update(wohnsitz=fremdort)
    Mitglied.objects.filter(pk=leute["fremd"].pk).update(wohnsitz=ort)
    assert list(region_empfaenger(a)) == [leute["ort"]]
    Mitglied.objects.filter(pk=leute["ort"].pk).update(post_einwilligung=False)
    assert not region_empfaenger(a).exists()


def test_nebenwohnsitz_register_korrigiert_nur_den_alten_systemtext():
    schluessel = "region-nebenwohnsitz-zaehlt"
    erstbestand_sicherstellen()
    Parameter.objects.filter(schluessel=schluessel).update(wert="1", beschreibung=NEBENWOHNSITZ_BESCHREIBUNG_ALT)
    erstbestand_sicherstellen()
    parameter = Parameter.objects.get(schluessel=schluessel)
    assert parameter.wert == "1" and "Meine Region" in parameter.beschreibung
    Parameter.objects.filter(schluessel=schluessel).update(beschreibung="Eigene Beschreibung")
    erstbestand_sicherstellen()
    parameter.refresh_from_db()
    assert parameter.beschreibung == "Eigene Beschreibung"


def test_kandidatur_bewerbung_und_zustimmung_benutzen_denselben_kreis(client, menschen, ordnung):  # noqa: F811
    leute, _, _ = menschen
    a = _einbringen(client, leute["autor"], art="mandat")
    b = bewerbung_einreichen(a, leute["ort"], "Vorstellung")
    with pytest.raises(BewerbungsFehler):
        bewerbung_einreichen(a, leute["fremd"], "Fremd")
    _abstimmung(a, 2)
    assert bewerbung_zustimmen(a, leute["autor"], b)
    with pytest.raises(StimmabgabeFehler):
        bewerbung_zustimmen(a, leute["fremd"], b)
    assert a.kandidatur_auszaehlen().stimmberechtigte == 2


def test_uebergang_rechnet_schwelle_und_nenner_mit_oertlichem_kreis(client, menschen, ordnung):  # noqa: F811
    leute, _, fremdort = menschen
    ordnung.regeln = {**ordnung.regeln, "unterstuetzung_anteil": 1}
    ordnung.save(update_fields=["regeln"])
    a = _einbringen(client, leute["autor"])
    assert a.policy().unterstuetzung_grundgesamtheit == 2
    assert a.policy().unterstuetzung_schwelle == 2

    Mitglied.objects.filter(pk=leute["ort"].pk).update(wohnsitz=fremdort)
    in_abstimmung_bringen(a, (leute["autor"], leute["ort"]))
    assert a.stimmberechtigte_anzahl == 2


def test_expertenratsvorschlag_nutzt_den_festgehaltenen_kreis(client, menschen, ordnung):  # noqa: F811
    leute, ort, _ = menschen
    a = _einbringen(client, leute["autor"])
    Mitglied.objects.filter(pk=leute["fremd"].pk).update(wohnsitz=ort)
    entwurf = Entwurf.objects.create(antrag=a)
    entwurf._endabstimmung_oeffnen(a, "Entwurfsfrist", timezone.now())
    a.refresh_from_db()
    assert a.phase == "abstimmung"
    assert a.stimmberechtigte_anzahl == 2


def test_pruefstand_bindet_gemeindekennziffer_bei_gleichem_namen(client, menschen, ordnung):  # noqa: F811
    leute, _, fremdort = menschen
    autor = leute["autor"]
    antrag_einbringen(autor, **ANTRAG, ordnung=ordnung)
    client.force_login(autor)
    url = reverse("verfahren:einbringen")
    eingabe = {**ANTRAG, "ebene": "gemeinde"}
    vorschau = client.post(url, eingabe)
    token = vorschau.context["pruefstand"]
    assert token and Antrag.objects.count() == 1

    Mitglied.objects.filter(pk=autor.pk).update(wohnsitz=fremdort)
    bestaetigung = client.post(url, {**eingabe, "pruefstand": token, "trotzdem": "1"})
    assert bestaetigung.status_code == 200
    assert "die Auswahl hat sich geändert" in str(bestaetigung.context["form"].non_field_errors())
    assert Antrag.objects.count() == 1


@pytest.mark.parametrize("art", ["sache", "mandat"])
def test_leerer_neuer_kreis_bleibt_null_und_export_ist_nachrechenbar(client, menschen, ordnung, art):  # noqa: F811
    leute, _, _ = menschen
    a = _einbringen(client, leute["autor"], art=art)
    if art == "mandat":
        bewerbung_einreichen(a, leute["ort"], "Vorstellung")
    _abstimmung(a, 0)
    ergebnis = a.auszaehlen()
    assert ergebnis.stimmberechtigte == 0 and not ergebnis.angenommen
    a.phase_beginn -= timedelta(days=8)
    a.save(update_fields=["phase_beginn"])
    url = reverse("verfahren:export", args=[a.pk])
    r = client.get(url)
    assert r.status_code == 200
    daten = r.json()
    assert daten["stimmberechtigte"] == 0
    assert "mitglieder" not in daten["teilnahmegebiet"]
    assert not nachrechnen(daten)["angenommen"]


def test_altverfahren_bleibt_weiter_parteiweit(client, menschen, ordnung):  # noqa: F811
    leute, ort, _ = menschen
    a = antrag_einbringen(leute["autor"], **ANTRAG, ordnung=ordnung, ebene="gemeinde", gebiet=ort.name)
    client.force_login(leute["fremd"])
    assert client.post(reverse("verfahren:unterstuetzen", args=[a.pk])).status_code == 302
    a.refresh_from_db()
    assert a.teilnahmegebiet is None and a.unterstuetzungen.count() == 1
