"""Der Export trägt die Audit-Spur mit vollem Hash und Vorgänger (Bestandsaufnahme A7, 0.52.0):
verify/nachrechnen.py rechnet jeden ungekürzten Eintrag nach; personenbezogene Werte sind ausgeblendet."""

import importlib.util
import json
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from verfahren.audit_oeffentlich import MASKE, ereignis_oeffentlich
from verfahren.models import Antrag, AuditEintrag, antrag_einbringen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    NACHRECHNEN_PFAD,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def _skript():
    spec = importlib.util.spec_from_file_location("nachrechnen", NACHRECHNEN_PFAD)
    modul = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(modul)
    return modul


def _beendeter_export(client, ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f"x{i}") for i in range(3)]
    antrag = in_abstimmung_bringen(antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung), leute[1:])
    for m, wahl in zip(leute, ["ja", "ja", "nein"], strict=True):
        client.force_login(m)
        client.post(reverse("verfahren:abstimmen", args=[antrag.pk]), {"stimme": wahl})
    Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=timezone.now() - timedelta(days=8))
    return antrag, json.loads(client.get(reverse("verfahren:export", args=[antrag.pk])).content)


def test_der_export_traegt_vollen_hash_und_vorgaenger(client, ordnung):  # noqa: F811
    antrag, daten = _beendeter_export(client, ordnung)
    assert daten["audit"], "die Spur des Antrags fehlt"
    gespeichert = {e.lfd: e for e in AuditEintrag.objects.filter(ereignis__antrag=antrag.pk)}
    for eintrag in daten["audit"]:
        assert len(eintrag["hash"]) == 64 and eintrag["hash"] == gespeichert[eintrag["lfd"]].hash
        assert eintrag["vorgaenger"] == gespeichert[eintrag["lfd"]].vorgaenger


def test_das_skript_rechnet_die_spur_nach_und_findet_eine_aenderung(client, ordnung):  # noqa: F811
    _antrag, daten = _beendeter_export(client, ordnung)
    skript = _skript()
    ergebnis = skript.audit_nachrechnen(daten["audit"])
    assert ergebnis["audit_nachgerechnet"] == len(daten["audit"]) and ergebnis["audit_gekuerzt"] == 0
    stimme = next(e for e in daten["audit"] if e["typ"] == "stimme")
    stimme["ereignis"]["pseudonym"] = "0" * 32  # jemand „korrigiert“ eine Stimme im Export
    with pytest.raises(SystemExit, match=f"Audit-Eintrag {stimme['lfd']}"):
        skript.audit_nachrechnen(daten["audit"])


def test_die_archivseite_zeigt_den_kurzen_hash_und_den_vollen_im_titel(client, ordnung):  # noqa: F811
    antrag, daten = _beendeter_export(client, ordnung)
    seite = client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()
    h = daten["audit"][-1]["hash"]
    assert f'title="{h}">{h[:12]}</code>' in seite


@pytest.mark.parametrize(
    ("ereignis", "sichtbar", "gekuerzt"),
    [
        ({"typ": "verwaltung", "aktion": "ausschliessen", "mitglied": 17, "durch": 2, "grund": "Name X"},
         {"typ": "verwaltung", "aktion": "ausschliessen", "mitglied": MASKE, "durch": MASKE, "grund": MASKE}, True),
        ({"typ": "testkonten_stillgelegt", "konten": [3, 4], "anlass": "a"},
         {"typ": "testkonten_stillgelegt", "konten": MASKE, "anlass": "a"}, True),
        ({"typ": "mandat_foto", "mandat": 5, "durch": "verwaltung"},
         {"typ": "mandat_foto", "mandat": 5, "durch": "verwaltung"}, False),
        ({"typ": "parameter_geaendert", "schluessel": "k", "alt": "1", "neu": "2", "grund": "Test."},
         {"typ": "parameter_geaendert", "schluessel": "k", "alt": "1", "neu": "2", "grund": "Test."}, False),
        ({"typ": "stimme", "antrag": 1, "pseudonym": "ab"}, {"typ": "stimme", "antrag": 1, "pseudonym": "ab"}, False),
    ],
)
def test_nur_mitgliedskennungen_und_personengruende_werden_ausgeblendet(ereignis, sichtbar, gekuerzt):
    assert ereignis_oeffentlich(ereignis) == (sichtbar, gekuerzt)


def test_ein_gekuerzter_eintrag_wird_gezaehlt_nicht_nachgerechnet():
    AuditEintrag.anhaengen({"typ": "vollzug", "antrag": 1, "status": "umgesetzt", "durch": 9})
    from verfahren.audit_oeffentlich import eintrag_oeffentlich

    eintrag = eintrag_oeffentlich(AuditEintrag.objects.get())
    assert eintrag["gekuerzt"] and eintrag["ereignis"]["durch"] == MASKE
    assert _skript().audit_nachrechnen([eintrag]) == {"audit_nachgerechnet": 0, "audit_gekuerzt": 1}


def test_die_aeltere_art_statt_typ_wird_gelesen():
    from verfahren.audit_oeffentlich import art_von

    assert art_von({"art": "beitrag_gemeldet"}) == "beitrag_gemeldet"
    assert art_von({"typ": "stimme", "art": "sache"}) == "stimme"
