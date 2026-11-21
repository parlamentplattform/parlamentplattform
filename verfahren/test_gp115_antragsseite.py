"""Zweite Behebungsrunde nach der Gesamtprüfung (0.115): Antragsseite, Chat und Aktionen.

Je Befund ein Abschnitt; die Kennung steht im Testnamen."""

import re

import pytest
from django.urls import reverse

from mitglieder.models import Identitaetsstufe, Mitgliedsstatus
from verfahren.chat import beitrag_schreiben
from verfahren.hinweise import HINWEISE
from verfahren.test_direkt_handlung import _feld, _lage
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

HX = {"HTTP_HX_REQUEST": "true"}


# ── GP-070: Antragsseite zeigt keinen Knopf ohne Recht und nennt denselben Grund ──────────────


def _konto(zustand):
    """Ein Konto im genannten Zustand — None ist der Gast."""
    if zustand == "gast":
        return None
    if zustand == "ungeprueft":
        return mitglied_anlegen("ungeprueft", stufe=Identitaetsstufe.UNGEPRUEFT)
    if zustand == "ohne_anwartschaft":
        return mitglied_anlegen("frisch", tage=10)
    person = mitglied_anlegen(zustand)
    if zustand == "pausiert":
        person.status = Mitgliedsstatus.PAUSIERT
        person.save(update_fields=["status"])
    elif zustand == "testkonto":
        person.testkonto = True
        person.save(update_fields=["testkonto"])
    return person


#: Zustand → (Sperrcode beim Unterstützen, Sperrcode beim Abstimmen); None = darf.
ZUSTAENDE = {
    "gast": (None, None),
    "ungeprueft": ("gesperrt_ungeprueft", "gesperrt_ungeprueft"),
    "pausiert": ("gesperrt_pausiert", "gesperrt_pausiert"),
    "testkonto": ("testkonto", "testkonto"),
    "ohne_anwartschaft": (None, "nicht_stimmberechtigt"),
    "stimmberechtigt": (None, None),
}


@pytest.mark.parametrize("zustand", list(ZUSTAENDE))
def test_gp070_antragsseite_und_parlament_nennen_denselben_grund(client, ordnung, settings, zustand):  # noqa: F811
    settings.DDOE_UEBERGANGSREGEL = False
    leute, sammelnd, abstimmung = _lage(ordnung)
    beitrag_schreiben(sammelnd, leute[0], "Ein Beitrag zum Reagieren.")
    beitrag_schreiben(abstimmung, leute[0], "Noch ein Beitrag zum Reagieren.")
    person = _konto(zustand)
    if person is not None:
        client.force_login(person)
    code_u, code_s = ZUSTAENDE[zustand]

    seite_u = client.get(reverse("verfahren:antrag", args=[sammelnd.pk])).content.decode()
    seite_s = client.get(reverse("verfahren:antrag", args=[abstimmung.pk])).content.decode()
    region = _feld(client, "region")

    # Derselbe Grund wie im Parlament — dort kurz in der Kachel, hier als Satz
    for code, seite in ((code_u, seite_u), (code_s, seite_s)):
        if code:
            assert str(HINWEISE[code]["kurz"]) in region, (zustand, code)
            assert str(HINWEISE[code]["text"]) in seite, (zustand, code)
    # Der Satz zur Anwartschaft erscheint nur, wo er zutrifft
    assert "mitberaten und unterstützen können Sie sofort" not in seite_s

    # Kein Knopf, dessen Absenden mit 403 endet
    faelle = []
    if f'action="{reverse("verfahren:unterstuetzen", args=[sammelnd.pk])}"' in seite_u:
        faelle.append(("unterstuetzen", reverse("verfahren:unterstuetzen", args=[sammelnd.pk]), {}))
    if 'name="stimme"' in seite_s:
        faelle.append(("abstimmen", reverse("verfahren:abstimmen", args=[abstimmung.pk]), {"stimme": "ja"}))
    for seite, antrag in ((seite_u, sammelnd), (seite_s, abstimmung)):
        if 'id="chat-eingabe"' in seite:
            faelle.append(("kommentieren", reverse("verfahren:kommentieren", args=[antrag.pk]), {"text": "Hallo."}))
        for pfad in re.findall(r'action="(/antrag/\d+/beitrag/\d+/reagieren/)"', seite):
            faelle.append(("reagieren", pfad, {"art": "zustimmung"}))
    erwartet_knopf = zustand == "stimmberechtigt"
    assert bool(faelle) == (erwartet_knopf or zustand == "ohne_anwartschaft"), (zustand, faelle)
    for name, pfad, daten in faelle:
        antwort = client.post(pfad, daten)
        assert antwort.status_code != 403, (zustand, name)


