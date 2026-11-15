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
from faktenbasis.test_ris_historie import GESETZ, KENNUNG, TAG, URL, norm_anlegen, original, referenz
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


def befehl(*belege, normbestand=False):
    args = ["--tag", TAG.isoformat()]
    if normbestand:
        args.append("--normbestand")
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
    assert "normabgleich" not in ergebnis
    sql = [abfrage["sql"].lower() for abfrage in abfragen]
    archivlesen = [x for x in sql if '"faktenbasis_risaenderungsseite"' in x]
    assert len(archivlesen) == 1 and '"original"' not in archivlesen[0]
    assert all(x.startswith("select") for x in sql)
    assert not any('"faktenbasis_norm"' in x for x in sql)
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


@pytest.mark.django_db
def test_freiwilliger_normabgleich_nutzt_exakte_bundeskennung_und_stichtag():
    erste = seite_anlegen(1, NUMMERN[:10])
    zweite = seite_anlegen(2, NUMMERN[10:])
    stichtag = TAG - timedelta(days=7)
    norm_anlegen(stichtag, kennung=NUMMERN[0])
    passend = norm_anlegen(stichtag, kennung=NUMMERN[0])
    norm_anlegen(TAG, kennung=NUMMERN[0], gesetz="77777777")
    norm_anlegen(TAG, kennung=NUMMERN[1], ebene="Land", land="Wien")
    norm_anlegen(TAG, kennung=NUMMERN[2], erfolgreich=False)
    letzter = norm_anlegen(TAG + timedelta(days=2), kennung=NUMMERN[-1])
    vorher = AuditEintrag.objects.count()
    with CaptureQueriesContext(connection) as abfragen:
        ergebnis = befehl(zweite.pk, erste.pk, normbestand=True)
    assert ergebnis["tag"] == TAG.isoformat()
    assert ergebnis["normabgleich"]["fassung"] == 1
    dokumente = ergebnis["normabgleich"]["dokumente"]
    assert [d["dokumentnummer"] for d in dokumente] == list(NUMMERN)
    assert dokumente[0] == {
        "dokumentnummer": NUMMERN[0], "gesetzesnummer": GESETZ, "beleg": erste.pk,
        "normstand": {"datensatz": passend.pk, "stichtag": stichtag.isoformat()},
    }
    assert all(d["normstand"] is None for d in dokumente[1:-1])
    assert dokumente[-1]["beleg"] == zweite.pk
    assert dokumente[-1]["normstand"] == {"datensatz": letzter.pk, "stichtag": letzter.stand.isoformat()}
    norm_sql = [a["sql"].lower() for a in abfragen if '"faktenbasis_norm"' in a["sql"].lower()]
    assert len(norm_sql) == 1 and '"rohdaten"' not in norm_sql[0]
    assert all(a["sql"].lower().startswith("select") for a in abfragen)
    assert AuditEintrag.objects.count() == vorher


@pytest.mark.django_db
def test_normabgleich_buendelt_mehr_als_einhundert_eindeutige_verweise():
    nummern = [f"NOR{n:08d}" for n in range(1, 102)]
    belege = [
        seite_anlegen(seite + 1, nummern[seite * 10:seite * 10 + 10], treffer=101).pk
        for seite in range(11)
    ]
    passend = norm_anlegen(TAG, kennung=nummern[-1])
    with CaptureQueriesContext(connection) as abfragen:
        ergebnis = befehl(*reversed(belege), normbestand=True)
    assert len(ergebnis["normabgleich"]["dokumente"]) == 101
    assert ergebnis["normabgleich"]["dokumente"][-1]["normstand"]["datensatz"] == passend.pk
    assert sum('"faktenbasis_norm"' in a["sql"].lower() for a in abfragen) == 2
