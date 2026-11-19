"""Der Ähnlichkeitshinweis beim Einbringen mit beiden Stufen (FB-H2, ADR-011): Wortvergleich ohne Modell,
Bedeutung über die Attrappe, stiller Rückfall ohne Anbieter, ein Aufruf je Einbringen, gespeicherte
Vektoren, Erbschaft der Rechtsbezug-Normen, Warteschlange nach „Trotzdem einbringen“. Nie Netz."""

import json

import pytest
from django.urls import reverse

from ki.anbieter import AttrappenAnbieter
from ki.models import KIAuftrag, KILauf, Zweck
from parameter.models import Parameter
from verfahren.aehnlichkeit import aehnliche_antraege
from verfahren.models import Antrag, AntragsEinbettung, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

FREMD = {
    "titel": "Börsennotierung von Rüstungs- und Pharmaunternehmen einschränken",
    "wortlaut": "Die Bundesregierung wird aufgefordert, dem Nationalrat umgehend einen Gesetzesentwurf vorzulegen, "
    "der die Börsennotierung von Rüstungs- und Pharmaunternehmen an strenge Auflagen bindet.",
    "begruendung": "Transparenz.",
}
UMFORMULIERT = {
    "titel": "Ratssitzungsprotokolle innerhalb von 48 Stunden veröffentlichen",
    "wortlaut": "Alle Protokolle der Ratssitzungen der DDÖ werden binnen 48 Stunden veröffentlicht.",
    "begruendung": "Transparenz.",
}


def _register(schluessel, wert):
    Parameter.objects.update_or_create(schluessel=schluessel, defaults={"wert": str(wert), "beschreibung": "x", "quelle": "Test"})


@pytest.fixture
def bestehend(ordnung):  # noqa: F811
    return antrag_einbringen(mitglied_anlegen("autorin"), ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)


# --- Stufe 1b im Browser ------------------------------------------------------------------------


def test_ein_fremder_antrag_bekommt_keinen_hinweis_mehr(client, bestehend):
    """Die Anweisung des Gründers: kein Treffer ohne inhaltliche Nähe — Fassung 1 meldete 29 Prozent."""
    client.force_login(mitglied_anlegen("bernd"))
    antwort = client.post(reverse("verfahren:einbringen"), FREMD)
    assert antwort.status_code == 302 and Antrag.objects.count() == 2
    assert antwort.url.endswith(f"/antrag/{Antrag.objects.latest('pk').pk}/?neu=1")


def test_ein_umformulierter_antrag_bekommt_den_hinweis_mit_wortvergleich(client, bestehend):
    client.force_login(mitglied_anlegen("bernd"))
    antwort = client.post(reverse("verfahren:einbringen"), UMFORMULIERT)
    assert antwort.status_code == 200 and Antrag.objects.count() == 1
    treffer = antwort.context["aehnliche"]
    assert treffer[0]["antrag"] == bestehend and treffer[0]["prozent"] >= 40
    assert treffer[0]["bedeutung_prozent"] is None  # ohne Anbieter keine Bedeutungsstufe
    inhalt = antwort.content.decode()
    assert "Wortvergleich" in inhalt and "Bedeutung " not in inhalt
    assert "der Modell-Steckplatz war stumm" in inhalt  # ehrlich gesagt, nicht verschwiegen
    assert "Mein Antrag ist etwas anderes — einbringen" in inhalt


def test_die_schwelle_kommt_aus_dem_register(client, bestehend):
    _register("aehnlichkeit-schwelle-prozent", 99)
    client.force_login(mitglied_anlegen("bernd"))
    assert client.post(reverse("verfahren:einbringen"), UMFORMULIERT).status_code == 302


# --- Stufe 2 mit der Attrappe --------------------------------------------------------------------


