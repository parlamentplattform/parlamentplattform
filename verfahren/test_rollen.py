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
#: Abwesenheit einer Anmeldung, die beiden Mitgliedszustände sind Felder am Mitglied, die
#: Verwaltung hängt an `ist_admin`, und der Mandatar hängt an einem offenen Mandat
#: (`Mitglied.ist_mandatar`) — kein Gremium, weil ein Mandat nicht befristet berufen wird
#: (§ 6 Abs 8) und keine Beschlussnummer trägt. Alles andere muss ein `Gremium` sein.
OHNE_GREMIUM = {"gast", "mitglied", "mitglied_ruht", "verwaltung", "mandatar"}

#: URL-Namen, die die Matrix schon nennt, obwohl sie erst mit der Zusammenführung eines
#: Bauschritts entstehen. Im Regelfall leer — ein Eintrag hier ist eine Zusage, die der
#: nächste Commit einlösen muss; nach der Zusammenführung muss die Menge wieder leer sein.
ERWARTET_NACH_ZUSAMMENFUEHRUNG: set[str] = set()


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
    # Die Grundlagen, auf die sich die fünf Nicht-Gremien-Rollen berufen, gibt es wirklich:
    assert hasattr(Mitglied, "ist_admin")
    assert hasattr(Mitglied, "ist_mandatar")
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
            if not f.urlname or f.urlname in ERWARTET_NACH_ZUSAMMENFUEHRUNG:
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
    """FB-K6: die vier Rollen, die fast jeden betreffen.

    Entscheidung des Gründers vom 5.9.2026: „Mitglied in Aufnahme oder pausiert" statt der
    Verwaltung. Die Verwaltung betrifft eine Handvoll Menschen; „in Aufnahme" ist der Zustand
    jedes Neuen und jedes Beitragssäumigen — und genau der fragt sich, warum er nicht mitreden
    kann. Die Verwaltung steht weiter auf /rollen/, nur nicht mehr auf der ersten Seite."""
    auswahl = [r.schluessel for r in alle_rollen(GRUPPEN) if r.auf_der_startseite]
    assert auswahl == ["gast", "mitglied", "mitglied_ruht", "mandatar"]


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
    for schluessel in ("gast", "mitglied", "mitglied_ruht", "mandatar"):
        rolle = next(r for r in alle_rollen(GRUPPEN) if r.schluessel == schluessel)
        assert rolle.name in inhalt


def test_die_matrix_widerspricht_sich_nicht_zur_fachliste_und_auslosung():
    """Befund #54: Beim Expertenrat stand „Heute gibt es weder Fachliste noch Auslosung", drei
    Zeilen tiefer führte dieselbe Karte ● „aus der Fachliste ausgelost werden" mit Link. Seit
    0.44 gibt es beides — der Weg-hinein-Text muss es sagen, und kein Text darf es bestreiten."""
    rollen = {r.schluessel: r for r in alle_rollen(GRUPPEN)}
    for schluessel in ("expertenrat1", "expertenrat2"):
        text = rollen[schluessel].wie_hinein
        assert "weder Fachliste" not in text and "von Hand" not in text, f"{schluessel}: {text}"
        assert "Fachliste" in text and "gelost" in text, f"{schluessel} nennt den heutigen Weg nicht"
    gelost = [f for f in rollen["expertenrat1"].faehigkeiten if "ausgelost" in f.titel]
    assert gelost and gelost[0].stand is Stand.VERFUEGBAR and gelost[0].urlname == "gremien:fachliste"


def test_was_ein_mitglied_kann_fehlt_beim_koordinationsrat_nicht():
    """Befund #54, innerer Widerspruch: Das Mitglied führte „Eine Einschätzung … beanstanden" als
    ● verfügbar, der Koordinationsrat nannte denselben Weg drei Karten weiter als fehlend."""
    rollen = {r.schluessel: r for r in alle_rollen(GRUPPEN)}
    verfuegbar = any(
        "beanstanden" in f.titel and f.stand is Stand.VERFUEGBAR for f in rollen["mitglied"].faehigkeiten
    )
    assert verfuegbar, "die Beanstandung durch Mitglieder gibt es (0.43)"
    for f in rollen["koordinationsrat"].faehigkeiten:
        assert "beanstanden, fehlen" not in f.einschraenkung, f.einschraenkung


