"""Die Rollenübersicht „Wer darf was" (FB-K6) — und ihr Wächter.

Die Seite behauptet öffentlich, wer auf der Plattform was darf. Sie ist damit genau so lange
nützlich, wie sie stimmt: Eine Fähigkeit, die als verfügbar ausgewiesen ist und es nicht ist,
ist eine Zusage an Menschen, die sich darauf verlassen. Diese Tests halten die Matrix gegen den
Code — jede Adresse muss auflösbar sein, jede Rolle des Codes muss vorkommen, und keine Zeile
darf eine Adresse tragen, die es nicht gibt.
"""

from __future__ import annotations

import pytest
from django.urls import NoReverseMatch, reverse

from plattform_core.rollen import GRUPPEN, VERSION, Stand, alle_rollen, zaehlung

#: Rollen, die kein Gegenstück im Code haben, weil sie keines haben können: „Gast" ist die
#: Abwesenheit einer Anmeldung, die beiden Mitgliedszustände sind Felder am Mitglied, und die
#: Verwaltung hängt an `ist_admin`. Alles andere muss ein `Gremium` sein.
OHNE_GREMIUM = {"gast", "mitglied", "mitglied_ruht", "verwaltung"}


def test_die_matrix_traegt_ihre_fassung():
    assert VERSION >= 1
    assert len(alle_rollen(GRUPPEN)) == 14, "FB-K6 nennt vierzehn Rollen"


def test_jede_rolle_des_codes_steht_in_der_matrix():
    """Der Wächter aus FB-K6: Ein neues Gremium ohne Matrix-Eintrag muss anschlagen.

    Sonst wäre die Seite am Tag nach dem nächsten Rat still falsch — und niemand merkte es,
    weil eine fehlende Zeile nichts kaputt macht, sondern nur etwas verschweigt."""
    from gremien.models import Gremium

    vorhanden = {r.schluessel for r in alle_rollen(GRUPPEN)}
    fehlend = [wert for wert in Gremium.values if wert not in vorhanden]
    assert not fehlend, f"Diese Gremien fehlen in plattform_core/rollen.py: {fehlend}"


def test_jede_matrix_zeile_hat_eine_entsprechung():
    """Umgekehrt: Wer in der Matrix als „im Code vorhanden" steht, muss es auch sein."""
    from gremien.models import Gremium
    from mitglieder.models import Mitglied, Mitgliedsstatus

    bekannt = set(Gremium.values) | OHNE_GREMIUM
    behauptet = {r.schluessel for r in alle_rollen(GRUPPEN) if r.im_code}
    assert behauptet <= bekannt, f"Ohne Entsprechung im Code: {sorted(behauptet - bekannt)}"
    # Die Grundlagen, auf die sich die vier Nicht-Gremien-Rollen berufen, gibt es wirklich:
    assert hasattr(Mitglied, "ist_admin")
    assert Mitgliedsstatus.PAUSIERT in Mitgliedsstatus.values


def test_die_beschlussnummern_kennen_dieselben_gremien():
    """Ein neues Gremium ohne Kürzel bekäme Beschlüsse mit der Nummer „GR-2026-01“.

    Der Rückfall in `beschlussnummer` ist bequem und würde genau deshalb verdecken, dass jemand
    einen Rat hinzugefügt und die Tabelle vergessen hat."""
    from gremien.models import GREMIUMSKUERZEL, Gremium

    assert set(GREMIUMSKUERZEL) == set(Gremium.values)


def test_jeder_mitgliedszustand_kommt_irgendwo_vor():
    """Ein Zustand, den der Code kennt und die Übersicht verschweigt, ist eine Zeile ohne Rolle.

    `ausgeschlossen` steht nicht als eigene Karte da — die Satzung kennt keinen ausgeschlossenen
    Mitwirkenden, nur einen beendeten. Er muss aber erklärt werden, sonst fragt sich jemand,
    warum sein Konto stumm ist."""
    from mitglieder.models import Mitgliedsstatus

    text = " ".join(
        [r.name + " " + r.was_sie_ist + " " + r.wie_hinein + " " + r.hinweis for r in alle_rollen(GRUPPEN)]
    ).lower()
    for wert, name in Mitgliedsstatus.choices:
        assert wert.lower() in text or name.split(" ")[0].lower() in text, (
            f"Der Mitgliedszustand „{name}“ kommt in keiner Rollenkarte vor."
        )