def test_bedeutung_laeuft_mit_einem_aufruf_und_speichert_die_vektoren(client, settings, bestehend):
    settings.DDOE_KI_ANBIETER = "attrappe"
    client.force_login(mitglied_anlegen("bernd"))
    antwort = client.post(reverse("verfahren:einbringen"), UMFORMULIERT)
    assert antwort.status_code == 200
    t = antwort.context["aehnliche"][0]
    assert t["bedeutung_prozent"] is not None and 0 <= t["bedeutung_prozent"] <= 100
    inhalt = antwort.content.decode()
    assert f"Wortvergleich {t['prozent']} % · Bedeutung {t['bedeutung_prozent']} %" in inhalt
    assert "attrappe-einbettung-1" in inhalt and "Vorschlag, keine Hürde" in inhalt
    # Ein Aufruf: neuer Text + der eine Antrag ohne Vektor; der bestehende Antrag hat jetzt seinen Vektor
    assert KILauf.objects.filter(zweck=Zweck.AEHNLICHKEIT).count() == 1
    assert AntragsEinbettung.objects.filter(antrag=bestehend, fassung_nummer=1, modell="attrappe-einbettung-1").exists()
    # Zweiter Versuch: der Vektor liegt vor, nur der neue Text wird eingebettet
    client.post(reverse("verfahren:einbringen"), UMFORMULIERT)
    lauf = KILauf.objects.filter(zweck=Zweck.AEHNLICHKEIT).order_by("-pk").first()
    assert KILauf.objects.filter(zweck=Zweck.AEHNLICHKEIT).count() == 2 and "---" not in lauf.eingabe


def test_ein_bedeutungstreffer_zaehlt_auch_ohne_wortvergleich(client, settings, bestehend):
    """Vereinigung beider Stufen: Wortschwelle unerreichbar hoch, Bedeutungsschwelle niedrig — der
    Treffer kommt allein über die Bedeutung, sortiert nach dem höheren Wert."""
    settings.DDOE_KI_ANBIETER = "attrappe"
    _register("aehnlichkeit-schwelle-prozent", 100)
    _register("aehnlichkeit-bedeutung-schwelle-prozent", 30)
    client.force_login(mitglied_anlegen("bernd"))
    antwort = client.post(reverse("verfahren:einbringen"), UMFORMULIERT)
    assert antwort.status_code == 200
    t = antwort.context["aehnliche"][0]
    assert t["prozent"] < 100 and t["bedeutung_prozent"] >= 30