def test_fassung_3_der_mandatar_ist_eine_rolle_im_code():
    """Bauschritt S10: Der Mandatar hängt am offenen Mandat (`Mitglied.ist_mandatar`), die
    Willkommensseite zeigt seine ersten fünf Zeilen — sie müssen die sein, die ein Mandatar
    täglich braucht, und keine davon darf noch „kommt mit S10" tragen."""
    from mitglieder.models import Mitglied

    assert VERSION >= 3
    assert isinstance(Mitglied.ist_mandatar, property)
    rollen = {r.schluessel: r for r in alle_rollen(GRUPPEN)}
    mandatar = rollen["mandatar"]
    assert mandatar.im_code, "seit 0.46 gibt es die Rolle im Code (Mitglied.ist_mandatar)"
    erste_fuenf = [f.titel for f in mandatar.faehigkeiten[:5]]
    assert any("Kandidatur" in t for t in erste_fuenf)
    assert any("Instant-Report" in t for t in erste_fuenf)
    assert any("Mandatsfrage" in t for t in erste_fuenf)
    assert any("Rechenschaftsregister" in t for t in erste_fuenf)
    for f in mandatar.faehigkeiten:
        assert f.stand is not Stand.GEPLANT, f.titel
        if f.stand is Stand.VERFUEGBAR:
            assert not f.bauschritt and not f.einschraenkung, f.titel
        assert "S10" not in f.einschraenkung and "S10" not in f.bauschritt, f.titel
    assert "S10" not in mandatar.wie_hinein
    # Der Weg hinein nennt nicht mehr die Verwaltung als Eintragende „heute noch".
    assert "heute noch" not in mandatar.wie_hinein


def test_fassung_3_die_bewerbung_im_fremden_kandidatur_antrag_gilt_als_gebaut():
    """Befund FP-13: Die Zeile „Kandidatur einbringen oder sich an einer bestehenden beteiligen“
    behauptete seit Fassung 1, eine eigene Bewerbung im fremden Antrag gebe es nicht — der Code
    hat sie seit dem 1.9.2026 (`bewerben` → `bewerbung_einreichen`). Die Zeile ist ●, nennt den
    zweiten Weg als Ort, und der Mandatar steht damit bei neun von zehn ● (◐ bleibt der
    Vollzugsbericht)."""
    from verfahren.models import bewerbung_einreichen  # noqa: F401 — die Fähigkeit, um die es geht

    rollen = {r.schluessel: r for r in alle_rollen(GRUPPEN)}
    mandatar = rollen["mandatar"]
    zeile = next(f for f in mandatar.faehigkeiten if f.titel.startswith("Kandidatur für ein Mandat"))
    assert zeile.stand is Stand.VERFUEGBAR and zeile.urlname == "verfahren:einbringen"
    assert "Antragsseite" in zeile.ort and not zeile.einschraenkung
    assert "eigene Bewerbung im fremden Antrag gibt es so nicht" not in " ".join(
        f.einschraenkung for f in mandatar.faehigkeiten
    )
    assert len(mandatar.faehigkeiten) == 10
    assert sum(f.stand is Stand.VERFUEGBAR for f in mandatar.faehigkeiten) == 9
    (teilweise,) = [f for f in mandatar.faehigkeiten if f.stand is Stand.TEILWEISE]
    assert "Vollzug" in teilweise.titel
    assert VERSION == 3  # Berichtigung einer falschen Auskunft, kein Statuswechsel — keine neue Fassung


def test_fassung_3_profil_rechenschaft_und_unvereinbarkeit():
    """Die übrigen Zeilen der Fassung 3: Profil und Pseudonym gehören dem Mitglied, der Gast
    liest das Rechenschaftsregister, die Verwaltung verknüpft Mandate mit der Kandidatur, und
    der Integritätsrat-Text behauptet nicht mehr, niemand prüfe Unvereinbarkeiten."""
    rollen = {r.schluessel: r for r in alle_rollen(GRUPPEN)}
    profil = [f for f in rollen["mitglied"].faehigkeiten if f.urlname == "mitglieder:profil"]
    assert len(profil) == 2 and all(f.stand is Stand.VERFUEGBAR for f in profil)
    assert any("Austritt" in f.titel and "Nebenwohnsitz" in f.titel for f in profil)
    assert any("Pseudonym" in f.titel for f in profil)
    gast = [f for f in rollen["gast"].faehigkeiten if f.urlname == "mandatare:rechenschaft"]
    assert gast and gast[0].stand is Stand.VERFUEGBAR
    verwaltung = [f for f in rollen["verwaltung"].faehigkeiten if "Kandidatur verknüpfen" in f.titel]
    assert verwaltung and verwaltung[0].stand is Stand.VERFUEGBAR
    assert all("kommt mit S10" not in f.einschraenkung for f in rollen["verwaltung"].faehigkeiten)
    assert "prüft niemand" not in rollen["integritaetsrat"].wie_hinein
    assert "bei der Berufung" in rollen["integritaetsrat"].wie_hinein
    assert "ausgetreten" in rollen["mitglied_ruht"].hinweis
