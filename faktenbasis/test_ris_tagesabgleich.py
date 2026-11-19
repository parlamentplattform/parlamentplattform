import io
import json
from dataclasses import replace
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import connection
from django.test.utils import CaptureQueriesContext

from faktenbasis.models import RisAenderungsseite
from faktenbasis.ris_historie import importieren
from faktenbasis.test_ris_historie import KENNUNG, TAG, URL, original, referenz
from parameter.models import Parameter
from plattform_core.ris_historie import TagesabgleichFehler, Tagesseite, tagesabgleich
from verfahren.models import AuditEintrag

NUMMERN = tuple(f"NOR{n:08d}" for n in range(1, 12))
ERSTE = Tagesseite(11, TAG, 1, 11, "b" * 64, NUMMERN[:10])
ZWEITE = Tagesseite(10, TAG, 2, 11, "a" * 64, NUMMERN[10:])


def test_seitensatz_aus_eigenen_trefferangaben_nachrechnen():
    assert tagesabgleich(TAG, [ZWEITE, ERSTE]) == {
        "fassung": 1, "tag": TAG.isoformat(), "gemeldete_treffer": 11,
        "seiten": [
            {"seite": 1, "datensatz": 11, "original_sha256": "b" * 64, "dokumentnummern": list(NUMMERN[:10])},
            {"seite": 2, "datensatz": 10, "original_sha256": "a" * 64, "dokumentnummern": list(NUMMERN[10:])},
        ],
    }


@pytest.mark.parametrize("daten,code", [
    ({"tag": TAG - timedelta(days=1)}, "tag"),
    ({"treffer": 12}, "trefferzahl"),
    ({"seite": 1}, "seitenfolge"),
    ({"seite": 3}, "seitenfolge"),
    ({"datensatz": 0}, "beleg"),
    ({"sha256": "0"}, "beleg"),
    ({"dokumentnummern": ()}, "referenzen"),
    ({"dokumentnummern": ("NOR	0012345",)}, "referenzen"),
    ({"dokumentnummern": NUMMERN[:1]}, "dokument_doppelt"),
])
def test_widersprueche_machen_den_ausgewaehlten_satz_ungueltig(daten, code):
    with pytest.raises(TagesabgleichFehler, match=code):
        tagesabgleich(TAG, [ERSTE, replace(ZWEITE, **daten)])


def seite_anlegen(seite, nummern, *, tag=TAG, treffer=11):
    verweise = []
    for kennung in nummern:
        verweis = referenz(tag)
        meta = verweis["Data"]["Metadaten"]
        meta["Technisch"]["ID"] = kennung
        meta["Allgemein"]["DokumentUrl"] = URL.replace(KENNUNG, kennung)
        verweise.append(verweis)
    return importieren(tag, seite, original(verweise, seite=seite, treffer=treffer))


def befehl(*belege):
    args = ["--tag", TAG.isoformat()]
    for beleg in belege:
        args.extend(("--beleg", str(beleg)))
    ausgabe = io.StringIO()
    call_command("ris_aenderungstag_pruefen", *args, stdout=ausgabe)
    return json.loads(ausgabe.getvalue())


@pytest.mark.django_db
def test_nur_ausgewaehlte_seiten_ohne_originale_oder_schreibwirkung():
    zweite = seite_anlegen(2, NUMMERN[10:])
    erste = seite_anlegen(1, NUMMERN[:10])
    seite_anlegen(2, ("NOR00000012",))
    vorher = AuditEintrag.objects.count()
    with CaptureQueriesContext(connection) as abfragen:
        ergebnis = befehl(zweite.pk, erste.pk)
    assert [seite["datensatz"] for seite in ergebnis["seiten"]] == [erste.pk, zweite.pk]
    sql = [abfrage["sql"].lower() for abfrage in abfragen]
    archivlesen = [x for x in sql if '"faktenbasis_risaenderungsseite"' in x]
    assert len(archivlesen) == 1 and '"original"' not in archivlesen[0]
    assert all(x.startswith("select") for x in sql)
    assert AuditEintrag.objects.count() == vorher and RisAenderungsseite.objects.count() == 3
    for auswahl, grund in (
        ([erste.pk], "seitenfolge"),
        ([erste.pk, erste.pk], "auswahl"),
        ([erste.pk, 0], "auswahl"),
        ([erste.pk, zweite.pk + 100], "beleg_fehlt"),
    ):
        with pytest.raises(CommandError, match=grund):
            befehl(*auswahl)


@pytest.mark.django_db
def test_uebergrenze_und_unlesbare_grenze_liefern_keinen_teilbestand():
    register = "faktenbasis-bestandsnachweis-hoechstzahl"
    for wert, meldung in (("1", "umfang"), ("unbekannt", "grenze")):
        Parameter.objects.update_or_create(schluessel=register, defaults={"wert": wert})
        with CaptureQueriesContext(connection) as abfragen, pytest.raises(CommandError, match=meldung):
            befehl(1, 2)
        assert not any("faktenbasis_risaenderungsseite" in x["sql"].lower() for x in abfragen)
