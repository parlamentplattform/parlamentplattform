"""Bildschirmtests des Abstimmungs-Chats und des Archivs (FB-G6, FB-G7): gepinnter Vorschlag
mit Diff, Reihung nach Engagement, Zustimmen und Ablehnen ohne Neuladen, Kritik mit
Textstellenbezug, Archiv-Reiter mit Export."""

from __future__ import annotations

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

HANDY = {"width": 390, "height": 844}


def _mitglied(name="demo1"):
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username=name)


def _vorschlagsantrag():
    """Der Demo-Antrag, dessen Vorschlag den Unterstützern vorliegt."""
    from verfahren.models import Antrag

    return Antrag.objects.filter(entwurf__status="unterstuetzer").first()


def _ruhe(p):
    p.wait_for_function("() => document.getAnimations().every(a => a.playState !== 'running')")


def test_vorschlag_steht_gepinnt_mit_diff_und_reihung(seite, live_server, demo):
    antrag = _vorschlagsantrag()
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/")
    _ruhe(p)
    karte = p.locator(".karte.vorschlag.gepinnt")
    assert karte.count() == 1, "der Vorschlag steht als erste, gepinnte Karte"
    kopf = p.locator(".vorschlagskopf").inner_text()
    assert "Vorschlag des Expertenrats" in kopf and "Runde 1" in kopf
    assert "Reihung: Engagement" in kopf, "die Reihungsregel ist offengelegt (§ 2 Abs 6)"

    # Der Diff steckt in einem <details> — auch ohne Skript erreichbar
    p.locator(".diff summary").click()
    p.wait_for_selector(".diff-text ins")
    assert p.locator(".diff-text ins").count() >= 1 and p.locator(".diff-text del").count() >= 1

    # Der Systembeitrag trägt kein Mitglied und lässt sich nicht melden
    system = p.locator(".blase.system")
    assert system.count() == 1 and "Passt alles" in system.inner_text()
    assert system.locator(".blase-melden").count() == 0


def test_zustimmen_und_ablehnen_ohne_neuladen(seite, live_server, demo):
    antrag = _vorschlagsantrag()
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/")
    _ruhe(p)
    p.evaluate("document.querySelector('.antragsseite').dataset.probe = 'unveraendert'")
    system = p.locator(".blase.system")
    ablehnen = system.locator(".blase-knopf.ablehnen")
    assert ablehnen.count() == 1, "im Abstimmungs-Chat gibt es beide Zeichen"
    ablehnen.click()
    p.wait_for_function(
        "() => document.querySelector('.blase.system .blase-knopf.ablehnen')?.getAttribute('aria-pressed') === 'true'"
    )
    assert p.evaluate("document.querySelector('.antragsseite').dataset.probe") == "unveraendert"
    # Umschalten auf Zustimmung: eine Reaktion je Mitglied
    p.locator(".blase.system .blase-knopf.zustimmen").click()
    p.wait_for_function(
        "() => document.querySelector('.blase.system .blase-knopf.zustimmen')?.getAttribute('aria-pressed') === 'true'"
    )
    assert p.locator(".blase.system .blase-knopf.ablehnen").get_attribute("aria-pressed") == "false"


def test_kritik_verlangt_einen_absatzbezug(seite, live_server, demo):
    antrag = _vorschlagsantrag()
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/")
    _ruhe(p)
    vorher = p.locator(".blase").count()
    p.locator(".kritikwahl .schalter input").check()
    p.wait_for_selector(".absatzwahl", state="visible")
    assert p.locator(".absatzwahl option").count() >= 2, "die Absätze des Vorschlags stehen zur Wahl"
    p.locator(".chatzeile textarea").fill(
        "Der zweite Absatz lässt offen, wer die Beleuchtung bezahlt — das gehört ausdrücklich geregelt."
    )
    p.wait_for_timeout(300)
    p.locator(".chatzeile button[type=submit]").click()  # ohne Absatzwahl: abgewiesen
    p.wait_for_timeout(800)
    assert p.locator(".blase").count() == vorher, "ohne Textstellenbezug keine Kritik"

    p.locator(".kritikwahl .schalter input").check()
    p.wait_for_selector(".absatzwahl", state="visible")
    p.select_option(".absatzwahl select", "2")
    p.locator(".chatzeile textarea").fill(
        "Der zweite Absatz lässt offen, wer die Beleuchtung bezahlt — das gehört ausdrücklich geregelt."
    )
    p.wait_for_timeout(300)
    p.locator(".chatzeile button[type=submit]").click()
    p.wait_for_function("(n) => document.querySelectorAll('.blase').length > n", arg=vorher)
    assert "Kritik · Absatz 2" in p.locator(".blase.kritik").last.inner_text()


def test_archiv_zeigt_die_zeitleiste_und_laesst_sich_mitnehmen(seite, live_server, demo):
    antrag = _vorschlagsantrag()
    p = seite(als=_mitglied())
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/")
    _ruhe(p)
    assert p.locator('.zreiter[href="#zone-archiv"]').count() == 1
    p.locator('.zreiter[href="#zone-archiv"]').click()
    p.wait_for_timeout(400)
    bloecke = p.locator(".archiv-block")
    assert bloecke.count() >= 2, "Unterstützungsphase, Beratung und die Vorschlagsrunde"
    texte = p.locator("#zone-archiv").inner_text()
    assert "Unterstützungsphase" in texte and "Vorschlagsberatung" in texte
    assert "Audit-Spur" in texte

    with p.expect_download() as vorgang:
        p.locator('.archiv-export a[href$="archiv.json"]').click()
    assert vorgang.value.suggested_filename == f"antrag-{antrag.pk}-archiv.json"


def test_ohne_javascript_bleibt_der_abstimmungschat_bedienbar(seite, live_server, demo):
    antrag = _vorschlagsantrag()
    p = seite(js=False, als=_mitglied())
    p.goto(f"{live_server.url}/antrag/{antrag.pk}/")
    p.wait_for_timeout(600)
    assert p.locator(".karte.vorschlag.gepinnt").count() == 1
    assert p.locator(".blase.system").count() == 1
    # Reagieren ohne Skript: gewöhnliches Formular, die Seite lädt neu
    knopf = ".blase.system .blase-knopf.zustimmen"
    vorher = p.locator(knopf).get_attribute("aria-pressed")
    p.locator(knopf).click()
    p.wait_for_load_state()
    assert p.locator(knopf).get_attribute("aria-pressed") != vorher, "die Reaktion schaltet um"
    # Das Archiv steht als <details> offen
    assert p.locator("#zone-archiv .archiv-block").count() >= 2