def test_neuer_antrag_speichert_seinen_vektor_ohne_zweiten_aufruf(client, settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    antrag_einbringen(mitglied_anlegen("autorin"), ANTRAG["titel"], ANTRAG["wortlaut"], "", ordnung)
    client.force_login(mitglied_anlegen("bernd"))
    antwort = client.post(reverse("verfahren:einbringen"), FREMD)
    assert antwort.status_code == 302
    neu = Antrag.objects.latest("pk")
    assert neu.einbettungen.filter(fassung_nummer=1).exists()
    assert KILauf.objects.filter(zweck=Zweck.AEHNLICHKEIT).count() == 1  # kein zweiter Aufruf
    assert not KIAuftrag.objects.filter(zweck=Zweck.AEHNLICHKEIT).exists()  # und kein Auftrag nötig
    assert KIAuftrag.objects.filter(zweck=Zweck.RECHTSFOLGEN, antrag=neu).exists()  # ein kombinierter Bericht
    assert not KIAuftrag.objects.filter(zweck=Zweck.RECHTSBEZUG, antrag=neu).exists()


def test_trotzdem_einbringen_reiht_den_vektor_in_die_warteschlange(client, settings, bestehend):
    settings.DDOE_KI_ANBIETER = "attrappe"
    client.force_login(mitglied_anlegen("bernd"))
    antwort = client.post(reverse("verfahren:einbringen"), {**UMFORMULIERT, "trotzdem": "1"})
    assert antwort.status_code == 302
    neu = Antrag.objects.latest("pk")
    assert not neu.einbettungen.exists()
    assert KIAuftrag.objects.filter(zweck=Zweck.AEHNLICHKEIT, antrag=neu).exists()
    assert KIAuftrag.objects.filter(zweck=Zweck.RECHTSFOLGEN, antrag=neu).exists()


def test_ohne_anbieter_wird_kein_vektor_auftrag_eingereiht(client, bestehend):
    client.force_login(mitglied_anlegen("bernd"))
    client.post(reverse("verfahren:einbringen"), {**UMFORMULIERT, "trotzdem": "1"})
    neu = Antrag.objects.latest("pk")
    assert not KIAuftrag.objects.filter(zweck=Zweck.AEHNLICHKEIT).exists()
    assert KIAuftrag.objects.filter(zweck=Zweck.RECHTSFOLGEN, antrag=neu).exists()  # wartet auf einen Anbieter


def test_stummer_anbieter_faellt_still_auf_den_wortvergleich_zurueck(client, settings, bestehend, monkeypatch):
    settings.DDOE_KI_ANBIETER = "attrappe"

    def kaputt(self, texte, zeitgrenze=None):
        from ki.anbieter import AnbieterFehler

        raise AnbieterFehler("HTTP 500 vom Anbieter")

    monkeypatch.setattr(AttrappenAnbieter, "einbetten", kaputt)
    client.force_login(mitglied_anlegen("bernd"))
    antwort = client.post(reverse("verfahren:einbringen"), UMFORMULIERT)
    assert antwort.status_code == 200
    t = antwort.context["aehnliche"][0]
    assert t["bedeutung_prozent"] is None and t["prozent"] >= 40
    assert KILauf.objects.get(zweck=Zweck.AEHNLICHKEIT).erfolgreich is False  # der Fehlversuch steht im Archiv


def test_in_der_anfrage_gilt_eine_kurze_zeitgrenze_die_warteschlange_behaelt_die_lange(client, settings, bestehend, monkeypatch):
    """Ein schweigender Anbieter hält „Einbringen“ nicht 45 s je Socket-Operation fest: In der Anfrage
    gilt die kurze Zeitgrenze der Bedeutungsstufe; die Warteschlange rechnet ohne wartende Person."""
    from ki.anbieter import ZEITGRENZE_SEKUNDEN
    from ki.test_einbettung import _Scheinantwort
    from ki.warteschlange import abarbeiten, einreihen

    settings.DDOE_KI_ANBIETER = "mistral"
    settings.DDOE_KI_SCHLUESSEL = "nur-fuer-den-test"
    zeitgrenzen = []

    def schein_urlopen(anfrage, timeout=None):
        zeitgrenzen.append(timeout)
        texte = json.loads(anfrage.data.decode())["input"]
        daten = {"model": "mistral-embed", "data": [{"index": i, "embedding": [1.0, 0.0]} for i in range(len(texte))]}
        return _Scheinantwort(json.dumps(daten).encode())

    monkeypatch.setattr("urllib.request.urlopen", schein_urlopen)
    client.force_login(mitglied_anlegen("bernd"))
    client.post(reverse("verfahren:einbringen"), UMFORMULIERT)
    assert len(zeitgrenzen) == 1 and zeitgrenzen[0] < 10  # die Anfrage: kurz
    einreihen(Zweck.AEHNLICHKEIT, bestehend, bestehend.eingebracht_von)
    abarbeiten()
    assert zeitgrenzen[1:] == [ZEITGRENZE_SEKUNDEN]  # die Warteschlange: die lange


def test_bedeutungsstufe_ist_je_konto_und_stunde_gedrosselt(client, settings, bestehend, monkeypatch):
    """Jeder POST ohne „Trotzdem“ ruft sonst den Anbieter — ein Konto könnte per Skript das Monatsbudget
    leeren. Über der Grenze je Konto rechnet nur der Wortvergleich, und die Karte sagt es ehrlich."""
    from types import SimpleNamespace

    # Die Drossel zählt je voller Stunde; fielen die zehn POSTs über einen Stundenwechsel, zählte
    # ein neuer Eimer und der Test schlüge fehl. Die Uhr der Drossel steht deshalb still.
    monkeypatch.setattr("mitglieder.botschutz.time", SimpleNamespace(time=lambda: 3600 * 480_000 + 1800))
    settings.DDOE_KI_ANBIETER = "attrappe"
    laeufe = KILauf.objects.filter(zweck=Zweck.AEHNLICHKEIT)
    client.force_login(mitglied_anlegen("bernd"))
    for _ in range(10):
        antwort = client.post(reverse("verfahren:einbringen"), UMFORMULIERT)
        assert antwort.status_code == 200
    assert laeufe.count() < 10  # nicht jeder POST geht an den Anbieter
    from verfahren.aehnlichkeit import BEDEUTUNG_JE_KONTO_UND_STUNDE

    assert laeufe.count() == BEDEUTUNG_JE_KONTO_UND_STUNDE
    t = antwort.context["aehnliche"][0]
    assert t["bedeutung_prozent"] is None and t["prozent"] >= 40  # der Wortvergleich bleibt
    inhalt = antwort.content.decode()
    assert "Bedeutungsvergleich diesmal nicht gerechnet" in inhalt and "Steckplatz war stumm" not in inhalt
    client.force_login(mitglied_anlegen("clara"))  # je Konto, nicht je Verbindung
    assert client.post(reverse("verfahren:einbringen"), UMFORMULIERT).context["aehnliche"][0]["bedeutung_prozent"] is not None
    assert laeufe.count() == BEDEUTUNG_JE_KONTO_UND_STUNDE + 1


def test_belegter_steckplatz_verbraucht_kein_stundenkontingent(client, settings, bestehend, monkeypatch):
    """GP-207 (ZWA-23): Ohne Anbieteraufruf zählt die Drossel nicht — fünf Versuche bei belegtem Zugang
    lassen den Zähler bei 0, der sechste bei freiem Zugang ruft den Anbieter."""
    from types import SimpleNamespace

    from ki.models import SteckplatzZugang
    from mitglieder.models import Drosselzaehler

    monkeypatch.setattr('mitglieder.botschutz.time', SimpleNamespace(time=lambda: 3600 * 480_000 + 1800))
    settings.DDOE_KI_ANBIETER = 'attrappe'
    bernd = mitglied_anlegen('bernd')
    client.force_login(bernd)
    SteckplatzZugang.objects.update_or_create(name='anbieter', defaults={'belegt': True})
    for _ in range(5):
        assert client.post(reverse('verfahren:einbringen'), UMFORMULIERT).status_code == 200
    zaehler = Drosselzaehler.objects.filter(zweck='bedeutung', kennung=f'konto:{bernd.pk}')
    assert sum(zaehler.values_list('anzahl', flat=True)) == 0
    assert not KILauf.objects.filter(zweck=Zweck.AEHNLICHKEIT).exists()
    SteckplatzZugang.objects.filter(name='anbieter').update(belegt=False)
    antwort = client.post(reverse('verfahren:einbringen'), UMFORMULIERT)
    assert antwort.context['aehnliche'][0]['bedeutung_prozent'] is not None
    assert KILauf.objects.filter(zweck=Zweck.AEHNLICHKEIT).count() == 1


def test_zeitgrenze_und_drossel_kommen_aus_dem_register(client, settings, bestehend, monkeypatch):
    """Entscheidung des Gründers 29.9.2026: Zeitgrenze und Drossel der Bedeutungsstufe sind Registerwerte."""
    from types import SimpleNamespace

    from ki.test_einbettung import _Scheinantwort

    Parameter.objects.create(schluessel="aehnlichkeit-zeitgrenze-sekunden", wert="3", beschreibung="x", quelle="Test")
    Parameter.objects.create(schluessel="aehnlichkeit-bedeutung-je-stunde", wert="2", beschreibung="x", quelle="Test")
    monkeypatch.setattr("mitglieder.botschutz.time", SimpleNamespace(time=lambda: 3600 * 480_000 + 1800))
    settings.DDOE_KI_ANBIETER = "mistral"
    settings.DDOE_KI_SCHLUESSEL = "nur-fuer-den-test"
    zeitgrenzen = []

    def schein_urlopen(anfrage, timeout=None):
        zeitgrenzen.append(timeout)
        texte = json.loads(anfrage.data.decode())["input"]
        daten = {"model": "mistral-embed", "data": [{"index": i, "embedding": [1.0, 0.0]} for i in range(len(texte))]}
        return _Scheinantwort(json.dumps(daten).encode())

    monkeypatch.setattr("urllib.request.urlopen", schein_urlopen)
    client.force_login(mitglied_anlegen("bernd"))
    for _ in range(4):
        client.post(reverse("verfahren:einbringen"), UMFORMULIERT)
    assert zeitgrenzen == [3, 3]  # zwei Aufrufe mit der Zeitgrenze aus dem Register, dann gedrosselt


def test_nachziehen_ist_je_aufruf_begrenzt(settings, ordnung):  # noqa: F811
    settings.DDOE_KI_ANBIETER = "attrappe"
    _register("aehnlichkeit-einbettungen-je-aufruf", 2)
    m = mitglied_anlegen("autorin")
    for i in range(4):
        antrag_einbringen(m, f"Antrag Nummer {i}", f"Wortlaut {i} über Radwege und Gemeinden.", "", ordnung)
    ergebnis = aehnliche_antraege("Radwege", "Radwege in Gemeinden", m)
    assert ergebnis.bedeutung_aktiv and AntragsEinbettung.objects.count() == 2
    aehnliche_antraege("Radwege", "Radwege in Gemeinden", m)
    assert AntragsEinbettung.objects.count() == 4  # der Rest folgt beim nächsten Einbringen


def test_mandats_kandidaturen_bleiben_ohne_pruefung_und_ohne_auftrag(client, settings, ordnung):  # noqa: F811
    from mandatare.models import Mandat  # noqa: F401 — die Kandidatur braucht die App

    settings.DDOE_KI_ANBIETER = "attrappe"
    client.force_login(mitglied_anlegen("bernd"))
    antwort = client.post(reverse("verfahren:einbringen"), {**ANTRAG, "art": "mandat"})
    assert antwort.status_code == 302
    assert not KIAuftrag.objects.exists() and not KILauf.objects.exists()


def test_personenantraege_gehen_nie_an_den_anbieter(client, settings, monkeypatch, ordnung):  # noqa: F811
    """GP-023 (ZWA-07): Über Personen rechnet keine Maschine (FB-F4, ADR-011). Titel und Wortlaut offener
    Vertrauensfragen und Kandidaturen gehen im Bedeutungsvergleich nicht an den Anbieter, landen nicht im
    Lauf-Archiv und bekommen keinen Vektor; vorhandene Vektoren werden nicht gelesen. Der Wortvergleich
    (ohne Modell) bleibt."""
    from verfahren.models import Antragsart

    settings.DDOE_KI_ANBIETER = 'attrappe'
    gesendet = []
    echt = AttrappenAnbieter.einbetten

    def horchen(self, texte, zeitgrenze=None):
        gesendet.extend(texte)
        return echt(self, texte, zeitgrenze=zeitgrenze)

    monkeypatch.setattr(AttrappenAnbieter, 'einbetten', horchen)
    import verfahren.aehnlichkeit as aehnlichkeit_modul

    verglichen = []
    echter_kosinus = aehnlichkeit_modul.kosinus

    def kosinus_horchen(a, b):
        verglichen.append(list(b))
        return echter_kosinus(a, b)

    monkeypatch.setattr(aehnlichkeit_modul, 'kosinus', kosinus_horchen)
    m = mitglied_anlegen('autorin')
    vf = antrag_einbringen(m, UMFORMULIERT['titel'] + ' Musterfrau', UMFORMULIERT['wortlaut'] + ' Versagung des Vertrauens.', '', ordnung)
    kandidatur = antrag_einbringen(m, 'Kandidatur Listenreihung Gemeinderat', 'Listenreihung Gemeinderat Polsenz. ' + UMFORMULIERT['wortlaut'], '', ordnung)
    Antrag.objects.filter(pk=vf.pk).update(art=Antragsart.VERTRAUENSFRAGE)
    Antrag.objects.filter(pk=kandidatur.pk).update(art=Antragsart.MANDAT)
    # ein früher gespeicherter Vektor zu einer Kandidatur wird nicht mehr gelesen
    AntragsEinbettung.objects.create(antrag=kandidatur, fassung_nummer=1, modell='attrappe-einbettung-1', vektor=[1.0, 0.0])
    sache = antrag_einbringen(m, ANTRAG['titel'], ANTRAG['wortlaut'], '', ordnung)
    client.force_login(mitglied_anlegen('bernd'))
    antwort = client.post(reverse('verfahren:einbringen'), UMFORMULIERT)
    assert antwort.status_code == 200
    alles = '\n'.join(gesendet) + '\n'.join(KILauf.objects.values_list('eingabe', flat=True))
    for verboten in ('Musterfrau', 'Versagung des Vertrauens', 'Listenreihung'):
        assert verboten not in alles
    assert not AntragsEinbettung.objects.filter(antrag=vf).exists()
    assert AntragsEinbettung.objects.filter(antrag=sache).exists()  # der Sachantrag bekommt seinen Vektor
    # der gespeicherte Vektor der Kandidatur geht in keinen Kosinus ein; der Sachantrag wird verglichen
    assert verglichen and [1.0, 0.0] not in verglichen
    treffer ={t['antrag'].pk: t for t in antwort.context['aehnliche']}
    assert kandidatur.pk not in treffer or treffer[kandidatur.pk]['bedeutung_prozent'] is None
    assert vf.pk not in treffer or treffer[vf.pk]['bedeutung_prozent'] is None
    # der Wortvergleich bleibt: ohne Anbieter findet er die Vertrauensfrage weiterhin
    wort = aehnliche_antraege(UMFORMULIERT['titel'], UMFORMULIERT['wortlaut'], m, bedeutung=False)
    assert vf.pk in {t['antrag'].pk for t in wort.treffer}


# --- Erbschaft: Treffer bringen ihre Rechtsbezug-Normen mit --------------------------------------


def test_treffer_zeigen_die_normen_des_bestehenden_antrags(client, bestehend):
    KILauf.objects.create(
        zweck=Zweck.RECHTSBEZUG,
        antrag=bestehend,
        angefordert_von=bestehend.eingebracht_von,
        eingabe="…",
        antwort=json.dumps({"normen": [{"titel": "Parteiengesetz 2012", "ebene": "Bund", "aenderung": "aendern"}], "unsicherheit": "niedrig"}),
        anbieter="attrappe",
        modell="attrappe-1",
        auftrag_version="rechtsbezug-v1",
    )
    client.force_login(mitglied_anlegen("bernd"))
    antwort = client.post(reverse("verfahren:einbringen"), UMFORMULIERT)
    inhalt = antwort.content.decode()
    assert antwort.context["aehnliche"][0]["normen"][0]["titel"] == "Parteiengesetz 2012"
    assert "Ein betroffenes Gesetz laut Zukunftswerkstatt" in inhalt and "Parteiengesetz 2012" in inhalt
    assert "nicht verifiziert" in inhalt and "rechtsbezug-v1" in inhalt
    assert "<details" in inhalt  # aufklappbar, ohne JavaScript bedienbar


def test_treffer_ohne_normen_zeigen_keine_klappe(client, bestehend):
    client.force_login(mitglied_anlegen("bernd"))
    inhalt = client.post(reverse("verfahren:einbringen"), UMFORMULIERT).content.decode()
    assert "laut Zukunftswerkstatt" not in inhalt


def test_karte_nennt_ihre_reihung_und_verlinkt_die_regel(client, bestehend):
    """GP-206 (ZWB-03): Die Karte sagt, wie sie reiht, und das Regelverzeichnis ist ein Link auf den
    vorhandenen Anker der Ähnlichkeitsregel."""
    client.force_login(mitglied_anlegen('bernd'))
    inhalt = client.post(reverse('verfahren:einbringen'), UMFORMULIERT).content.decode()
    ziel = reverse('parameter:regeln') + '#regel-similarity'
    assert f'href="{ziel}"' in inhalt
    assert 'gereiht nach dem höheren der beiden Werte' in inhalt
    assert 'id="regel-similarity"' in client.get(reverse('parameter:regeln')).content.decode()


def test_gp175_aehnlichkeitskarte_zaehlt_wiener_kalendertage(bestehend):
    """GP-175 (Rest): Die Ähnlichkeitskarte rundete `(frist - jetzt)` auf ganze 24 Stunden auf — 25 Stunden
    vor einem Fristende morgen stand „Noch 2 Tage“, nach dem Ende „Noch 0 Tage“ mit Knopf. Sie rechnet
    jetzt mit derselben Funktion wie Kachel und Zeile."""
    from datetime import datetime, timedelta
    from unittest import mock
    from zoneinfo import ZoneInfo

    from django.template.loader import render_to_string

    wien = ZoneInfo("Europe/Vienna")
    frist = datetime(2026, 11, 19, 12, 0, tzinfo=wien)
    tage = bestehend.policy().unterstuetzung_frist_tage
    Antrag.objects.filter(pk=bestehend.pk).update(phase_beginn=frist - timedelta(days=tage))

    def treffer(jetzt):
        with mock.patch("django.utils.timezone.now", return_value=jetzt):
            gefunden = aehnliche_antraege(ANTRAG["titel"], ANTRAG["wortlaut"], None, bedeutung=False).treffer
        return next(t for t in gefunden if t["antrag"].pk == bestehend.pk)

    vortag = treffer(datetime(2026, 11, 18, 11, 0, tzinfo=wien))  # 25 Stunden, aber morgen
    assert vortag["rest_tage"] == 1 and not vortag["frist_abgelaufen"]
    assert treffer(datetime(2026, 11, 19, 0, 5, tzinfo=wien))["rest_tage"] == 0
    danach = treffer(frist + timedelta(minutes=1))
    assert danach["rest_tage"] is None and danach["frist_abgelaufen"]

    html = render_to_string("verfahren/_aehnliche_antraege.html", {"aehnliche": [danach], "oertlich_gesperrte_treffer": []})
    assert "Frist abgelaufen, wird ausgewertet" in html
    assert f'name="unterstuetzen" value="{bestehend.pk}"' not in html
    html = render_to_string("verfahren/_aehnliche_antraege.html", {"aehnliche": [vortag], "oertlich_gesperrte_treffer": []})
    assert "Noch 1 Tag" in html and f'name="unterstuetzen" value="{bestehend.pk}"' in html
