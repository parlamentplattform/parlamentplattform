"""Auftragsfassungen bleiben neben den Vorschlägen erhalten; der Rat entscheidet weiter."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import GremienBeschluss
from gremien.test_werkstatt import mitglied_anlegen
from ki import auftraege
from ki.anbieter import AnbieterFehler, AttrappenAnbieter
from ki.auftraege import auftrag_laden
from ki.models import KILauf, Zweck
from parameter.models import Parameter, ParameterTest
from parameter.models import TestStatus as ParameterTestStatus
from parameter.test_parametertest import korat, register  # noqa: F401

pytestmark = pytest.mark.django_db


@pytest.fixture
def ausgewertet(korat, register):  # noqa: F811
    heute = timezone.localdate()
    return ParameterTest.objects.create(
        parameter=register, testwert="9", alter_wert=register.wert,
        hypothese="Mehr Beteiligung nach längerer Frist.", messgroesse="motions.total",
        beginn=heute - timedelta(days=31), ende=heute - timedelta(days=1),
        rueckweg="Der alte Wert gilt weiter.", status=ParameterTestStatus.AUSGEWERTET,
        angeordnet_von=korat[0], werte_vorher={"motions.total": 10},
        werte_nachher={"motions.total": 12},
    )


def _anfordern(client, test):
    return client.post(
        reverse("gremien:koordination_test", args=[test.pk]), {"aktion": "zukunftswerkstatt"},
    )


def test_parametervorschlag_archiviert_fassung_ohne_einen_wert_einzufuehren(
    client, settings, korat, register, ausgewertet, monkeypatch,  # noqa: F811
):
    settings.DDOE_KI_ANBIETER = "attrappe"
    client.force_login(korat[0])
    vorher = (register.wert, register.status, ausgewertet.status, GremienBeschluss.objects.count())
    gesehen = []
    original = AttrappenAnbieter.frage

    def frage(self, auftrag, eingabe):
        gesehen.append(auftrag)
        return original(self, auftrag, eingabe)

    monkeypatch.setattr(AttrappenAnbieter, "frage", frage)
    assert _anfordern(client, ausgewertet).status_code == 302
    lauf = KILauf.objects.get()
    assert lauf.zweck == Zweck.PARAMETERVORSCHLAG and lauf.erfolgreich
    assert lauf.auftrag_version == "parametervorschlag-v1"
    assert gesehen == [auftrag_laden(Zweck.PARAMETERVORSCHLAG).text]
    assert ausgewertet.hypothese in lauf.eingabe and "10" in lauf.eingabe and "12" in lauf.eingabe
    ausgewertet.refresh_from_db()
    register.refresh_from_db()
    assert ausgewertet.ki_lauf_id == lauf.pk
    assert (register.wert, register.status, ausgewertet.status, GremienBeschluss.objects.count()) == vorher
    public = client.get(reverse("verfahren:zukunftswerkstatt")).content.decode()
    assert "parametervorschlag-v1" in public
    assert "entschieden wird vom Koordinationsrat" in public


def test_neuer_parameterauftrag_aendert_keinen_archivierten_lauf(
    client, settings, korat, ausgewertet, tmp_path, monkeypatch,  # noqa: F811
):
    settings.DDOE_KI_ANBIETER = "attrappe"
    alt = auftrag_laden(Zweck.PARAMETERVORSCHLAG)
    (tmp_path / "parametervorschlag-v1.md").write_text(alt.text, encoding="utf-8")
    monkeypatch.setattr(auftraege, "ORDNER", tmp_path)
    client.force_login(korat[0])
    _anfordern(client, ausgewertet)
    erster = KILauf.objects.get()
    neu = "Neuer Auftrag: Der Koordinationsrat entscheidet."
    (tmp_path / "parametervorschlag-v2.md").write_text(neu, encoding="utf-8")
    _anfordern(client, ausgewertet)
    zweiter = KILauf.objects.exclude(pk=erster.pk).get()
    assert zweiter.auftrag_version == "parametervorschlag-v2"
    erster.refresh_from_db()
    assert erster.auftrag_version == "parametervorschlag-v1"
    assert erster.antwort and erster.erfolgreich
    public = client.get(reverse("verfahren:zukunftswerkstatt")).content.decode()
    assert "parametervorschlag-v1" in public and "parametervorschlag-v2" in public and neu in public


def test_gescheiterter_parametervorschlag_behaelt_seine_fassung_und_den_bisherigen_vorschlag(
    client, settings, korat, ausgewertet, monkeypatch,  # noqa: F811
):
    settings.DDOE_KI_ANBIETER = "attrappe"
    client.force_login(korat[0])
    _anfordern(client, ausgewertet)
    erster = KILauf.objects.get()

    def kaputt(self, auftrag, eingabe):
        raise AnbieterFehler("Testfehler")

    monkeypatch.setattr(AttrappenAnbieter, "frage", kaputt)
    assert _anfordern(client, ausgewertet).status_code == 302
    fehler = KILauf.objects.exclude(pk=erster.pk).get()
    assert not fehler.erfolgreich and fehler.auftrag_version == "parametervorschlag-v1"
    ausgewertet.refresh_from_db()
    assert ausgewertet.ki_lauf_id == erster.pk and ausgewertet.status == ParameterTestStatus.AUSGEWERTET


@pytest.mark.parametrize("zugang", ["gast", "mitglied", "budget"])
def test_die_versionierung_oeffnet_keinen_weiteren_modellzugang(
    client, settings, korat, ausgewertet, zugang,  # noqa: F811
):
    settings.DDOE_KI_ANBIETER = "attrappe"
    if zugang == "mitglied":
        client.force_login(mitglied_anlegen("ohne-ratsrolle"))
    elif zugang == "budget":
        client.force_login(korat[0])
        Parameter.objects.filter(schluessel="ki-monatstokens").update(wert="0")
    _anfordern(client, ausgewertet)
    assert not KILauf.objects.exists()
    ausgewertet.refresh_from_db()
    assert ausgewertet.ki_lauf_id is None
