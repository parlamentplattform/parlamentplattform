"""S6 — das Chatsystem (FB-G1 bis G5): Faden mit Antworten, Reaktionen, Ändern und Zurückziehen,
Melden, Lesestand mit „n neue", Archivierung bei jeder Hochstufung und die Gespräche im Panel."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from verfahren import chat as chatkern
from verfahren.models import (
    Antrag,
    AuditEintrag,
    Kommentar,
    Lesestand,
    Meldung,
    Reaktion,
    antrag_einbringen,
)
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db


def _antrag(ordnung, autor=None):  # noqa: F811
    return antrag_einbringen(autor or mitglied_anlegen("autor"), **ANTRAG, ordnung=ordnung)


def _seite(client, antrag):
    return client.get(reverse("verfahren:antrag", args=[antrag.pk])).content.decode()


# ── Der Faden (FB-G1) ─────────────────────────────────────────────────────────


def test_beitrag_und_antwort_bilden_einen_faden(client, ordnung):  # noqa: F811
    anna, bernd = mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    antrag = _antrag(ordnung, anna)
    client.force_login(anna)
    client.post(reverse("verfahren:kommentieren", args=[antrag.pk]), {"text": "Mein erster Gedanke."})
    wurzel = Kommentar.objects.get()
    assert wurzel.phase == antrag.phase and wurzel.antwort_auf is None

    client.force_login(bernd)
    client.post(
        reverse("verfahren:kommentieren", args=[antrag.pk]),
        {"text": "Da stimme ich zu.", "antwort_auf": wurzel.pk},
    )
    antwort = Kommentar.objects.exclude(pk=wurzel.pk).get()
    assert antwort.antwort_auf == wurzel
    # Antwort auf eine Antwort bleibt am selben Wurzelbeitrag — der Faden bleibt eine Ebene tief
    client.post(
        reverse("verfahren:kommentieren", args=[antrag.pk]),
        {"text": "Und noch etwas.", "antwort_auf": antwort.pk},
    )
    assert Kommentar.objects.filter(antwort_auf=wurzel).count() == 2
    assert Kommentar.objects.filter(antwort_auf=antwort).count() == 0

    faden = chatkern.faden(antrag, bernd)
    assert len(faden) == 1 and len(faden[0]["antworten"]) == 2
    inhalt = _seite(client, antrag)
    assert 'class="antworten"' in inhalt and f'id="k-{antwort.pk}"' in inhalt


def test_gaeste_lesen_mit_aber_schreiben_nicht(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    antrag = _antrag(ordnung, anna)
    chatkern.beitrag_schreiben(antrag, anna, "Öffentlich lesbar.")
    inhalt = _seite(client, antrag)
    assert "Öffentlich lesbar." in inhalt
    assert "Mitlesen ist offen" in inhalt and 'class="chatzeile"' not in inhalt
    assert client.post(reverse("verfahren:kommentieren", args=[antrag.pk]), {"text": "x"}).status_code == 302


def test_reaktion_ist_umschaltbar_und_rein_informativ(client, ordnung):  # noqa: F811
    anna, bernd = mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    antrag = _antrag(ordnung, anna)
    beitrag = chatkern.beitrag_schreiben(antrag, anna, "Ein guter Punkt.")
    client.force_login(bernd)
    ziel = reverse("verfahren:reagieren", args=[antrag.pk, beitrag.pk])
    client.post(ziel)
    assert Reaktion.objects.filter(kommentar=beitrag, mitglied=bernd).count() == 1
    client.post(ziel)  # noch einmal: die Zustimmung wird zurückgenommen
    assert not Reaktion.objects.filter(kommentar=beitrag).exists()
    client.post(ziel)
    inhalt = _seite(client, antrag)
    assert "&#128077; 1" in inhalt or "👍 1" in inhalt
    # Die Reihung bleibt chronologisch — Zustimmung hebt nichts nach oben (Grundregel 6)
    zweiter = chatkern.beitrag_schreiben(antrag, anna, "Zweiter Beitrag ohne Zustimmung.")
    faden = chatkern.faden(antrag, bernd)
    assert [f["k"].pk for f in faden] == [beitrag.pk, zweiter.pk]


def test_aendern_nur_fuenf_minuten_zurueckziehen_laesst_den_faden_stehen(client, ordnung):  # noqa: F811
    anna, bernd = mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    antrag = _antrag(ordnung, anna)
    beitrag = chatkern.beitrag_schreiben(antrag, anna, "Erst so gemeint.")
    antwort = chatkern.beitrag_schreiben(antrag, bernd, "Antwort darauf.", beitrag)

    client.force_login(anna)
    client.post(reverse("verfahren:beitrag_bearbeiten", args=[antrag.pk, beitrag.pk]), {"text": "Doch anders."})
    beitrag.refresh_from_db()
    assert beitrag.text == "Doch anders." and beitrag.bearbeitet_am is not None
    assert "bearbeitet" in _seite(client, antrag)

    # Nach fünf Minuten steht der Text
    Kommentar.objects.filter(pk=beitrag.pk).update(erstellt_am=timezone.now() - timedelta(minutes=6))
    beitrag.refresh_from_db()
    assert not beitrag.darf_bearbeiten(anna)
    client.post(reverse("verfahren:beitrag_bearbeiten", args=[antrag.pk, beitrag.pk]), {"text": "Zu spät."})
    beitrag.refresh_from_db()
    assert beitrag.text == "Doch anders."

    # Fremde Beiträge sind tabu
    client.post(reverse("verfahren:beitrag_entfernen", args=[antrag.pk, antwort.pk]))
    antwort.refresh_from_db()
    assert not antwort.geloescht

    client.post(reverse("verfahren:beitrag_entfernen", args=[antrag.pk, beitrag.pk]))
    beitrag.refresh_from_db()
    assert beitrag.geloescht and beitrag.text == "Doch anders."  # der Text bleibt in der Datenbank
    assert "[vom Verfasser entfernt]" in beitrag.sichtbarer_text()
    inhalt = _seite(client, antrag)
    assert "Doch anders." not in inhalt and "[vom Verfasser entfernt]" in inhalt
    assert "Antwort darauf." in inhalt  # die Antwort darunter bleibt


def test_melden_geht_an_die_verwaltung_und_ist_auditiert(client, ordnung):  # noqa: F811
    anna, bernd = mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    antrag = _antrag(ordnung, anna)
    beitrag = chatkern.beitrag_schreiben(antrag, anna, "Strittiger Beitrag.")
    client.force_login(bernd)
    vorher = AuditEintrag.objects.count()
    client.post(reverse("verfahren:melden", args=[antrag.pk, beitrag.pk]), {"grund": "thema", "erlaeuterung": "Passt nicht."})
    meldung = Meldung.objects.get()
    assert meldung.grund == "thema" and meldung.mitglied == bernd and meldung.erledigt_am is None
    assert AuditEintrag.objects.count() == vorher + 1
    client.post(reverse("verfahren:melden", args=[antrag.pk, beitrag.pk]), {"grund": "recht"})
    assert Meldung.objects.count() == 1  # eine Meldung je Mensch und Beitrag
    client.post(reverse("verfahren:melden", args=[antrag.pk, beitrag.pk]), {"grund": "unsinn"})
    assert Meldung.objects.count() == 1  # unbekannter Grund wird abgewiesen


def test_ausgeblendeter_beitrag_zeigt_den_grund(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    antrag = _antrag(ordnung, anna)
    beitrag = chatkern.beitrag_schreiben(antrag, anna, "Wird ausgeblendet.")
    Kommentar.objects.filter(pk=beitrag.pk).update(
        ausgeblendet_am=timezone.now(), ausgeblendet_grund="Beleidigung"
    )
    inhalt = _seite(client, antrag)
    assert "Wird ausgeblendet." not in inhalt
    assert "von der Verwaltung ausgeblendet: Beleidigung" in inhalt


# ── Lesestand und „neue Beiträge" (FB-G2) ─────────────────────────────────────


def test_neue_beitraege_werden_gezaehlt_und_der_lesestand_rueckt_nach(client, ordnung):  # noqa: F811
    anna, bernd = mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    antrag = _antrag(ordnung, anna)
    chatkern.beitrag_schreiben(antrag, anna, "Vor dem Lesen.")
    assert chatkern.neue_zaehlen(antrag, bernd) == 0  # ohne Lesestand gibt es kein „neu"
    chatkern.gelesen_merken(antrag, bernd)
    chatkern.beitrag_schreiben(antrag, anna, "Nach dem Lesen.")
    chatkern.beitrag_schreiben(antrag, bernd, "Eigener Beitrag zählt nicht.")
    assert chatkern.neue_zaehlen(antrag, bernd) == 1

    client.force_login(bernd)
    inhalt = _seite(client, antrag)
    assert 'class="neulinie"' in inhalt and "1 neuer Beitrag" in inhalt
    client.post(reverse("verfahren:chat_gelesen", args=[antrag.pk]))
    assert chatkern.neue_zaehlen(antrag, bernd) == 0
    assert Lesestand.objects.filter(mitglied=bernd, antrag=antrag).count() == 1


# ── Archivierung bei Hochstufung (FB-G5) ──────────────────────────────────────


def test_hochstufung_raeumt_den_chat_ohne_zu_loeschen(client, ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = _antrag(ordnung, leute[0])
    chatkern.beitrag_schreiben(antrag, leute[0], "Beitrag in der Unterstützungsphase.")
    chatkern.beitrag_schreiben(antrag, leute[1], "Noch einer.")
    assert antrag.kommentare.filter(archiviert_am__isnull=True).count() == 2

    for m in leute[1:]:  # Schwelle erreichen → Hochstufung in die Beratung
        antrag.unterstuetzungen.create(mitglied=m)
    antrag.fortschreiben()
    antrag.refresh_from_db()
    assert antrag.phase == "beratung"
    assert antrag.kommentare.count() == 2, "nichts wird gelöscht (Grundregel 7)"
    assert antrag.kommentare.filter(archiviert_am__isnull=True).count() == 0
    assert {k.phase for k in antrag.kommentare.all()} == {"unterstuetzung"}

    inhalt = _seite(client, antrag)
    assert "Beitrag in der Unterstützungsphase." not in inhalt
    assert "2 Beiträge aus der vorigen Phase liegen im Archiv." in inhalt
    letzter = AuditEintrag.objects.order_by("-lfd").first()
    assert letzter.ereignis["typ"] == "phasenwechsel" and letzter.ereignis["chat_archiviert"] == 2

    # Der neue Chat beginnt leer und nimmt wieder Beiträge an
    neuer = chatkern.beitrag_schreiben(antrag, leute[0], "Jetzt in der Beratung.")
    assert neuer.phase == "beratung"
    assert len(chatkern.faden(antrag, leute[0])) == 1


def test_archivierung_ist_idempotent(ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    antrag = _antrag(ordnung, anna)
    chatkern.beitrag_schreiben(antrag, anna, "Ein Beitrag.")
    erste = antrag.chat_archivieren()
    stempel = antrag.kommentare.get().archiviert_am
    assert erste == 1 and antrag.chat_archivieren() == 0
    assert antrag.kommentare.get().archiviert_am == stempel


def test_nach_verfahrensende_bleibt_der_chat_lesbar_aber_geschlossen(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    antrag = _antrag(ordnung, anna)
    Antrag.objects.filter(pk=antrag.pk).update(phase="angenommen")
    antrag.refresh_from_db()
    assert not chatkern.chat_offen(antrag)
    with pytest.raises(chatkern.ChatGesperrt):
        chatkern.beitrag_schreiben(antrag, anna, "Zu spät.")
    client.force_login(anna)
    inhalt = _seite(client, antrag)
    assert "Das Verfahren ist beendet — der Chat bleibt lesbar." in inhalt


# ── Meine Gespräche (FB-G3) ───────────────────────────────────────────────────


def test_ein_gespraech_entsteht_durch_die_antwort(client, ordnung):  # noqa: F811
    anna, bernd, clara = mitglied_anlegen("anna"), mitglied_anlegen("bernd"), mitglied_anlegen("clara")
    antrag = _antrag(ordnung, anna)
    meiner = chatkern.beitrag_schreiben(antrag, anna, "Mein Beitrag.")
    chatkern.beitrag_schreiben(antrag, clara, "Ein eigener Faden von Clara.")  # kein Gespräch
    assert chatkern.gespraeche(anna) == []

    antwort = chatkern.beitrag_schreiben(antrag, bernd, "Bernd antwortet mir.", meiner)
    zeilen = chatkern.gespraeche(anna)
    assert len(zeilen) == 1
    zeile = zeilen[0]
    assert zeile["gegenueber"] == bernd and zeile["antrag"] == antrag and zeile["letzter"] == antwort
    assert zeile["ungelesen"] is True and chatkern.ungelesene_gespraeche(anna) == 1
    # Aus Bernds Sicht ist es dasselbe Gespräch, aber gelesen (er hat selbst geschrieben)
    assert chatkern.gespraeche(bernd)[0]["gegenueber"] == anna
    assert chatkern.ungelesene_gespraeche(bernd) == 0

    chatkern.gelesen_merken(antrag, anna)
    assert chatkern.ungelesene_gespraeche(anna) == 0

    client.force_login(anna)
    seite = client.get(reverse("verfahren:gespraeche")).content.decode()
    assert bernd.anzeigename in seite and antrag.titel in seite
    assert f'href="/antrag/{antrag.pk}/#k-{antwort.pk}"' in seite


def test_gespraeche_verschwinden_bei_der_hochstufung(ordnung):  # noqa: F811
    leute = [mitglied_anlegen(f"m{i}") for i in range(3)]
    antrag = _antrag(ordnung, leute[0])
    meiner = chatkern.beitrag_schreiben(antrag, leute[0], "Mein Beitrag.")
    chatkern.beitrag_schreiben(antrag, leute[1], "Antwort.", meiner)
    assert len(chatkern.gespraeche(leute[0])) == 1
    for m in leute[1:]:
        antrag.unterstuetzungen.create(mitglied=m)
    antrag.fortschreiben()
    assert chatkern.gespraeche(leute[0]) == [], "archivierte Fäden gehören ins Archiv, nicht ins Panel"


def test_panel_und_griff_nur_fuer_mitglieder(client, ordnung):  # noqa: F811
    anna = mitglied_anlegen("anna")
    assert 'class="g-griff"' not in client.get("/parlament/").content.decode()
    client.force_login(anna)
    inhalt = client.get("/parlament/").content.decode()
    assert 'class="g-griff"' in inhalt and 'x-data="gespraechspanel"' in inhalt
    assert 'href="/gespraeche/"' in inhalt  # ohne JavaScript führt der Griff auf die Seite
    assert 'role="dialog" aria-modal="true"' in inhalt


def test_gespraechsseite_filtert_ungelesene(client, ordnung):  # noqa: F811
    anna, bernd = mitglied_anlegen("anna"), mitglied_anlegen("bernd")
    antrag = _antrag(ordnung, anna)
    meiner = chatkern.beitrag_schreiben(antrag, anna, "Mein Beitrag.")
    chatkern.beitrag_schreiben(antrag, bernd, "Antwort.", meiner)
    client.force_login(anna)
    assert bernd.anzeigename in client.get("/gespraeche/?filter=ungelesen").content.decode()
    chatkern.gelesen_merken(antrag, anna)
    leer = client.get("/gespraeche/?filter=ungelesen").content.decode()
    assert "Nichts Ungelesenes." in leer


@pytest.mark.django_db
def test_gespraeche_sind_gaesten_verschlossen(client):
    """Die eigene Gesprächsliste geht niemanden sonst etwas an — Gäste landen bei der Anmeldung."""
    antwort = client.get(reverse("verfahren:gespraeche"))
    assert antwort.status_code == 302 and "/anmelden/" in antwort["Location"]
