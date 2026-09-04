"""Die Regel des Abstimmungs-Chats (FB-G6): Reihung nach Engagement und die
Auswertung nach Fristablauf — nachgerechnet ohne Datenbank."""

from __future__ import annotations

from plattform_core import vorschlagschat as v


def b(kennung, ja=0, nein=0, zeit=0, system=False, kritik=False) -> dict:
    return {"id": kennung, "ja": ja, "nein": nein, "zeit": zeit, "system": system, "ist_kritik": kritik}


def test_engagement_zaehlt_beteiligung_nicht_richtung():
    assert v.engagement(b("a", ja=3, nein=4)) == 7
    assert v.engagement(b("b")) == 0
    assert v.anteil(b("a", ja=3, nein=1)) == 0.75
    assert v.anteil(b("leer")) == 0.0, "ohne Reaktionen ist der Anteil 0, nicht undefiniert"


def test_reihung_engagement_dann_anteil_dann_zeit():
    beitraege = [
        b("wenig", ja=1, zeit=1),
        b("viel-umstritten", ja=3, nein=4, zeit=2),
        b("viel-getragen", ja=7, zeit=3),
        b("gleich-aelter", ja=1, zeit=0),
    ]
    reihe = [x["id"] for x in v.reihen(beitraege)]
    assert reihe[0] == "viel-getragen", "gleiches Engagement, mehr Zustimmung zuerst"
    assert reihe[1] == "viel-umstritten"
    assert reihe[2:] == ["gleich-aelter", "wenig"], "bei Gleichstand entscheidet die Zeit"


def test_stille_hemmt_nie():
    ergebnis = v.auswerten([b("passt", system=True, zeit=0), b("kritik", kritik=True, zeit=1)])
    assert ergebnis["angenommen"] is True and ergebnis["grund"] == "stille"
    assert ergebnis["stimmen"] == 0


def test_oben_und_ueber_der_schwelle_stuft_hoch():
    ergebnis = v.auswerten([b("passt", ja=3, nein=1, system=True, zeit=0), b("kritik", ja=1, kritik=True, zeit=1)])
    assert ergebnis["angenommen"] is True and ergebnis["grund"] == "passt_alles_oben"
    assert ergebnis["oben"] is True and ergebnis["anteil"] == 0.75


def test_genau_die_haelfte_genuegt_nicht():
    """A0-07 verlangt *mehr* als 50 % — Gleichstand ist keine Mehrheit."""
    ergebnis = v.auswerten([b("passt", ja=2, nein=2, system=True, zeit=0)])
    assert ergebnis["angenommen"] is False and ergebnis["grund"] == "rueckgabe"


def test_oben_aber_zu_wenig_zustimmung_gibt_zurueck():
    ergebnis = v.auswerten([b("passt", ja=1, nein=5, system=True, zeit=0), b("kritik", ja=1, kritik=True, zeit=1)])
    assert ergebnis["angenommen"] is False and ergebnis["oben"] is True


def test_kritik_oben_gibt_zurueck_obwohl_die_zustimmung_reicht():
    """Der Gründer verlangt beides: ganz oben *und* mehr als 50 % (D-G6b)."""
    ergebnis = v.auswerten([b("passt", ja=3, system=True, zeit=0), b("kritik", ja=5, nein=2, kritik=True, zeit=1)])
    assert ergebnis["oben"] is False and ergebnis["angenommen"] is False
    assert ergebnis["anteil"] == 1.0, "die Zustimmung allein genügt nicht"


def test_ohne_systembeitrag_geht_es_weiter():
    ergebnis = v.auswerten([b("kritik", ja=2, kritik=True, zeit=0)])
    assert ergebnis["angenommen"] is True and ergebnis["grund"] == "kein_systembeitrag"


def test_schwelle_ist_einstellbar():
    beitraege = [b("passt", ja=6, nein=4, system=True, zeit=0)]
    assert v.auswerten(beitraege, schwelle=0.5)["angenommen"] is True
    assert v.auswerten(beitraege, schwelle=0.6)["angenommen"] is False, "60 % verlangt mehr als 60 %"


def test_kritik_uebergeben_reiht_nach_engagement_und_laesst_das_system_aus():
    beitraege = [
        b("passt", ja=9, system=True, zeit=0),
        b("kritik-klein", ja=1, kritik=True, zeit=1),
        b("kritik-gross", ja=4, nein=1, kritik=True, zeit=2),
        b("lob", ja=8, zeit=3),
    ]
    assert [x["id"] for x in v.kritik_uebergeben(beitraege)] == ["kritik-gross", "kritik-klein"]


def test_prozentwert_steht_in_der_rechnung():
    """Die Anzeige soll nicht selbst rechnen — sonst steht irgendwo „1 %" statt 67 %."""
    ergebnis = v.auswerten([b("passt", ja=2, nein=1, system=True, zeit=0)])
    assert ergebnis["prozent"] == 67 and 0.66 < ergebnis["anteil"] < 0.67
    assert v.auswerten([b("passt", system=True, zeit=0)])["prozent"] == 0