@pytest.mark.parametrize("zustand", ["ungeprueft", "pausiert", "testkonto"])
def test_gp070_abstimmen_von_der_antragsseite_nennt_den_wahren_grund(client, ordnung, zustand):  # noqa: F811
    leute, _, abstimmung = _lage(ordnung)
    client.force_login(_konto(zustand))
    antwort = client.post(reverse("verfahren:abstimmen", args=[abstimmung.pk]), {"stimme": "ja"})
    assert antwort.status_code == 403
    html = antwort.content.decode()
    assert "drei Monaten" not in html and "Anwartschaft läuft bereits" not in html
    assert abstimmung.stimmabgaben.count() == 0


# ── GP-068: Der Lesestand entsteht beim Ausliefern der Antragsseite ───────────────────────────


def test_gp068_lesestand_entsteht_und_rueckt_vor(client, ordnung):  # noqa: F811
    """Ohne JavaScript (Testclient): Die Seite selbst schreibt den Stand fort, kein Skriptaufruf nötig."""
    from datetime import timedelta

    from verfahren.chat import ungelesene_gespraeche
    from verfahren.models import Lesestand

    leute, sammelnd, _ = _lage(ordnung)
    leser, andere = leute[1], leute[2]
    wurzel = beitrag_schreiben(sammelnd, leser, "Meine Frage an alle.")
    client.force_login(leser)
    url = reverse("verfahren:antrag", args=[sammelnd.pk])

    html = client.get(url).content.decode()  # erster Besuch: legt den Stand an, keine Linie
    stand = Lesestand.objects.get(mitglied=leser, antrag=sammelnd)
    assert 'id="neu"' not in html

    # Den Stand eine Minute zurücklegen: die fremde Antwort ist sicher jünger, ohne Blick auf die Uhr
    Lesestand.objects.filter(pk=stand.pk).update(gelesen_bis=stand.gelesen_bis - timedelta(minutes=1))
    beitrag_schreiben(sammelnd, andere, "Meine Antwort.", antwort_auf=wurzel)
    assert ungelesene_gespraeche(leser) == 1
    html = client.get(url).content.decode()
    assert 'id="neu"' in html and "1 neuer Beitrag" in html
    assert ungelesene_gespraeche(leser) == 0  # der Besuch hat gelesen
    assert 'id="neu"' not in client.get(url).content.decode()  # der übernächste Besuch: keine Linie


def test_gp068_lesestand_rueckt_auch_im_ruhenden_chat_vor(client, ordnung):  # noqa: F811
    from datetime import timedelta

    from verfahren.models import Lesestand

    leute, sammelnd, _ = _lage(ordnung)
    client.force_login(leute[1])
    url = reverse("verfahren:antrag", args=[sammelnd.pk])
    client.get(url)
    stand = Lesestand.objects.get(mitglied=leute[1], antrag=sammelnd)
    Lesestand.objects.filter(pk=stand.pk).update(gelesen_bis=stand.gelesen_bis - timedelta(minutes=1))
    beitrag_schreiben(sammelnd, leute[2], "Neu dazu.")
    Antrag = type(sammelnd)
    Antrag.objects.filter(pk=sammelnd.pk).update(phase="angenommen")  # Chat geschlossen, nur lesbar
    assert 'id="neu"' in client.get(url).content.decode()
    assert 'id="neu"' not in client.get(url).content.decode()


# ── GP-071: Rückmeldungen der Chat-Handlungen unter htmx stehen im Chat-Faden ────────────────


def _meldungen(antwort) -> list[str]:
    from django.contrib.messages import get_messages

    return [str(m) for m in get_messages(antwort.wsgi_request)]


def test_gp071_vier_handlungen_melden_sich_im_chat_faden(client, ordnung):  # noqa: F811
    from verfahren.models import Kommentar

    leute, sammelnd, _ = _lage(ordnung)
    fremd = beitrag_schreiben(sammelnd, leute[0], "Ein fremder Beitrag.")
    eigen = beitrag_schreiben(sammelnd, leute[1], "Mein Beitrag.")
    client.force_login(leute[1])

    def post(name, beitrag, daten=None):
        antwort = client.post(reverse(f"verfahren:{name}", args=[sammelnd.pk, beitrag.pk]), daten or {}, **HX)
        assert antwort.status_code == 200, name
        html = antwort.content.decode()
        assert html.startswith('<div id="chat-faden"'), name
        assert _meldungen(antwort) == [], name  # nichts für die nächste Seite
        return html

    # Melden: Fehler und Erfolg in der Zone
    assert '<p class="chat-fehler" role="alert">Bitte einen Grund wählen.</p>' in post("melden", fremd)
    assert "Danke — die Meldung liegt der Verwaltung vor." in post("melden", fremd, {"grund": "thema"})
    # Ändern: leerer Text und Frist vorbei
    assert "Bitte einen Text eingeben." in post("beitrag_bearbeiten", eigen, {"text": "  "})
    Kommentar.objects.filter(pk=eigen.pk).update(erstellt_am=eigen.erstellt_am - timedelta_tage(1))
    assert "Ändern ist nur in den ersten" in post("beitrag_bearbeiten", eigen, {"text": "Neu."})
    # Zurückziehen eines fremden Beitrags
    assert "Nur eigene Beiträge im laufenden Chat lassen sich zurückziehen." in post("beitrag_entfernen", fremd)
    # Reagieren als gesperrtes Konto: kein stummer 403
    pause = mitglied_anlegen("pause")
    pause.status = Mitgliedsstatus.PAUSIERT
    pause.save(update_fields=["status"])
    client.force_login(pause)
    html = post("reagieren", fremd, {"art": "zustimmung"})
    assert str(HINWEISE["gesperrt_pausiert"]["text"]) in html
    # Die nächste volle Seite trägt keine nachgereichte Meldung
    html = client.get("/parlament/").content.decode()
    assert "Meldung liegt der Verwaltung vor" not in html and "Bitte einen Grund" not in html


