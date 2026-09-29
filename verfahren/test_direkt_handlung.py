"""Direkt-Handlung aus Kachel und Feed-Zeile (Befunde B1/B2, 28.9.2026).

Eine Handlung aus dem Parlament kehrt — mit und ohne JavaScript — mit einem Hinweis in ihr
Ursprungsfeld zurück (`?hinweis=<code>&feld=<kennung>`), nie auf die Antragsseite und nie mit
einer Flash-Meldung. Wer nicht handeln darf, sieht statt der Knöpfe den Zustand mit Link.
Der Chat behält bei Fehlern den Entwurf. Formulare der Antragsseite (ohne `feld`) behalten ihr
Verhalten (Flash, 403-Seiten)."""

from datetime import timedelta

import pytest
from django.contrib.messages import get_messages
from django.urls import reverse
from django.utils import timezone

from mitglieder.models import Adresswechsel, Identitaetsstufe, Mitgliedsstatus
from verfahren.hinweise import HINWEISE, hinweis_lage, weiter_ohne_hinweis
from verfahren.models import Antrag, FilterProfil, antrag_einbringen
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db

HX = {"HTTP_HX_REQUEST": "true"}


def _meldungen(antwort) -> list[str]:
    return [str(m) for m in get_messages(antwort.wsgi_request)]


def _feld(client, name: str, url: str = "/parlament/") -> str:
    html = client.get(url).content.decode()
    return html.split(f'id="feld-{name}"')[1].split("</section>")[0]


def _lage(ordnung):  # noqa: F811
    """Ein Antrag in Unterstützung, einer in Abstimmung — beide regional (Feld „Region“) und im Feed."""
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    ort = {"ebene": "gemeinde", "gebiet": "St. Marienkirchen an der Polsenz"}
    sammelnd = antrag_einbringen(leute[0], **ANTRAG, ordnung=ordnung, **ort)
    abstimmung = in_abstimmung_bringen(
        antrag_einbringen(leute[0], "Zweiter Antrag zur Abstimmung", "Wortlaut.", "", ordnung, **ort), leute[1:]
    )
    return leute, sammelnd, abstimmung


# ── Unterstützen aus dem Feed ─────────────────────────────────────────────────────────────────


def test_unterstuetzen_aus_dem_feed_kehrt_mit_hinweis_ins_feld_zurueck(client, ordnung):  # noqa: F811
    leute, sammelnd, _ = _lage(ordnung)
    client.force_login(leute[2])
    feld = _feld(client, "filter")
    assert f'id="u-filter-{sammelnd.pk}"' in feld and 'name="feld" value="filter"' in feld

    antwort = client.post(
        reverse("verfahren:unterstuetzen", args=[sammelnd.pk]), {"weiter": "/parlament/", "feld": "filter"}, **HX
    )
    assert antwort.status_code == 302
    assert antwort.url == "/parlament/?hinweis=erfasst&feld=filter#feld-filter"
    assert _meldungen(antwort) == []  # keine Django-messages auf diesem Pfad
    assert sammelnd.unterstuetzungen.filter(zurueckgezogen_am__isnull=True).count() == 1

    feld = _feld(client, "filter", antwort.url.split("#")[0])
    assert '<p class="feld-hinweis ok" role="status" id="hinweis-filter">Unterstützung erfasst.</p>' in feld
    assert f'id="u-filter-{sammelnd.pk}" class="knopf gewaehlt" aria-pressed="true">✓ Unterstützt' in feld
    # die anderen Felder zeigen keinen Hinweis
    html = client.get(antwort.url.split("#")[0]).content.decode()
    assert html.count('class="feld-hinweis') == 1

    # noch einmal: zurückziehen — der alte Hinweis in `weiter` wird nicht mitgeschleppt
    antwort = client.post(
        reverse("verfahren:unterstuetzen", args=[sammelnd.pk]),
        {"weiter": "/parlament/?fach=energie&hinweis=erfasst&feld=filter", "feld": "filter"},
    )
    assert antwort.url == "/parlament/?fach=energie&hinweis=zurueckgezogen&feld=filter#feld-filter"


def test_unsicheres_weiter_faellt_aufs_parlament_zurueck(client, ordnung):  # noqa: F811
    leute, sammelnd, _ = _lage(ordnung)
    client.force_login(leute[2])
    antwort = client.post(
        reverse("verfahren:unterstuetzen", args=[sammelnd.pk]), {"weiter": "https://boese", "feld": "filter"}
    )
    assert antwort.url == "/parlament/?hinweis=erfasst&feld=filter#feld-filter"


