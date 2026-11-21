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
