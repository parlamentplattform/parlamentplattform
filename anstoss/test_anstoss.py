"""Der Anstoß (F-69): das begleitende Feedback-Widget auf jeder Seite."""

import pytest
from django.urls import reverse

from anstoss.models import Anstoss

pytestmark = pytest.mark.django_db


def person(django_user_model, name="anna", admin=False):
    m = django_user_model.objects.create_user(username=name, password="x", email=f"{name}@example.org")
    if admin:
        m.ist_admin = True
        m.save(update_fields=["ist_admin"])
    return m


def test_gast_kann_anonym_anstoss_geben(client):
    antwort = client.post(reverse("anstoss:senden"), {"text": "Bitte größere Schrift.", "seite": "/parlament/"})
    assert antwort.status_code == 302
    assert antwort.url == "/parlament/?anstoss=danke"
    a = Anstoss.objects.get()
    assert a.text == "Bitte größere Schrift."
    assert a.seite == "/parlament/"
    assert a.nutzer is None
    assert a.status == "neu"


def test_mitglied_wird_zugeordnet(client, django_user_model):
    client.force_login(person(django_user_model))
    client.post(reverse("anstoss:senden"), {"text": "Wunsch: Dunkelmodus-Schalter.", "seite": "/"})
    assert Anstoss.objects.get().nutzer.username == "anna"


def test_honigtopf_speichert_nichts_und_verraet_nichts(client):
    antwort = client.post(
        reverse("anstoss:senden"), {"text": "Kaufen Sie X!", "webseite": "http://spam", "seite": "/"}
    )
    assert antwort.status_code == 302 and "anstoss=danke" in antwort.url  # nach außen wie Erfolg
    assert Anstoss.objects.count() == 0


def test_sendeabstand_wird_verlangt(client):
    client.post(reverse("anstoss:senden"), {"text": "Erster Anstoß.", "seite": "/"})
    antwort = client.post(reverse("anstoss:senden"), {"text": "Gleich noch einer.", "seite": "/"})
    assert "anstoss=warte" in antwort.url
    assert Anstoss.objects.count() == 1


def test_leere_nachricht_wird_nicht_gespeichert(client):
    antwort = client.post(reverse("anstoss:senden"), {"text": "   ", "seite": "/parlament/"})
    assert "anstoss=leer" in antwort.url
    assert Anstoss.objects.count() == 0


def test_ruecksprung_nur_auf_interne_pfade(client):
    antwort = client.post(reverse("anstoss:senden"), {"text": "Test.", "seite": "https://boese.example"})
    assert antwort.url == "/?anstoss=danke"
    assert Anstoss.objects.get().seite == "/"


def test_htmx_bekommt_fragment_statt_umleitung(client):
    antwort = client.post(
        reverse("anstoss:senden"), {"text": "Per htmx gesendet.", "seite": "/"}, HTTP_HX_REQUEST="true"
    )
    assert antwort.status_code == 200
    # Erfolg meldet sich als Ereignis (HX-Trigger) statt per Inline-Script — Alpine schließt das
    # Widget und zeigt die Bestätigungsblase (FB-P4, Vorgabe 1.9. abends).
    assert antwort["HX-Trigger"] == "anstoss-danke"
    inhalt = antwort.content.decode()
    assert "<script" not in inhalt and "gespeichert" in inhalt
    assert Anstoss.objects.count() == 1
    zweite = client.post(reverse("anstoss:senden"), {"text": "Gleich noch einer.", "seite": "/"}, HTTP_HX_REQUEST="true")
    assert zweite["HX-Trigger"] == "anstoss-warte"


def test_schliesslinks_behalten_die_abfrage_ohne_anstoss_parameter(client):
    html = client.get("/parlament/?fach=umwelt&anstoss=danke").content.decode()
    assert 'href="/parlament/?fach=umwelt"' in html
    assert 'id="anstoss-blase" role="status" x-ref="blase">' in html  # Blase sichtbar (kein hidden)
    warte = client.get("/parlament/?anstoss=warte").content.decode()
    assert 'x-ref="klappe" open' in warte


def test_widget_begleitet_auf_allen_seiten(client):
    for pfad in ["/", "/parlament/", reverse("mitglieder:mitgliedschaft"), reverse("verfahren:umsetzung")]:
        assert "anstoss-fleck" in client.get(pfad).content.decode(), pfad


def test_verwaltung_nur_fuer_admins(client, django_user_model):
    Anstoss.objects.create(text="Geheimnis? Nein — aber intern.", seite="/")
    url = reverse("anstoss:verwaltung")
    assert client.get(url).status_code in (302, 403)  # anonym
    client.force_login(person(django_user_model, "bernd"))
    assert client.get(url).status_code == 403  # Mitglied ohne Adminrechte
    client.force_login(person(django_user_model, "admina", admin=True))
    antwort = client.get(url)
    assert antwort.status_code == 200
    assert "aber intern" in antwort.content.decode()


def test_status_und_exporte(client, django_user_model):
    a = Anstoss.objects.create(text="Bitte Fächer bauen.", seite="/parlament/")
    client.force_login(person(django_user_model, "admina", admin=True))
    client.post(reverse("anstoss:status", args=[a.pk]), {"status": "gesichtet", "weiter": "/verwaltung/anstoesse/"})
    a.refresh_from_db()
    assert a.status == "gesichtet"

    csv_inhalt = client.get(reverse("anstoss:export_csv")).content.decode("utf-8-sig")
    assert "Bitte Fächer bauen." in csv_inhalt and csv_inhalt.startswith("nr,")
    json_antwort = client.get(reverse("anstoss:export_json")).json()
    assert json_antwort["anstoesse"][0]["text"] == "Bitte Fächer bauen."
    assert json_antwort["anstoesse"][0]["status"] == "gesichtet"