def test_unterstuetzen_von_der_antragsseite_bleibt_wie_bisher(client, ordnung):  # noqa: F811
    leute, sammelnd, _ = _lage(ordnung)
    client.force_login(leute[2])
    antwort = client.post(reverse("verfahren:unterstuetzen", args=[sammelnd.pk]))  # ohne `feld`
    assert antwort.url == f"/antrag/{sammelnd.pk}/"
    assert _meldungen(antwort) == ["Danke — Ihre Unterstützung ist erfasst."]


def test_phase_vorbei_meldet_sich_im_feld_statt_auf_der_antragsseite(client, ordnung):  # noqa: F811
    leute, sammelnd, _ = _lage(ordnung)
    Antrag.objects.filter(pk=sammelnd.pk).update(phase="beratung")
    client.force_login(leute[2])
    antwort = client.post(
        reverse("verfahren:unterstuetzen", args=[sammelnd.pk]), {"weiter": "/parlament/", "feld": "wichtig"}, **HX
    )
    assert antwort.url == "/parlament/?hinweis=phase_vorbei&feld=wichtig#feld-wichtig"
    assert _meldungen(antwort) == []
    assert "Die Unterstützungsphase ist beendet." in _feld(client, "wichtig", antwort.url.split("#")[0])


# ── Abstimmen aus der Kachel ──────────────────────────────────────────────────────────────────


def test_abstimmen_aus_der_kachel_erfolg_und_phase_vorbei(client, ordnung):  # noqa: F811
    leute, _, abstimmung = _lage(ordnung)
    client.force_login(leute[2])
    region = _feld(client, "region")
    assert f'id="st-region-{abstimmung.pk}-ja"' in region and 'name="feld" value="region"' in region

    antwort = client.post(
        reverse("verfahren:abstimmen", args=[abstimmung.pk]),
        {"stimme": "ja", "weiter": "/parlament/", "feld": "region"}, **HX,
    )
    assert antwort.url == "/parlament/?hinweis=stimme&feld=region#feld-region"
    assert _meldungen(antwort) == [] and abstimmung.stimmabgaben.count() == 1
    region = _feld(client, "region", "/parlament/?hinweis=stimme&feld=region")
    assert "Stimme erfasst — änderbar bis zum Fristende." in region
    assert f'id="st-region-{abstimmung.pk}-ja" class="btn-linie gewaehlt" aria-pressed="true"' in region

    Antrag.objects.filter(pk=abstimmung.pk).update(phase="angenommen")
    antwort = client.post(
        reverse("verfahren:abstimmen", args=[abstimmung.pk]),
        {"stimme": "nein", "weiter": "/parlament/", "feld": "region"}, **HX,
    )
    assert antwort.url == "/parlament/?hinweis=stimme_fehler&feld=region#feld-region"
    assert abstimmung.stimmabgaben.get().stimme == "ja"


def test_abstimmen_von_der_antragsseite_folgt_weiter_mit_flash(client, ordnung):  # noqa: F811
    leute, _, abstimmung = _lage(ordnung)
    client.force_login(leute[2])
    antwort = client.post(reverse("verfahren:abstimmen", args=[abstimmung.pk]), {"stimme": "ja"})
    assert antwort.url == f"/antrag/{abstimmung.pk}/"
    assert _meldungen(antwort) == ["Ihre Stimme ist erfasst — bis zum Fristende können Sie sie ändern."]


# ── Sperren je Stufe: keine Knöpfe, Hinweis statt 403-Seite ──────────────────────────────────