@pytest.mark.django_db
def test_jede_genannte_adresse_ist_erreichbar():
    """Ein toter Link auf dieser Seite wäre schlimmer als gar keiner: Er behauptet, es gebe die
    Funktion schon."""
    kaputt = []
    for r in alle_rollen(GRUPPEN):
        for f in r.faehigkeiten:
            if not f.urlname:
                continue
            try:
                reverse(f.urlname)
            except NoReverseMatch:
                kaputt.append(f"{r.name}: {f.titel} → {f.urlname}")
    assert not kaputt, "Nicht auflösbare Adressen:\n  " + "\n  ".join(kaputt)


def test_geplantes_traegt_seinen_bauschritt_und_keine_adresse():
    """Wer ein ○ liest, soll erfahren, wann es ein ● wird — sonst ist es nur ein Achselzucken."""
    ohne = [
        f"{r.name}: {f.titel}"
        for r in alle_rollen(GRUPPEN)
        for f in r.faehigkeiten
        if f.stand is Stand.GEPLANT and not f.bauschritt
    ]
    assert not ohne, "Geplant ohne Bauschritt:\n  " + "\n  ".join(ohne)


def test_teilweise_sagt_was_fehlt():
    """Ein ◐ ohne Erklärung ist ein Rätsel, kein Soll/Ist-Abgleich."""
    stumm = [
        f"{r.name}: {f.titel}"
        for r in alle_rollen(GRUPPEN)
        for f in r.faehigkeiten
        if f.stand is Stand.TEILWEISE and not f.einschraenkung
    ]
    assert not stumm, "Teilweise ohne Angabe, was fehlt:\n  " + "\n  ".join(stumm)


def test_jede_rolle_sagt_was_sie_ist_und_wie_man_hineinkommt():
    unvollstaendig = [
        r.name
        for r in alle_rollen(GRUPPEN)
        if not r.was_sie_ist.strip() or not r.wie_hinein.strip() or not r.satzung.strip()
    ]
    assert not unvollstaendig, f"Ohne Satz, Weg oder Satzungsbezug: {unvollstaendig}"


def test_vier_rollen_stehen_auf_der_willkommensseite():
    """FB-K6: Gast, Mitglied, Mandatar, Verwaltung — die, die fast jeden betreffen."""
    auswahl = [r.schluessel for r in alle_rollen(GRUPPEN) if r.auf_der_startseite]
    assert auswahl == ["gast", "mitglied", "mandatar", "verwaltung"]


@pytest.mark.django_db
def test_die_seite_zeigt_alle_rollen_und_den_soll_ist_abgleich(client):
    inhalt = client.get(reverse("verfahren:rollen")).content.decode()
    for r in alle_rollen(GRUPPEN):
        assert r.name in inhalt, f"Rolle fehlt auf der Seite: {r.name}"
    assert "○" in inhalt and "●" in inhalt  # beide Seiten des Abgleichs sind zu sehen
    zahlen = zaehlung(GRUPPEN)
    assert str(zahlen["geplant"]) in inhalt


@pytest.mark.django_db
def test_die_willkommensseite_zeigt_vier_karten_und_den_weg_zur_vollen_liste(client):
    inhalt = client.get(reverse("verfahren:index")).content.decode()
    assert reverse("verfahren:rollen") in inhalt
    for schluessel in ("gast", "mitglied", "mandatar", "verwaltung"):
        rolle = next(r for r in alle_rollen(GRUPPEN) if r.schluessel == schluessel)
        assert rolle.name in inhalt
