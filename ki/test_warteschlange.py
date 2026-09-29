"""Die Warteschlange der Zukunftswerkstatt (FB-H1, FB-H6): idempotentes Einreihen, Tageskontingent,
atomare Reservierung, Rückzug bei Fehlern bis „gescheitert“, toleranter Ergebnisparser, versionierte
Auftragstexte — und der Lauf über den Hintergrundfaden. Alles ohne Netz (Attrappe)."""

import json
from datetime import timedelta

import pytest
from django.utils import timezone

from ki import warteschlange
from ki.anbieter import AttrappenAnbieter, SteckplatzStumm
from ki.auftraege import auftrag_laden, auftragsversionen
from ki.models import Auftragsstatus, KIAuftrag, KILauf, Zweck
from ki.rechtsbezug import antwort_parsen, rechtsbezug_fuer, rechtsbezug_lage
from ki.warteschlange import (
    abarbeiten,
    auftrag_ausfuehren,
    einreihen,
    platz_in_der_schlange,
    warteschlange_stand,
)
from verfahren import hintergrund
from verfahren.models import Hintergrundlauf, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

JSON_ANTWORT = json.dumps(
    {
        "normen": [
            {"titel": "Parteiengesetz 2012", "ebene": "Bund", "kennung": "BGBl. I Nr. 56/2012", "aenderung": "aendern", "begruendung": "Regelt die Rechenschaft."},
            {"titel": "Erfundene Norm", "ebene": "Mars", "aenderung": "explodieren"},
            {"kein": "titel"},
        ],
        "hinweis": "Bundeskompetenz nach Art. 10 B-VG.",
        "unsicherheit": "mittel",
    }
)


@pytest.fixture
def attrappe(settings):
    settings.DDOE_KI_ANBIETER = "attrappe"


@pytest.fixture
def json_attrappe(attrappe, monkeypatch):
    """Die Attrappe antwortet mit der festen JSON-Form — wie ein echter Anbieter auf rechtsbezug-v1."""
    from ki.anbieter import Antwort

    monkeypatch.setattr(
        AttrappenAnbieter, "frage", lambda self, auftrag, eingabe: Antwort(JSON_ANTWORT, "attrappe-1", 10, 20)
    )


def _antrag(ordnung, name="anna", titel=None):  # noqa: F811
    return antrag_einbringen(mitglied_anlegen(name), titel or ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)


# --- Auftragstexte ------------------------------------------------------------------------------


def test_auftragstext_rechtsbezug_liegt_versioniert_im_repo():
    text = auftrag_laden("rechtsbezug")
    assert text.version == "rechtsbezug-v1" and "JSON" in text.text and "Rechtsberatung" in text.text
    assert [a.version for a in auftragsversionen()] == ["rechtsbezug-v1"]
    with pytest.raises(KeyError):
        auftrag_laden("gibtesnicht")


# --- Einreihen ------------------------------------------------------------------------------------


def test_einreihen_ist_idempotent_je_antrag_zweck_und_fassung(ordnung):  # noqa: F811
    antrag = _antrag(ordnung)
    a1 = einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    a2 = einreihen(Zweck.RECHTSBEZUG, antrag, mitglied_anlegen("bernd"))
    assert a1.pk == a2.pk and KIAuftrag.objects.count() == 1
    assert a1.status == Auftragsstatus.GEPLANT and a1.fassung_nummer == 1
    einreihen(Zweck.AEHNLICHKEIT, antrag, antrag.eingebracht_von)
    assert KIAuftrag.objects.count() == 2
    with pytest.raises(ValueError):
        einreihen(Zweck.EINSCHAETZUNG, antrag, antrag.eingebracht_von)


def test_platz_in_der_schlange_zaehlt_die_wartenden_davor(ordnung):  # noqa: F811
    a = einreihen(Zweck.RECHTSBEZUG, _antrag(ordnung, "a"), mitglied_anlegen("x"))
    b = einreihen(Zweck.RECHTSBEZUG, _antrag(ordnung, "b", "Zweiter"), mitglied_anlegen("y"))
    assert platz_in_der_schlange(a) == 1 and platz_in_der_schlange(b) == 2
    assert platz_in_der_schlange(None) is None