@pytest.mark.parametrize(
    ("stufe", "status", "code", "kurz"),
    [
        (Identitaetsstufe.UNGEPRUEFT, Mitgliedsstatus.AKTIV, "gesperrt_ungeprueft", "Identität noch ungeprüft"),
        (Identitaetsstufe.GEPRUEFT, Mitgliedsstatus.PAUSIERT, "gesperrt_pausiert", "Mitwirkung ruht"),
        (Identitaetsstufe.GEPRUEFT, Mitgliedsstatus.AUSGESCHLOSSEN, "gesperrt_ausgeschlossen", "Mitwirkung ruht"),
    ],
)
def test_gesperrte_sehen_keine_knoepfe_und_bekommen_den_hinweis(client, ordnung, stufe, status, code, kurz):  # noqa: F811
    leute, sammelnd, abstimmung = _lage(ordnung)
    person = mitglied_anlegen("gesperrt", stufe=stufe)
    person.status = status
    person.save(update_fields=["status"])
    client.force_login(person)

    for name in ("filter", "region"):
        feld = _feld(client, name)
        assert "unterstuetzen/" not in feld and 'name="stimme"' not in feld
        assert feld.count(kurz) == 2, name  # je Antrag ein Zustand statt Knöpfen
    if code != "gesperrt_ausgeschlossen":
        assert 'sperre">Identität noch ungeprüft — <a href="/willkommen/">Beitrag</a>' in _feld(client, "filter") or (
            'sperre">Mitwirkung ruht — <a href="/willkommen/">Beitrag</a>' in _feld(client, "filter")
        )

    antwort = client.post(
        reverse("verfahren:unterstuetzen", args=[sammelnd.pk]), {"weiter": "/parlament/", "feld": "filter"}, **HX
    )
    assert antwort.status_code == 302 and antwort.url == f"/parlament/?hinweis={code}&feld=filter#feld-filter"
    assert _meldungen(antwort) == [] and sammelnd.unterstuetzungen.count() == 0
    hinweis = _feld(client, "filter", antwort.url.split("#")[0])
    assert 'class="feld-hinweis fehler" role="status"' in hinweis and str(HINWEISE[code]["text"]) in hinweis

    antwort = client.post(
        reverse("verfahren:abstimmen", args=[abstimmung.pk]), {"stimme": "ja", "weiter": "/parlament/", "feld": "region"}
    )
    assert antwort.url == f"/parlament/?hinweis={code}&feld=region#feld-region"
    assert abstimmung.stimmabgaben.count() == 0

    # Von der Antragsseite (ohne `feld`) bleiben die 403-Seiten richtig
    assert client.post(reverse("verfahren:unterstuetzen", args=[sammelnd.pk])).status_code == 403
    assert client.post(reverse("verfahren:abstimmen", args=[abstimmung.pk]), {"stimme": "ja"}).status_code == 403


def test_nicht_stimmberechtigte_sehen_den_stichtag_statt_der_knoepfe(client, ordnung, settings):  # noqa: F811
    settings.DDOE_UEBERGANGSREGEL = False
    leute, sammelnd, abstimmung = _lage(ordnung)
    frisch = mitglied_anlegen("frisch", tage=10)  # unterstützen ja, abstimmen nein (§ 4 Abs 4)
    client.force_login(frisch)
    feld = _feld(client, "filter")
    assert f'id="u-filter-{sammelnd.pk}"' in feld
    assert 'name="stimme"' not in feld
    assert 'Nicht stimmberechtigt am Stichtag — <a href="/rollen/">Wer darf was</a>' in feld

    antwort = client.post(
        reverse("verfahren:abstimmen", args=[abstimmung.pk]), {"stimme": "ja", "weiter": "/parlament/", "feld": "filter"}
    )
    assert antwort.url == "/parlament/?hinweis=nicht_stimmberechtigt&feld=filter#feld-filter"
    assert client.post(reverse("verfahren:abstimmen", args=[abstimmung.pk]), {"stimme": "ja"}).status_code == 403


def test_offener_adresswechsel_sperrt_nur_die_stimmabgabe(client, ordnung):  # noqa: F811
    leute, sammelnd, abstimmung = _lage(ordnung)
    Adresswechsel.objects.create(
        mitglied=leute[2], neue_email="neu@example.org", frist_bis=timezone.now() + timedelta(days=1),
        einspruch_hash="x" * 64,
    )
    client.force_login(leute[2])
    feld = _feld(client, "filter")
    assert f'id="u-filter-{sammelnd.pk}"' in feld and 'name="stimme"' not in feld
    assert 'Adresswechsel offen — <a href="/profil/">Profil</a>' in feld
    antwort = client.post(
        reverse("verfahren:abstimmen", args=[abstimmung.pk]), {"stimme": "ja", "weiter": "/parlament/", "feld": "filter"}
    )
    assert antwort.url == "/parlament/?hinweis=adresswechsel&feld=filter#feld-filter"


