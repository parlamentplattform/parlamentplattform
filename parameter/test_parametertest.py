"""Das Parameterverfahren (FB-J3, § 6 Abs 11 lit c): Test → Auswertung → Vorschlag → Einführung.

Die Satzung nennt zweimal den Rat: Er ordnet den Test an, er gibt die Einführung frei. Beides
ist hier ein Beschluss nach § 6 Abs 2 lit e — kein Ratsmitglied kann allein einen Wert setzen.
Und kein Test erreicht ein laufendes Verfahren (§ 5 Abs 5): Das Register wirkt nur auf neue.
"""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import (
    Anlass,
    BeschlussStatus,
    GremienBeschluss,
    Gremium,
    Hinweis,
    HinweisStatus,
    parametertests_fortschreiben,
)
from gremien.test_werkstatt import mitglied_anlegen, ordnung, rolle_geben  # noqa: F401
from parameter import models as pm
from parameter.models import Aenderung, Parameter, ParameterTest, Status, erstbestand_sicherstellen
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db

SCHLUESSEL = "gremien-beschluss-tage"


@pytest.fixture
def korat():
    leute = [mitglied_anlegen(f"kr{i}") for i in range(3)]
    for m in leute:
        rolle_geben(m, Gremium.KOORDINATIONSRAT)
    return leute


@pytest.fixture
def register():
    erstbestand_sicherstellen()
    return Parameter.objects.get(schluessel=SCHLUESSEL)


def anordnen(client, wer, parameter, testwert="9", ende=None, messgroesse="motions.total"):
    client.force_login(wer)
    return client.post(
        reverse("gremien:koordination_test", args=[0]),
        {
            "aktion": "anordnen",
            "parameter": parameter.pk,
            "testwert": testwert,
            "hypothese": "Kürzere Fristen, mehr Beteiligung.",
            "messgroesse": messgroesse,
            "ende": (ende or (timezone.localdate() + timedelta(days=30))).isoformat(),
            "rueckweg": "Der alte Wert kommt am Ende von selbst zurück.",
        },
    )


def abstimmen(client, leute, beschluss, option="dafuer"):
    for m in leute:
        client.force_login(m)
        client.post(
            reverse("gremien:beschluss_stimme", args=[beschluss.pk]),
            {"option": option, "begruendung": "Weil."},
        )
    beschluss.refresh_from_db()
    return beschluss


def test_anordnen_legt_test_und_beschluss_an_und_aendert_noch_nichts(client, korat, register):
    anordnen(client, korat[0], register)
    test = ParameterTest.objects.get()
    assert test.status == pm.TestStatus.GEPLANT and test.beschluss.anlass == Anlass.PARAMETERTEST
    register.refresh_from_db()
    assert register.wert == "7" and register.status == Status.GUELTIG, "vor dem Beschluss ändert sich nichts"


def test_nur_der_rat_ordnet_an(client, korat, register):
    fremd = mitglied_anlegen("fremd")
    anordnen(client, fremd, register)
    assert not ParameterTest.objects.exists()


def test_der_beschluss_startet_den_test_und_setzt_das_band(client, korat, register):
    anordnen(client, korat[0], register)
    test = ParameterTest.objects.get()
    abstimmen(client, korat, test.beschluss)
    test.refresh_from_db()
    register.refresh_from_db()
    assert test.status == pm.TestStatus.LAEUFT and test.alter_wert == "7" and test.beginn == timezone.localdate()
    assert register.wert == "9" and register.status == Status.IM_TEST and register.test_bis == test.ende
    assert "motions.total" in test.werte_vorher
    aenderung = Aenderung.objects.get(parameter=register)
    assert aenderung.alter_wert == "7" and aenderung.neuer_wert == "9" and "Beschluss KR-" in aenderung.durch
    assert any(e.ereignis["typ"] == "parametertest_begonnen" for e in AuditEintrag.objects.all())
    # Öffentlich: das Band steht im Register und auf der Seite des Parameters
    assert "Im Test" in client.get(reverse("parameter:liste")).content.decode()
    seite = client.get(reverse("parameter:parameter", args=[SCHLUESSEL])).content.decode()
    assert "Kürzere Fristen" in seite and "läuft" in seite


