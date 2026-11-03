"""Begrenzter tatsächlicher Bestand, neutrale Auswahl und getrennte Textstände."""

import json

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from faktenbasis import importieren as meta
from faktenbasis.auswahl import erfassen
from faktenbasis.models import Norm
from faktenbasis.ris import antwort_parsen
from faktenbasis.test_ris import NUMMER, STAND, beispiel
from faktenbasis.test_volltext import norm  # noqa: F401
from faktenbasis.testhilfe import abrufuhr  # noqa: F401
from ki.kontext import festhalten
from ki.test_kontext_auftrag import a  # noqa: F401
from parameter.models import Parameter
from verfahren.test_views_aktionen import ordnung  # noqa: F401

pytestmark = [pytest.mark.django_db, pytest.mark.usefixtures("abrufuhr")]


def test_begrenzter_bestand_und_treffer_bleiben_als_teilmenge_nachrechenbar(a, norm, monkeypatch):  # noqa: F811
    daten = beispiel()
    ergebnisse = daten["OgdSearchResult"]["OgdDocumentResults"]
    ergebnisse["Hits"]["#text"] = "8"
    ergebnisse["OgdDocumentReference"] = [
        {"Data": json.loads(json.dumps(norm.rohdaten).replace(norm.ris_id, f"NOR120061{i:02d}"))}
        for i in range(5, 13)
    ]
    monkeypatch.setattr(meta, "abrufen", lambda *args: antwort_parsen(daten, NUMMER))
    meta.importieren(NUMMER, STAND)
    a.titel = norm.kurztitel
    a.save(update_fields=["titel"])
    Parameter.objects.update_or_create(schluessel="quellenkontext-bestandsgrenze", defaults={"wert": "4"})
    Parameter.objects.update_or_create(schluessel="quellenkontext-hoechstzahl", defaults={"wert": "2"})
    with CaptureQueriesContext(connection) as abfragen:
        stand = erfassen(festhalten(a))
    auswahl = stand["auswahl"]
    ids = list(Norm.objects.order_by("ris_id", "pk").values_list("pk", flat=True))
    assert auswahl["bestand_ids"] == ids[:4] and auswahl["bestand_gesamt"] == 8
    assert auswahl["treffer_ids"] == ids[:4] and auswahl["ausgewaehlt"] == ids[:2]
    assert auswahl["bestand_begrenzt"] and auswahl["treffer_begrenzt"]
    assert len([q for q in abfragen if 'FROM "faktenbasis_norm"' in q["sql"]]) == 2
    assert "COUNT(" in next(q["sql"] for q in abfragen if 'OVER (' in q["sql"])


def test_unpassende_quelle_und_suchwortmangel_werden_nicht_als_betroffen_ausgegeben(a, norm):  # noqa: F811
    a.titel = "Xylophon Quarzmuschel"
    a.save(update_fields=["titel"])
    from verfahren.models import AntragsFassung
    AntragsFassung.objects.create(antrag=a, nummer=2, wortlaut="Xylophon Quarzmuschel")
    stand = erfassen(festhalten(a))
    assert stand["auswahl"]["bestand_gesamt"] == 1 and stand["quellen"] == []