def test_gaeste_werden_zur_anmeldung_geschickt(client, ordnung):  # noqa: F811
    """Ohne Sitzung (abgelaufen, abgemeldet, Konto stillgelegt): Mit htmx wechselt die ganze Seite zur
    Anmeldung (HX-Redirect) — einem 302 folgte htmx unsichtbar und tauschte das Feld gegen nichts.
    `next` zeigt auf den sicheren weiter-Pfad, nie auf die POST-Adresse. Ohne htmx bleibt der 302."""
    _, sammelnd, abstimmung = _lage(ordnung)
    antwort = client.post(
        reverse("verfahren:unterstuetzen", args=[sammelnd.pk]), {"weiter": "/parlament/?fach=umwelt", "feld": "filter"}, **HX
    )
    assert antwort.status_code == 200 and antwort.content == b""
    assert antwort["HX-Redirect"] == "/anmelden/?next=%2Fparlament%2F%3Ffach%3Dumwelt"
    antwort = client.post(
        reverse("verfahren:abstimmen", args=[abstimmung.pk]), {"stimme": "ja", "weiter": "//fremd.example", "feld": "region"}, **HX
    )
    assert antwort["HX-Redirect"] == "/anmelden/?next=%2Fparlament%2F"
    antwort = client.post(reverse("verfahren:abstimmen", args=[abstimmung.pk]), {"stimme": "ja", "feld": "region"})
    assert antwort.status_code == 302 and antwort.url.startswith("/anmelden/") and "HX-Redirect" not in antwort
    feld = _feld(client, "filter")
    assert "unterstuetzen/" not in feld and 'name="stimme"' not in feld


# ── Der Hinweis selbst ────────────────────────────────────────────────────────────────────────


def test_fremde_codes_und_felder_zeigen_nichts(client, ordnung, rf):  # noqa: F811
    _lage(ordnung)
    assert hinweis_lage(rf.get("/parlament/?hinweis=erfasst&feld=filter"))["code"] == "erfasst"
    assert hinweis_lage(rf.get("/parlament/?hinweis=<script>&feld=filter")) is None
    assert hinweis_lage(rf.get("/parlament/?hinweis=erfasst&feld=favoriten")) is None
    assert hinweis_lage(rf.get("/parlament/")) is None
    html = client.get("/parlament/?hinweis=boese&feld=filter").content.decode()
    assert 'class="feld-hinweis' not in html
    assert weiter_ohne_hinweis("/parlament/?fach=x&hinweis=a&feld=b") == "/parlament/?fach=x"
    assert weiter_ohne_hinweis("/parlament/") == "/parlament/"


def test_jeder_code_hat_text_und_uebersetzbare_kurzform():
    for code, eintrag in HINWEISE.items():
        assert str(eintrag["text"]).strip(), code
        assert eintrag.get("art") in ("ok", "fehler"), code
        if eintrag.get("link"):
            assert eintrag.get("link_text"), code


# ── Chat: Fehler mit Entwurf, nie über messages ───────────────────────────────────────────────


def test_chat_fehler_behaelt_den_text_und_zeigt_die_meldung(client, ordnung):  # noqa: F811
    leute, sammelnd, _ = _lage(ordnung)
    client.force_login(leute[2])
    url = reverse("verfahren:kommentieren", args=[sammelnd.pk])

    antwort = client.post(url, {"text": ""}, **HX)
    assert antwort.status_code == 200 and _meldungen(antwort) == []
    html = antwort.content.decode()
    assert '<p class="chat-fehler" role="alert">Bitte einen Text eingeben.</p>' in html
    assert 'id="chat-faden"' in html and 'id="chat-eingabe"' in html

    Antrag.objects.filter(pk=sammelnd.pk).update(phase="angenommen")  # Chat geschlossen
    antwort = client.post(url, {"text": "Mein Entwurf bleibt.", "antwort_auf": ""}, **HX)
    html = antwort.content.decode()
    assert "chat-fehler" in html and "Das Verfahren ist beendet" in html
    assert sammelnd.kommentare.count() == 0
    # Der Chat ist zu — das Formular fehlt, der Fehler steht trotzdem; wieder offen: der Entwurf im Feld
    Antrag.objects.filter(pk=sammelnd.pk).update(phase="unterstuetzung")
    antwort = client.post(url, {"text": "Mein Entwurf bleibt.", "antwort_auf": "999"}, **HX)
    html = antwort.content.decode()
    assert "nicht mehr im laufenden Chat" in html
    assert ">Mein Entwurf bleibt.</textarea>" in html
    assert _meldungen(antwort) == []