# --- Abarbeiten ---------------------------------------------------------------------------------


def test_ohne_anbieter_wartet_alles_und_nichts_zaehlt_als_versuch(settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "mistral"
    settings.DDOE_KI_SCHLUESSEL = ""
    a = einreihen(Zweck.RECHTSBEZUG, _antrag(ordnung), mitglied_anlegen("x"))
    stand = abarbeiten()
    assert stand["anbieter"] is False and stand["offen"] == 1
    a.refresh_from_db()
    assert a.versuche == 0 and a.status == Auftragsstatus.GEPLANT


def test_rechtsbezug_lauf_archiviert_mit_auftragsversion_und_erledigt_den_auftrag(json_attrappe, ordnung):  # noqa: F811
    antrag = _antrag(ordnung)
    a = einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    stand = abarbeiten()
    assert stand["erledigt"] == 1 and stand["offen"] == 0
    a.refresh_from_db()
    assert a.status == Auftragsstatus.ERLEDIGT and a.lauf and a.erledigt_am and a.sperrcode == ""
    lauf = a.lauf
    assert lauf.zweck == Zweck.RECHTSBEZUG and lauf.auftrag_version == "rechtsbezug-v1" and lauf.antrag == antrag
    assert "Titel: " + ANTRAG["titel"] in lauf.eingabe and ANTRAG["wortlaut"] in lauf.eingabe
    ergebnis = rechtsbezug_fuer(antrag)
    assert [n["titel"] for n in ergebnis["normen"]] == ["Parteiengesetz 2012", "Erfundene Norm"]
    assert ergebnis["normen"][0]["ebene"] == "Bund" and ergebnis["normen"][0]["aenderung"] == "aendern"
    assert ergebnis["normen"][1]["ebene"] == "" and ergebnis["normen"][1]["aenderung"] == "beruehrt"  # unbekannte Werte fallen ehrlich zurück
    assert all(n["verifiziert"] is False for n in ergebnis["normen"])
    assert ergebnis["unsicherheit"] == "mittel" and ergebnis["auftrag_version"] == "rechtsbezug-v1"


def test_tageskontingent_deckelt_die_laeufe(json_attrappe, ordnung):  # noqa: F811
    from parameter.models import Parameter

    Parameter.objects.create(schluessel="ki-tageslaeufe", wert="2", beschreibung="x", quelle="Test")
    for i in range(3):
        einreihen(Zweck.RECHTSBEZUG, _antrag(ordnung, f"m{i}", f"Antrag {i}"), mitglied_anlegen(f"x{i}"))
    stand = abarbeiten()
    assert stand["erledigt"] == 2 and stand["offen"] == 1
    stand = abarbeiten()
    assert stand.get("kontingent_erschoepft") is True and stand["erledigt"] == 0
    # Am nächsten Tag geht es weiter
    stand = abarbeiten(timezone.now() + timedelta(days=1))
    assert stand["erledigt"] == 1 and stand["offen"] == 0
    assert warteschlange_stand()["kontingent"] == 2


def test_reservierter_auftrag_wird_nicht_zugleich_gerechnet(json_attrappe, ordnung):  # noqa: F811
    jetzt = timezone.now()
    a = einreihen(Zweck.RECHTSBEZUG, _antrag(ordnung), mitglied_anlegen("x"))
    KIAuftrag.objects.filter(pk=a.pk).update(sperrcode="y" * 32, gesperrt_bis=jetzt + timedelta(minutes=5))
    assert auftrag_ausfuehren(a.pk, jetzt) == "uebersprungen"
    assert KILauf.objects.count() == 0
    # Nach Ablauf der Sperre (Prozessverlust) übernimmt der nächste Worker
    assert auftrag_ausfuehren(a.pk, jetzt + timedelta(minutes=6)) == "erledigt"


def test_fehler_ziehen_den_naechsten_versuch_nach_hinten_bis_gescheitert(attrappe, ordnung, monkeypatch):  # noqa: F811
    def kaputt(self, auftrag, eingabe):
        from ki.anbieter import AnbieterFehler

        raise AnbieterFehler("HTTP 503 vom Anbieter")

    monkeypatch.setattr(AttrappenAnbieter, "frage", kaputt)
    antrag = _antrag(ordnung)
    a = einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    jetzt = timezone.now()
    erwartete_pausen = [2, 4, 8, 16, 32]
    for versuch, pause in enumerate(erwartete_pausen, start=1):
        assert auftrag_ausfuehren(a.pk, jetzt) == "verschoben"
        a.refresh_from_db()
        assert a.versuche == versuch and a.status == Auftragsstatus.GEPLANT and "HTTP 503" in a.fehler
        assert a.naechster_versuch == jetzt + timedelta(minutes=pause)
        assert auftrag_ausfuehren(a.pk, jetzt) == "uebersprungen"  # vor dem nächsten Versuch: nichts
        jetzt = a.naechster_versuch
    assert auftrag_ausfuehren(a.pk, jetzt) == "gescheitert"
    a.refresh_from_db()
    assert a.status == Auftragsstatus.GESCHEITERT and a.versuche == 6 and a.naechster_versuch is None
    assert KILauf.objects.filter(erfolgreich=False).count() == 6  # jeder Fehlversuch steht im Archiv
    assert rechtsbezug_lage(antrag)["zustand"] == "gescheitert"
    assert warteschlange_stand()["zwecke"][0]["gescheitert"] == 1


def test_stummer_steckplatz_wegen_budget_zaehlt_keinen_versuch(attrappe, ordnung):  # noqa: F811
    from parameter.models import Parameter

    Parameter.objects.create(schluessel="ki-monatstokens", wert="1", beschreibung="x", quelle="Test")
    KILauf.objects.create(zweck=Zweck.EINSCHAETZUNG, angefordert_von=mitglied_anlegen("x"), eingabe="", anbieter="a", modell="m", tokens_ein=5)
    a = einreihen(Zweck.RECHTSBEZUG, _antrag(ordnung), mitglied_anlegen("y"))
    stand = abarbeiten()
    assert stand.get("budget_erschoepft") is True
    a.refresh_from_db()
    assert a.versuche == 0


def test_budget_das_mitten_im_stapel_ausgeht_kostet_keinen_versuch(json_attrappe, ordnung):  # noqa: F811
    """Verbraucht der erste Auftrag des Stapels den Rest des Monatsbudgets, bricht der Stapel ab — der
    zweite wartet ohne gezählten Versuch, statt nach sechs Monatsenden „gescheitert“ zu heißen."""
    from parameter.models import Parameter

    Parameter.objects.create(schluessel="ki-monatstokens", wert="25", beschreibung="x", quelle="Test")  # ein Lauf: 30
    for i in range(2):
        einreihen(Zweck.RECHTSBEZUG, _antrag(ordnung, f"b{i}", f"Budget {i}"), mitglied_anlegen(f"y{i}"))
    stand = abarbeiten()
    assert stand["erledigt"] == 1 and stand["verschoben"] == 0 and stand.get("budget_erschoepft") is True
    zweiter = KIAuftrag.objects.order_by("pk").last()
    assert zweiter.versuche == 0 and zweiter.status == Auftragsstatus.GEPLANT and zweiter.naechster_versuch is None


def test_programmfehler_im_auftrag_toetet_den_lauf_nicht(attrappe, ordnung, monkeypatch):  # noqa: F811
    monkeypatch.setitem(warteschlange.ARBEIT, Zweck.RECHTSBEZUG, lambda auftrag: 1 / 0)
    a = einreihen(Zweck.RECHTSBEZUG, _antrag(ordnung), mitglied_anlegen("x"))
    assert auftrag_ausfuehren(a.pk) == "verschoben"
    a.refresh_from_db()
    assert a.fehler.startswith("ZeroDivisionError")


def test_auftrag_aehnlichkeit_zieht_den_textvektor_nach(attrappe, ordnung):  # noqa: F811
    antrag = _antrag(ordnung)
    einreihen(Zweck.AEHNLICHKEIT, antrag, antrag.eingebracht_von)
    assert abarbeiten()["erledigt"] == 1
    zeile = antrag.einbettungen.get()
    assert zeile.fassung_nummer == 1 and zeile.modell == "attrappe-einbettung-1" and len(zeile.vektor) == 64
    assert KILauf.objects.get().zweck == Zweck.AEHNLICHKEIT


def test_auftraege_rechnen_mit_dem_text_ihrer_fassung(attrappe, ordnung):  # noqa: F811
    """Bekommt der Antrag vor dem Abarbeiten eine neue Fassung, rechnet der Auftrag zu Fassung 1 trotzdem
    mit dem Text von Fassung 1 — sonst stünden Ergebnis und Vektor unter der falschen Fassungsnummer."""
    from ki.anbieter import attrappen_vektor
    from verfahren.aehnlichkeit import antragstext
    from verfahren.models import AntragsFassung

    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    einreihen(Zweck.AEHNLICHKEIT, antrag, antrag.eingebracht_von)
    AntragsFassung.objects.create(antrag=antrag, nummer=2, wortlaut="Ganz anderer Text über Nachtzüge nach Linz.")
    assert abarbeiten()["erledigt"] == 2
    lauf = KILauf.objects.get(zweck=Zweck.RECHTSBEZUG)
    assert ANTRAG["wortlaut"] in lauf.eingabe and "Nachtzüge" not in lauf.eingabe
    zeile = antrag.einbettungen.get()
    assert zeile.fassung_nummer == 1
    assert zeile.vektor == attrappen_vektor(antragstext(antrag, 1)) != attrappen_vektor(antragstext(antrag))


def test_der_hintergrundlauf_zukunftswerkstatt_arbeitet_die_schlange_ab(json_attrappe, ordnung):  # noqa: F811
    antrag = _antrag(ordnung)
    einreihen(Zweck.RECHTSBEZUG, antrag, antrag.eingebracht_von)
    assert "zukunftswerkstatt" in hintergrund.faellige_ausfuehren()
    zeile = Hintergrundlauf.objects.get(name="zukunftswerkstatt")
    assert zeile.zuletzt_stand["erledigt"] == 1 and zeile.fehler == ""
    assert rechtsbezug_fuer(antrag) is not None


def test_anbieterfehler_ohne_programmfehler_wird_nicht_als_ausnahme_geloggt(attrappe, ordnung, monkeypatch, caplog):  # noqa: F811
    def stumm(self, auftrag, eingabe):
        raise SteckplatzStumm("Der Anbieter hat nicht geantwortet")

    monkeypatch.setattr(AttrappenAnbieter, "frage", stumm)
    a = einreihen(Zweck.RECHTSBEZUG, _antrag(ordnung), mitglied_anlegen("x"))
    assert auftrag_ausfuehren(a.pk) == "verschoben"
    assert "gescheitert" not in caplog.text


# --- Der tolerante Parser -------------------------------------------------------------------------


def test_parser_zieht_json_aus_zaeunen_und_umgebendem_text():
    text = "Hier das Ergebnis:\n```json\n" + JSON_ANTWORT + "\n```\nViel Erfolg."
    e = antwort_parsen(text)
    assert e["roh"] is False and len(e["normen"]) == 2 and e["hinweis"].startswith("Bundeskompetenz")


def test_parser_haelt_kaputtes_json_als_rohen_hinweis_fest():
    e = antwort_parsen('{"normen": [{"titel": "Abgebrochen…')
    assert e["roh"] is True and e["normen"] == [] and e["unsicherheit"] == "hoch" and "Abgebrochen" in e["hinweis"]
    assert antwort_parsen("")["hinweis"] == ""
    assert antwort_parsen("Keine Ahnung.")["hinweis"] == "Keine Ahnung."
    assert antwort_parsen('["liste"]')["roh"] is True
    assert antwort_parsen('{"normen": "kein array", "unsicherheit": "extrem"}') == {
        "normen": [],
        "hinweis": "",
        "unsicherheit": "hoch",
        "roh": False,
    }


def test_parser_begrenzt_die_zahl_der_normen():
    viele = json.dumps({"normen": [{"titel": f"Norm {i}"} for i in range(30)]})
    assert len(antwort_parsen(viele)["normen"]) == 12
