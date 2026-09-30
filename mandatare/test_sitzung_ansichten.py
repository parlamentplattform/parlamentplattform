"""Die Ansichten des Sitzungsmodus (FB-L5): Karte im Bereich, öffentliche Live-Seite, /live/, Chat der
Sitzung, Kachel „Live“ in „Meine Region“, Rechenschaft und Sammelbericht aus dem Ticker — mit der
Rechte-Matrix (Gast, Mitglied, ungeprüft, fremder und ruhender Mandatar) und ohne JavaScript."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from mandatare.models import Livemeldung, Mandat, Rechenschaft, Sitzung
from mandatare.sitzung import meldung_abgeben, sitzung_beenden, sitzung_beginnen
from mandatare.test_mandatare import mandat_anlegen
from mandatare.test_sitzung_modelle import sitzungstag
from mitglieder.models import Identitaetsstufe
from plattform_core import Phase
from verfahren.chat import sitzung_beitrag_schreiben
from verfahren.models import AuditEintrag, Kommentar, Meldung, antrag_einbringen
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

AKTION = reverse("mandatare:mein_aktion")
UEBERSICHT = reverse("mandatare:live_uebersicht")


def live_url(mandat, sitzung=None, **extra):
    url = reverse("mandatare:live", args=[mandat.pk])
    teile = ([f"sitzung={sitzung.pk}"] if sitzung else []) + [f"{k}={v}" for k, v in extra.items()]
    return url + ("?" + "&".join(teile) if teile else "")


@pytest.fixture
def anna(client):
    m = mitglied_anlegen("anna")
    mandat = mandat_anlegen(m)
    client.force_login(m)
    return mandat


def post(client, mandat, aktion, **daten):
    return client.post(AKTION, {"aktion": aktion, "mandat": mandat.pk, **daten}, follow=True)


# ── Bereich des Mandatars ─────────────────────────────────────────────────────────────────


def test_karte_zeigt_den_heutigen_sitzungstag_zuerst(client, anna):
    aufgabe = sitzungstag(anna)
    html = client.get(reverse("mandatare:mein")).content.decode()
    assert 'id="sitzung"' in html and 'value="sitzung_beginnen"' in html
    assert f'<option value="{aufgabe.pk}">' in html
    assert html.index('id="sitzung"') < html.index('id="karte"')  # am Sitzungstag zuerst


def test_ohne_sitzungstag_steht_die_karte_hinten(client, anna):
    html = client.get(reverse("mandatare:mein")).content.decode()
    assert 'id="sitzung"' in html and 'value="sitzung_beginnen"' not in html
    assert html.index('id="sitzung"') > html.index('id="berichte"')


def test_live_modus_ueber_den_bereich(client, anna):
    aufgabe = sitzungstag(anna)
    antwort = post(client, anna, "sitzung_beginnen", aufgabe=aufgabe.pk, stream="https://tv.example.org/gr",
                   tagesordnung="Budget 2027\n\nRadweg\n")
    assert antwort.status_code == 200
    sitzung = Sitzung.objects.get()
    assert [p.titel for p in sitzung.punkte.all()] == ["Budget 2027", "Radweg"]
    html = antwort.content.decode()
    assert 'value="sitzung_meldung"' in html and "Beschlusslage" in html
    punkt = sitzung.punkte.get(nummer=2)
    post(client, anna, "sitzung_meldung", punkt=punkt.pk, text="Ich stimme für den Radweg.", stimme="dafuer")
    alt = Livemeldung.objects.get()
    post(client, anna, "sitzung_meldung", punkt=punkt.pk, text="Abgestimmt: dafür.", stimme="dafuer",
         abgestimmt="on", berichtigt=alt.pk)
    assert Livemeldung.objects.filter(berichtigt=alt, abgestimmt=True).exists()
    post(client, anna, "sitzung_punkt", titel="Allfälliges")
    assert sitzung.punkte.count() == 3
    post(client, anna, "sitzung_stream", stream="https://tv.example.org/neu")
    assert Sitzung.objects.get().stream == "https://tv.example.org/neu"
    antwort = post(client, anna, "sitzung_stream", stream="http://unsicher.example.org")
    assert "https://" in antwort.content.decode() and Sitzung.objects.get().stream == "https://tv.example.org/neu"
    post(client, anna, "sitzung_beenden")
    assert not Sitzung.objects.get().laeuft()
    assert {e.ereignis["typ"] for e in AuditEintrag.objects.all()} >= {
        "sitzung_begonnen", "livemeldung", "tagesordnungspunkt", "sitzung_stream", "sitzung_beendet"
    }


def test_verknuepfen_nur_sach_und_mandatsfragen(client, anna, ordnung):  # noqa: F811
    sitzung = sitzung_beginnen(anna, sitzungstag(anna), punkte=["Budget"])
    punkt = sitzung.punkte.get()
    kandidatur = antrag_einbringen(anna.mitglied, "Liste", "Reihung.", "", ordnung, art="mandat")
    antwort = post(client, anna, "sitzung_verknuepfen", punkt=punkt.pk, antrag=kandidatur.pk)
    assert "keine Sach- oder Mandatsfrage" in antwort.content.decode()
    sache = antrag_einbringen(anna.mitglied, "Budget", "Das Budget.", "", ordnung)
    post(client, anna, "sitzung_verknuepfen", punkt=punkt.pk, antrag=f"#{sache.pk}")
    punkt.refresh_from_db()
    assert punkt.antrag == sache


def test_fremder_mandatar_und_gast(client, anna):
    sitzung = sitzung_beginnen(anna, sitzungstag(anna))
    client.logout()
    assert client.post(AKTION, {"aktion": "sitzung_meldung", "mandat": anna.pk, "text": "x"}).status_code == 302
    bernd = mitglied_anlegen("bernd")
    mandat_anlegen(bernd)
    client.force_login(bernd)
    assert client.post(AKTION, {"aktion": "sitzung_meldung", "mandat": anna.pk, "text": "x"}).status_code == 403
    assert not sitzung.meldungen.exists()


def test_ungepruefte_identitaet_schreibt_nicht(client):
    m = mitglied_anlegen("cora", stufe=Identitaetsstufe.UNGEPRUEFT)
    mandat = mandat_anlegen(m)
    sitzungstag(mandat)
    client.force_login(m)
    html = client.get(reverse("mandatare:mein")).content.decode()
    assert 'value="sitzung_beginnen"' not in html
    assert client.post(AKTION, {"aktion": "sitzung_beginnen", "mandat": mandat.pk}).status_code == 403
    assert not Sitzung.objects.exists()


def test_ruhende_befugnis_zeigt_kein_formular(client, anna):
    aufgabe = sitzungstag(anna)
    Mandat.objects.filter(pk=anna.pk).update(vertrauen_entzogen_am=timezone.now())
    html = client.get(reverse("mandatare:mein")).content.decode()
    assert 'value="sitzung_beginnen"' not in html
    antwort = post(client, anna, "sitzung_beginnen", aufgabe=aufgabe.pk)
    assert "nicht ruhender Befugnis" in antwort.content.decode() and not Sitzung.objects.exists()


# ── Öffentlich ────────────────────────────────────────────────────────────────────────────


def test_live_seite_fuer_gaeste_mit_neuladen_ohne_javascript(client, anna, ordnung):  # noqa: F811
    sitzung = sitzung_beginnen(anna, sitzungstag(anna), stream="https://tv.example.org/gr", punkte=["Budget"])
    meldung_abgeben(sitzung, "Es beginnt.", sitzung.punkte.get(), "dafuer")
    client.logout()
    html = client.get(live_url(anna)).content.decode()
    assert "Es beginnt." in html and "Budget" in html and 'id="m-' in html
    assert '<noscript><meta http-equiv="refresh" content="15"></noscript>' in html
    assert 'hx-trigger="every 15s' in html
    assert 'href="https://tv.example.org/gr" rel="noopener noreferrer external"' in html
    assert "<iframe" not in html and "<video" not in html  # nur ein Link, kein Player (D-L5a)
    assert "Anmelden zum Mitschreiben" in html
    # beim Schreiben ohne JavaScript lädt nichts neu
    assert "http-equiv" not in client.get(live_url(anna, sitzung, schreiben=1)).content.decode()


def test_nach_dem_ende_ist_die_seite_das_protokoll(client, anna):
    sitzung = sitzung_beginnen(anna, sitzungstag(anna))
    meldung_abgeben(sitzung, "Letzte Meldung.")
    sitzung_beenden(sitzung)
    html = client.get(live_url(anna)).content.decode()
    assert "Letzte Meldung." in html and "Protokoll" in html
    assert "http-equiv" not in html and "hx-trigger" not in html


def test_takt_aus_dem_register(client, anna):
    from parameter.models import Parameter, erstbestand_sicherstellen

    erstbestand_sicherstellen()
    Parameter.objects.filter(schluessel="live-takt-sekunden").update(wert="2")  # unter 5 → 5
    sitzung_beginnen(anna, sitzungstag(anna))
    html = client.get(live_url(anna)).content.decode()
    assert 'content="5"' in html and "every 5s" in html


def test_beschlusslage_ohne_zwischenstand(client, anna, ordnung):  # noqa: F811
    """§ 5 Abs 3 lit d, D-D2: Eine laufende Abstimmung zeigt, bis wann — nicht, wie es steht."""
    from verfahren.models import mandatsfrage_eroeffnen

    frage_aufgabe = sitzungstag(anna, timezone.localdate() + timedelta(days=30), titel="Radweg?")
    frage = mandatsfrage_eroeffnen(anna, frage_aufgabe, "Radweg?", "Soll ich zustimmen?", ordnung)
    angenommen = antrag_einbringen(anna.mitglied, "Budget", "Das Budget.", "", ordnung)
    angenommen.phase = Phase.ANGENOMMEN.value
    angenommen.save()
    sitzung = sitzung_beginnen(anna, sitzungstag(anna), punkte=["Budget", "Radweg", "Allfälliges"])
    p1, p2, _ = sitzung.punkte.order_by("nummer")
    p1.antrag, p2.antrag = angenommen, frage
    p1.save()
    p2.save()
    html = client.get(live_url(anna)).content.decode()
    assert "lage-angenommen" in html and "lage-abstimmung" in html and "lage-kein_antrag" in html
    assert "Stimmen" not in html.split('id="live-stand"')[1].split('id="live-chat"')[0]


def test_uebersicht(client, anna):
    laufend = sitzung_beginnen(anna, sitzungstag(anna, titel="Gemeinderat heute"))
    bernd = mandat_anlegen(mitglied_anlegen("bernd"), bezeichnung="Landtag", ebene="land", gebiet="Oberösterreich")
    alt = sitzung_beginnen(bernd, sitzungstag(bernd, titel="Landtag alt"))
    sitzung_beenden(alt)
    Sitzung.objects.filter(pk=alt.pk).update(beginn=timezone.now() - timedelta(days=9), ende=timezone.now() - timedelta(days=9))
    frisch = sitzung_beginnen(bernd, sitzungstag(bernd, titel="Landtag frisch"))
    sitzung_beenden(frisch)
    html = client.get(UEBERSICHT).content.decode()
    assert "Gemeinderat heute" in html and "Landtag frisch" in html and "Landtag alt" not in html
    assert html.index("Gemeinderat heute") < html.index("Landtag frisch")
    assert f"?sitzung={laufend.pk}" in html


def test_kachel_live_in_meiner_region(client, anna):
    sitzung_beginnen(anna, sitzungstag(anna))
    bernd = mitglied_anlegen("bernd")  # wohnt in derselben Gemeinde
    client.force_login(bernd)
    html = client.get(reverse("verfahren:parlament")).content.decode()
    assert 'class="kachel live"' in html and live_url(anna).split("?")[0] in html
    fremd = mitglied_anlegen("dora", gemeinde="Wels")
    client.force_login(fremd)
    assert 'class="kachel live"' not in client.get(reverse("verfahren:parlament")).content.decode()


# ── Chat der Sitzung ──────────────────────────────────────────────────────────────────────


def test_chat_schreiben_melden_zurueckziehen_beantworten(client, anna):
    sitzung = sitzung_beginnen(anna, sitzungstag(anna))
    beitrag_url = reverse("mandatare:live_beitrag", args=[anna.pk, sitzung.pk])
    client.logout()
    assert client.post(beitrag_url, {"text": "Gast"}).status_code == 302  # zur Anmeldung
    bernd = mitglied_anlegen("bernd")
    client.force_login(bernd)
    antwort = client.post(beitrag_url, {"text": "Wie stimmen Sie zum Budget?"})
    frage = Kommentar.objects.get(sitzung=sitzung)
    assert antwort.status_code == 302 and antwort["Location"].endswith(f"#k-{frage.pk}")
    client.post(beitrag_url, {"text": "Nachfrage", "antwort_auf": frage.pk})
    assert Kommentar.objects.filter(antwort_auf=frage).count() == 1
    aktion = reverse("mandatare:live_beitrag_aktion", args=[anna.pk, sitzung.pk, frage.pk])
    assert client.post(aktion, {"aktion": "beantwortet"}).status_code == 403  # nur der Mandatar
    cora = mitglied_anlegen("cora")
    client.force_login(cora)
    client.post(aktion, {"aktion": "melden", "grund": Meldung.Grund.values[0]})
    assert Meldung.objects.filter(kommentar=frage, mitglied=cora).exists()
    assert client.post(aktion, {"aktion": "entfernen"}).status_code == 403  # nicht der eigene
    client.force_login(anna.mitglied)
    client.post(aktion, {"aktion": "beantwortet"})
    frage.refresh_from_db()
    assert frage.beantwortet_am is not None
    client.force_login(bernd)
    client.post(aktion, {"aktion": "entfernen"})
    frage.refresh_from_db()
    assert frage.geloescht and Kommentar.objects.filter(pk=frage.pk).exists()  # nichts wird gelöscht


def test_chat_nach_dem_ende_behaelt_den_entwurf(client, anna):
    sitzung = sitzung_beginnen(anna, sitzungstag(anna))
    sitzung_beenden(sitzung)
    client.force_login(mitglied_anlegen("bernd"))
    antwort = client.post(reverse("mandatare:live_beitrag", args=[anna.pk, sitzung.pk]), {"text": "Mein langer Text"})
    html = antwort.content.decode()
    assert antwort.status_code == 200 and "Die Sitzung ist beendet" in html
    assert not Kommentar.objects.filter(sitzung=sitzung).exists()


def test_chat_ungepruefte_schreiben_nicht(client, anna):
    sitzung = sitzung_beginnen(anna, sitzungstag(anna))
    client.force_login(mitglied_anlegen("emil", stufe=Identitaetsstufe.UNGEPRUEFT))
    antwort = client.post(reverse("mandatare:live_beitrag", args=[anna.pk, sitzung.pk]), {"text": "x"})
    assert antwort.status_code == 403 and not Kommentar.objects.exists()


def test_offene_fragen_in_der_karte(client, anna):
    sitzung = sitzung_beginnen(anna, sitzungstag(anna))
    sitzung_beitrag_schreiben(sitzung, mitglied_anlegen("bernd"), "Offene Frage an Sie")
    html = client.get(reverse("mandatare:mein")).content.decode()
    assert "Offene Frage an Sie" in html


# ── Rechenschaft und Sammelbericht aus dem Ticker ─────────────────────────────────────────


def test_rechenschaft_aus_dem_ticker(client, anna):
    sitzung = sitzung_beginnen(anna, sitzungstag(anna), punkte=["Budget 2027"])
    punkt = sitzung.punkte.get()
    meldung_abgeben(sitzung, "Dafür, weil die Mitglieder es beschlossen haben.", punkt, "dafuer", True)
    html = client.get(reverse("mandatare:mein") + f"?punkt={punkt.pk}").content.decode()
    assert f'name="punkt" value="{punkt.pk}"' in html
    assert 'value="Budget 2027"' in html and "Dafür, weil die Mitglieder es beschlossen haben.</textarea>" in html
    daten = {"punkt": punkt.pk, "gegenstand": "Budget 2027", "stimme": "dafuer", "begruendung": "Beschluss der Mitglieder."}
    post(client, anna, "rechenschaft", **daten)
    eintrag = Rechenschaft.objects.get()
    assert eintrag.punkt == punkt and eintrag.aufgabe == sitzung.aufgabe
    assert eintrag.sitzung_am == timezone.localdate()
    assert anna.offene_pflichten()["rechenschaften"] == []
    antwort = post(client, anna, "rechenschaft", **daten)
    assert "schon Rechenschaft" in antwort.content.decode() and Rechenschaft.objects.count() == 1
    # fremder Punkt
    bernd = mandat_anlegen(mitglied_anlegen("bernd"))
    fremd = sitzung_beginnen(bernd, sitzungstag(bernd), punkte=["X"]).punkte.get()
    antwort = post(client, anna, "rechenschaft", **{**daten, "punkt": fremd.pk})
    assert "gibt es hier nicht" in antwort.content.decode() and Rechenschaft.objects.count() == 1


def test_sammelbericht_aus_dem_ticker(client, anna):
    aufgabe = sitzungstag(anna)
    sitzung = sitzung_beginnen(anna, aufgabe, punkte=["Budget 2027"])
    meldung_abgeben(sitzung, "Dafür.", sitzung.punkte.get(), "dafuer", True)
    sitzung_beenden(sitzung)
    from mandatare.models import Aufgabe

    Aufgabe.objects.filter(pk=aufgabe.pk).update(frist=timezone.now() - timedelta(minutes=1))
    html = client.get(reverse("mandatare:mein") + f"?aufgabe={aufgabe.pk}&vorlage=1").content.decode()
    assert "Punkt 1 · Budget 2027 — Beschluss der Plattform: kein Beschluss der Plattform" in html
    assert "meine Stimme: dafür (abgestimmt)" in html


# ── Aus der gegnerischen Prüfung 0.53.0 ───────────────────────────────────────────────────


def test_punkt_ohne_antrag_erbt_nicht_den_antrag_des_sitzungstags(client, anna, ordnung):  # noqa: F811
    """Befund 1: Die Rechenschaft zu einem Punkt ohne Antrag bekam die Mandatsfrage der Aufgabe — falsches
    „weicht ab“ im Register und ein falscher Anlass für eine Vertrauensfrage."""
    aufgabe = sitzungstag(anna)
    frage = antrag_einbringen(anna.mitglied, "Radweg?", "Radweg.", "", ordnung)
    frage.phase = Phase.ANGENOMMEN.value
    frage.save()
    aufgabe.antrag = frage
    aufgabe.save()
    sitzung = sitzung_beginnen(anna, aufgabe, punkte=["Budget 2027"])
    punkt = sitzung.punkte.get()
    post(client, anna, "rechenschaft", punkt=punkt.pk, gegenstand="Budget 2027", stimme="dagegen",
         begruendung="Zu teuer.", beschluss_plattform="keiner")
    eintrag = Rechenschaft.objects.get()
    assert eintrag.antrag is None and eintrag.beschluss_anzeige == "keiner" and not eintrag.weicht_ab


def test_punkt_verknuepfen_nach_rechenschaft_gesperrt(client, anna, ordnung):  # noqa: F811
    sitzung = sitzung_beginnen(anna, sitzungstag(anna), punkte=["Budget"])
    punkt = sitzung.punkte.get()
    post(client, anna, "rechenschaft", punkt=punkt.pk, gegenstand="Budget", stimme="dafuer", begruendung="x")
    sache = antrag_einbringen(anna.mitglied, "Budget", "Das Budget.", "", ordnung)
    antwort = post(client, anna, "sitzung_verknuepfen", punkt=punkt.pk, antrag=sache.pk)
    punkt.refresh_from_db()
    assert punkt.antrag is None and "schon Rechenschaft" in antwort.content.decode()


def test_beenden_nach_dem_ende_der_vertretung(client, anna):
    """Befund 2: Nach dem Ende der Vertretung, des Mandats oder bei ruhender Mitwirkung ließ sich die laufende
    Sitzung nicht beenden — Live-Status und Chat blieben bis zur Höchstdauer offen."""
    sitzung = sitzung_beginnen(anna, sitzungstag(anna))
    Mandat.objects.filter(pk=anna.pk).update(vertretung_beendet_am=timezone.localdate())
    post(client, anna, "sitzung_beenden")
    assert not Sitzung.objects.get(pk=sitzung.pk).laeuft()
    # ein fremdes Mitglied beendet nichts
    andere = mandat_anlegen(mitglied_anlegen("bernd"))
    zweite = sitzung_beginnen(andere, sitzungstag(andere))
    assert client.post(AKTION, {"aktion": "sitzung_beenden", "mandat": andere.pk}).status_code == 403
    assert Sitzung.objects.get(pk=zweite.pk).laeuft()


def test_protokoll_bleibt_nach_dem_ende(client, anna):
    """Befunde 4 und 11: Nach dem Ende lässt sich im Chat nichts mehr zurückziehen oder als beantwortet markieren."""
    sitzung = sitzung_beginnen(anna, sitzungstag(anna))
    bernd = mitglied_anlegen("bernd")
    frage = sitzung_beitrag_schreiben(sitzung, bernd, "Frage")
    antwort = sitzung_beitrag_schreiben(sitzung, bernd, "Nachsatz", frage)
    aktion = reverse("mandatare:live_beitrag_aktion", args=[anna.pk, sitzung.pk, antwort.pk])
    client.post(aktion, {"aktion": "beantwortet"})  # eine Antwort ist keine Frage
    assert Kommentar.objects.get(pk=antwort.pk).beantwortet_am is None
    sitzung_beenden(sitzung)
    client.post(reverse("mandatare:live_beitrag_aktion", args=[anna.pk, sitzung.pk, frage.pk]), {"aktion": "beantwortet"})
    client.force_login(bernd)
    client.post(reverse("mandatare:live_beitrag_aktion", args=[anna.pk, sitzung.pk, frage.pk]), {"aktion": "entfernen"})
    frage.refresh_from_db()
    assert frage.beantwortet_am is None and not frage.geloescht


def test_fehlerseite_verlinkt_absolut(client, anna):
    """Befund 6: Die Fehlerseite des Chats steht unter der POST-Adresse — relative Links endeten mit 405."""
    sitzung = sitzung_beginnen(anna, sitzungstag(anna))
    client.force_login(mitglied_anlegen("bernd"))
    html = client.post(
        reverse("mandatare:live_beitrag", args=[anna.pk, sitzung.pk]), {"text": "x", "antwort_auf": "999999"}
    ).content.decode()
    assert "gibt es hier nicht" in html
    assert 'href="?' not in html and f'href="/mandatare/{anna.pk}/live/?sitzung={sitzung.pk}&amp;schreiben=1' in html
    assert f'hx-get="/mandatare/{anna.pk}/live/?sitzung={sitzung.pk}"' in html


def test_sammelbericht_nach_frueh_beendeter_sitzung(client, anna):
    """Befund 8: Endet die Sitzung vor der Uhrzeit der Aufgabe, gibt es Sammelbericht und Vorlage trotzdem."""
    aufgabe = sitzungstag(anna)  # Frist 23:59 heute
    sitzung = sitzung_beginnen(anna, aufgabe, punkte=["Budget 2027"])
    sitzung_beenden(sitzung)
    html = client.get(reverse("mandatare:mein") + f"?aufgabe={aufgabe.pk}&vorlage=1").content.decode()
    assert 'id="sb-aufgabe"' in html and "Punkt 1 · Budget 2027" in html
    post(client, anna, "sammelbericht", aufgabe=aufgabe.pk, text="Bericht")
    from mandatare.models import Bericht

    assert Bericht.objects.filter(aufgabe=aufgabe).exists()


def test_eingabefehler_behaelt_den_punkt(client, anna):
    """Befund 20: Nach einem Eingabefehler kommt das Formular mit dem Punkt zurück."""
    sitzung = sitzung_beginnen(anna, sitzungstag(anna), punkte=["Budget"])
    punkt = sitzung.punkte.get()
    html = client.post(AKTION, {"aktion": "rechenschaft", "mandat": anna.pk, "punkt": punkt.pk, "gegenstand": "Budget",
                                "stimme": "dafuer", "begruendung": ""}).content.decode()
    assert f'name="punkt" value="{punkt.pk}"' in html


def test_melden_ohne_javascript_ueber_die_seite_ohne_neuladen(client, anna):
    """Befund 24: Ohne JavaScript führt „Melden“ auf die Seite ohne Neuladetakt."""
    sitzung = sitzung_beginnen(anna, sitzungstag(anna))
    frage = sitzung_beitrag_schreiben(sitzung, mitglied_anlegen("bernd"), "Frage")
    client.force_login(mitglied_anlegen("cora"))
    html = client.get(live_url(anna, sitzung)).content.decode()
    assert f"schreiben=1#k-{frage.pk}" in html and "nur-mit-js" in html
    html = client.get(live_url(anna, sitzung, schreiben=1)).content.decode()
    assert 'http-equiv="refresh"' not in html and 'class="blase-melden nur-mit-js"' not in html


def test_ein_takt_fuer_stand_und_chat(client, anna):
    """Befund 29: Ein Takt holt die Seite einmal und tauscht Stand und Chat zugleich."""
    sitzung_beginnen(anna, sitzungstag(anna))
    html = client.get(live_url(anna)).content.decode()
    assert html.count("hx-trigger=") == 1 and 'hx-select-oob="#live-faden"' in html