def test_dagegen_heisst_verworfen_und_der_wert_bleibt(client, korat, register):
    anordnen(client, korat[0], register)
    test = ParameterTest.objects.get()
    abstimmen(client, korat, test.beschluss, option="dagegen")
    test.refresh_from_db()
    register.refresh_from_db()
    assert test.status == pm.TestStatus.VERWORFEN and register.wert == "7" and register.status == Status.GUELTIG


def test_ein_test_je_parameter(client, korat, register):
    anordnen(client, korat[0], register)
    anordnen(client, korat[1], register, testwert="11")
    assert ParameterTest.objects.count() == 1


def test_die_messgroesse_muss_eine_kennzahl_sein(client, korat, register):
    anordnen(client, korat[0], register, messgroesse="mein.bauchgefuehl")
    assert not ParameterTest.objects.exists()


def test_das_ende_liegt_in_der_zukunft(client, korat, register):
    anordnen(client, korat[0], register, ende=timezone.localdate())
    assert not ParameterTest.objects.exists()


def laufenden_test_anlegen(client, korat, register, tage=30):
    anordnen(client, korat[0], register, ende=timezone.localdate() + timedelta(days=tage))
    test = ParameterTest.objects.get()
    abstimmen(client, korat, test.beschluss)
    test.refresh_from_db()
    return test


def test_nach_dem_ende_faellt_der_wert_zurueck_und_der_posteingang_bekommt_die_auswertung(client, korat, register):
    test = laufenden_test_anlegen(client, korat, register)
    assert parametertests_fortschreiben() == 0, "vor dem Ende geschieht nichts"
    ParameterTest.objects.filter(pk=test.pk).update(ende=timezone.localdate() - timedelta(days=1))
    assert parametertests_fortschreiben() == 1
    test.refresh_from_db()
    register.refresh_from_db()
    assert test.status == pm.TestStatus.AUSGEWERTET and "motions.total" in test.werte_nachher
    assert register.wert == "7" and register.status == Status.GUELTIG and register.test_bis is None
    rueckweg = Aenderung.objects.filter(parameter=register).order_by("-geaendert_am").first()
    assert rueckweg.alter_wert == "9" and rueckweg.neuer_wert == "7" and "Testende" in rueckweg.durch
    hinweis = Hinweis.objects.get(parametertest=test)
    assert hinweis.status == HinweisStatus.OFFEN and "vorher" in hinweis.text
    assert parametertests_fortschreiben() == 0, "idempotent"


def test_die_einfuehrung_braucht_wieder_einen_beschluss(client, korat, register):
    test = laufenden_test_anlegen(client, korat, register)
    ParameterTest.objects.filter(pk=test.pk).update(ende=timezone.localdate() - timedelta(days=1))
    parametertests_fortschreiben()
    client.force_login(korat[0])
    client.post(reverse("gremien:koordination_test", args=[test.pk]), {"aktion": "einfuehrung"})
    test.refresh_from_db()
    beschluss = test.einfuehrung_beschluss
    assert beschluss.anlass == Anlass.PARAMETER_EINFUEHRUNG and beschluss.status == BeschlussStatus.OFFEN
    register.refresh_from_db()
    assert register.wert == "7", "vor dem Beschluss gilt der alte Wert"
    abstimmen(client, korat, beschluss)
    test.refresh_from_db()
    register.refresh_from_db()
    assert test.status == pm.TestStatus.EINGEFUEHRT and register.wert == "9" and register.status == Status.GUELTIG
    letzte = Aenderung.objects.filter(parameter=register).order_by("-geaendert_am").first()
    assert letzte.neuer_wert == "9" and "Einführung" in letzte.grund
    assert any(e.ereignis["typ"] == "parameter_eingefuehrt" for e in AuditEintrag.objects.all())