def test_chat_fehler_ohne_javascript_zeigt_die_seite_mit_entwurf(client, ordnung):  # noqa: F811
    leute, sammelnd, _ = _lage(ordnung)
    client.force_login(leute[2])
    antwort = client.post(
        reverse("verfahren:kommentieren", args=[sammelnd.pk]), {"text": "Ohne Skript.", "antwort_auf": "999"}
    )
    assert antwort.status_code == 200 and _meldungen(antwort) == []
    html = antwort.content.decode()
    assert '<p class="chat-fehler" role="alert">' in html and ">Ohne Skript.</textarea>" in html
    assert "<title>" in html  # die ganze Antragsseite, nicht nur die Zone
    # Erfolg ohne JavaScript: Redirect auf den Anker wie bisher
    antwort = client.post(reverse("verfahren:kommentieren", args=[sammelnd.pk]), {"text": "Passt."})
    assert antwort.status_code == 302 and "#k-" in antwort.url


def test_chat_sperre_mit_htmx_als_fehler_mit_link(client, ordnung):  # noqa: F811
    leute, sammelnd, _ = _lage(ordnung)
    person = mitglied_anlegen("pause")
    person.status = Mitgliedsstatus.PAUSIERT
    person.save(update_fields=["status"])
    client.force_login(person)
    url = reverse("verfahren:kommentieren", args=[sammelnd.pk])
    antwort = client.post(url, {"text": "Darf ich?"}, **HX)
    assert antwort.status_code == 200
    html = antwort.content.decode()
    assert "Mitwirkung ruht — Beitrag ausständig (§ 4 Abs 3)." in html and 'href="/willkommen/">Beitrag ›</a>' in html
    assert ">Darf ich?</textarea>" in html and sammelnd.kommentare.count() == 0
    assert client.post(url, {"text": "Darf ich?"}).status_code == 403  # ohne htmx die 403-Seite


# ── WeicherFilter und Sterne: keine Flash-Meldung auf htmx-Pfaden ─────────────────────────────


def test_filter_fehler_und_erfolg_als_hinweis_im_feld(client, ordnung):  # noqa: F811
    leute, *_ = _lage(ordnung)
    client.force_login(leute[2])
    FilterProfil.objects.create(mitglied=leute[2], name="Eins", regler={}, aktiv=True)
    zwei = FilterProfil.objects.create(mitglied=leute[2], name="Zwei", regler={})
    antwort = client.post(
        reverse("verfahren:filter_umbenennen", args=[zwei.pk]), {"name": "Eins", "weiter": "/parlament/", "feld": "filter"}, **HX
    )
    assert antwort.url == "/parlament/?hinweis=name_vergeben&feld=filter#feld-filter" and _meldungen(antwort) == []
    assert "Eine Konfiguration mit diesem Namen gibt es schon." in _feld(client, "filter", "/parlament/?hinweis=name_vergeben&feld=filter")

    antwort = client.post(
        reverse("verfahren:filter_anwenden"), {"r_chronologisch": "50", "weiter": "/parlament/", "feld": "filter"}, **HX
    )
    assert antwort.url == "/parlament/?hinweis=filter_aktiv&feld=filter#feld-filter" and _meldungen(antwort) == []
    antwort = client.post(reverse("verfahren:filter_loeschen", args=[zwei.pk]), {"weiter": "/parlament/", "feld": "filter"})
    assert antwort.url == "/parlament/?hinweis=profil_geloescht&feld=filter#feld-filter" and _meldungen(antwort) == []
    # Ohne `feld` (fremdes Formular) bleibt die Flash-Meldung
    antwort = client.post(reverse("verfahren:filter_anwenden"), {"r_chronologisch": "60"})
    assert antwort.url == "/parlament/" and len(_meldungen(antwort)) == 1
    # Das Feld trägt alle Formulare mit `feld`
    feld = _feld(client, "filter")
    assert feld.count('name="feld" value="filter"') >= 5


def test_favorisieren_mit_htmx_setzt_keine_meldung(client, ordnung):  # noqa: F811
    leute, sammelnd, _ = _lage(ordnung)
    client.force_login(leute[2])
    antwort = client.post(reverse("verfahren:favorisieren", args=[sammelnd.pk]), {"weiter": "/parlament/"}, **HX)
    assert antwort.status_code == 200 and _meldungen(antwort) == []
    antwort = client.post(
        reverse("verfahren:favorisieren", args=[sammelnd.pk]), {"weiter": "/parlament/?hinweis=erfasst&feld=filter"}
    )
    assert antwort.url == "/parlament/" and len(_meldungen(antwort)) == 1  # ohne htmx: Flash, alter Hinweis fällt weg