def timedelta_tage(n):
    from datetime import timedelta

    return timedelta(days=n)


# ── GP-077: Abstimmungs-Chat chronologisch über ?reihung=zeit ────────────────────────────────


def test_gp077_reihung_zeit_zeigt_chronologisch_bei_gleicher_auswertung(client, ordnung):  # noqa: F811
    from gremien.test_werkstatt import einreichen, reagieren, systembeitrag, werkstatt_lage
    from verfahren.test_chat import _faden_html

    antrag, unterstuetzer, er = werkstatt_lage(ordnung)
    einreichen(client, antrag, er)
    passt = systembeitrag(antrag)
    beitrag_schreiben(antrag, unterstuetzer[0], "Ohne Reaktion.")
    bewegt = beitrag_schreiben(antrag, unterstuetzer[1], "Das bewegt am meisten.")
    for u in unterstuetzer:
        reagieren(client, antrag, bewegt, u)
    reagieren(client, antrag, passt, unterstuetzer[0])
    client.force_login(unterstuetzer[0])
    ziel = reverse("verfahren:antrag", args=[antrag.pk])

    engagement = client.get(ziel).content.decode()
    faden = _faden_html(engagement)
    assert faden.index("Das bewegt am meisten.") < faden.index("Ohne Reaktion."), "Vorgabe: Engagement"
    assert f'href="{ziel}?reihung=zeit#chat-faden"' in engagement, "der Umschalter als Link, ohne JavaScript"

    zeit = client.get(f"{ziel}?reihung=zeit").content.decode()
    faden = _faden_html(zeit)
    assert faden.index("Passt alles") < faden.index("Ohne Reaktion.") < faden.index("Das bewegt am meisten.")
    assert f'href="{ziel}#chat-faden"' in zeit, "zurück zur Reihung nach Engagement"

    def stand(html):
        return html.split('class="meta stand"')[1].split("</p>")[0]

    assert stand(zeit) == stand(engagement), "die Auswertung bleibt unverändert"


# ── GP-084: Beanstanden mit Stundengrenze je Konto, nie an Personenwahlen ────────────────────


def test_gp084_beanstanden_ueber_der_stundengrenze_legt_nichts_an(client, ordnung, monkeypatch):  # noqa: F811
    from types import SimpleNamespace

    from verfahren import views_aktionen
    from verfahren.models import Beanstandung
    from verfahren.test_views_aktionen import ANTRAG

    monkeypatch.setattr(views_aktionen, "BEANSTANDUNGEN_JE_STUNDE", 2, raising=False)
    # EINE Stunde für alle Versuche — der Test hängt nicht an der Uhrzeit
    monkeypatch.setattr("mitglieder.botschutz.time", SimpleNamespace(time=lambda: 1_000_000 * 3600.0 + 60))
    from verfahren.models import antrag_einbringen

    antrag = antrag_einbringen(mitglied_anlegen("autorin"), **ANTRAG, ordnung=ordnung)
    client.force_login(mitglied_anlegen("bernd"))
    url = reverse("verfahren:beanstanden", args=[antrag.pk])
    for i in range(2):
        assert client.post(url, {"text": f"Die Zahl {i} stimmt nicht."}).status_code == 302
    assert Beanstandung.objects.count() == 2
    antwort = client.post(url, {"text": "Noch eine."}, follow=True)
    assert Beanstandung.objects.count() == 2, "der Versuch über der Grenze legt nichts an"
    assert "Höchstens 2 Beanstandungen je Stunde" in antwort.content.decode()


@pytest.mark.parametrize("art", ["mandat", "vertrauensfrage"])
def test_gp084_an_einer_personenwahl_entsteht_keine_beanstandung(client, ordnung, art):  # noqa: F811
    from verfahren.models import Antrag, AuditEintrag, Beanstandung, antrag_einbringen
    from verfahren.test_views_aktionen import ANTRAG

    antrag = antrag_einbringen(mitglied_anlegen("autorin"), **ANTRAG, ordnung=ordnung)
    Antrag.objects.filter(pk=antrag.pk).update(art=art)
    vorher = AuditEintrag.objects.count()
    client.force_login(mitglied_anlegen("bernd"))
    antwort = client.post(reverse("verfahren:beanstanden", args=[antrag.pk]), {"text": "Falsch."})
    assert antwort.status_code == 404
    assert Beanstandung.objects.count() == 0 and AuditEintrag.objects.count() == vorher