def test_der_posteingang_legt_den_einfuehrungsbeschluss_an(client, korat, register):
    test = laufenden_test_anlegen(client, korat, register)
    ParameterTest.objects.filter(pk=test.pk).update(ende=timezone.localdate() - timedelta(days=1))
    parametertests_fortschreiben()
    hinweis = Hinweis.objects.get(parametertest=test)
    client.force_login(korat[1])
    client.post(reverse("gremien:koordination_hinweis", args=[hinweis.pk]), {"aktion": "beschluss"})
    hinweis.refresh_from_db()
    assert hinweis.status == HinweisStatus.BESCHLUSS
    assert GremienBeschluss.objects.filter(anlass=Anlass.PARAMETER_EINFUEHRUNG).count() == 1


def test_verwerfen_braucht_einen_grund_und_der_bleibt_stehen(client, korat, register):
    test = laufenden_test_anlegen(client, korat, register)
    ParameterTest.objects.filter(pk=test.pk).update(ende=timezone.localdate() - timedelta(days=1))
    parametertests_fortschreiben()
    client.force_login(korat[0])
    client.post(reverse("gremien:koordination_test", args=[test.pk]), {"aktion": "verwerfen", "grund": ""})
    test.refresh_from_db()
    assert test.status == pm.TestStatus.AUSGEWERTET
    client.post(
        reverse("gremien:koordination_test", args=[test.pk]),
        {"aktion": "verwerfen", "grund": "Die Beteiligung sank."},
    )
    test.refresh_from_db()
    assert test.status == pm.TestStatus.VERWORFEN and "Die Beteiligung sank." in test.auswertung
    assert Hinweis.objects.get(parametertest=test).status == HinweisStatus.VERWORFEN


def test_ein_laufendes_verfahren_bleibt_unberuehrt(client, korat, ordnung):  # noqa: F811
    """§ 5 Abs 5, § 6 Abs 11 lit c: Tests dürfen laufende Verfahren nicht berühren."""
    from verfahren.models import antrag_einbringen

    erstbestand_sicherstellen()
    parameter = Parameter.objects.get(schluessel="expertenrat-erstvorschlag-tage")
    antrag = antrag_einbringen(
        mitglied_anlegen("stellerin"),
        titel="Ein Antrag vor dem Test",
        wortlaut="Wortlaut.",
        begruendung="Grund.",
        ordnung=ordnung,
    )
    vorher = antrag.policy().beratung_tage
    anordnen(client, korat[0], parameter, testwert="35")
    abstimmen(client, korat, ParameterTest.objects.get().beschluss)
    parameter.refresh_from_db()
    assert parameter.wert == "35"
    antrag.refresh_from_db()
    assert antrag.policy().beratung_tage == vorher


def test_der_parameterbericht_zeigt_aenderungen_und_tests_des_jahres(client, korat, register):
    laufenden_test_anlegen(client, korat, register)
    jahr = timezone.localdate().year
    seite = client.get(reverse("parameter:bericht", args=[jahr])).content.decode()
    assert SCHLUESSEL in seite and "Kürzere Fristen" in seite
    assert client.get(reverse("parameter:bericht", args=[jahr - 5])).status_code == 200


def test_die_zukunftswerkstatt_schweigt_ehrlich_ohne_anbieter(client, korat, register, settings):
    settings.DDOE_KI_SCHLUESSEL = ""
    test = laufenden_test_anlegen(client, korat, register)
    ParameterTest.objects.filter(pk=test.pk).update(ende=timezone.localdate() - timedelta(days=1))
    parametertests_fortschreiben()
    client.force_login(korat[0])
    antwort = client.post(
        reverse("gremien:koordination_test", args=[test.pk]), {"aktion": "zukunftswerkstatt"}, follow=True
    )
    test.refresh_from_db()
    assert test.ki_lauf is None
    assert "Steckplatz" in antwort.content.decode()
