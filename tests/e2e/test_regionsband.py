"""E-43 Zeile 1 (GP-171, Variante c): Im Regionsband am Desktop rollt das Feld, statt die Kachel zu
beschneiden. Bei 1440×900 ragt kein Element einer Regionskachel über seine Kachel hinaus und keines wird
von ihr (oder einem Teil der Kachel) abgeschnitten — Kopf, Titel, Phase und Ort, Frist und Knopf; der
Gebietsname einer Kachel aus fremdem Gebiet bleibt sichtbar. Geprüft als Gast und als Mitglied, mit und
ohne JavaScript."""

from __future__ import annotations

from datetime import timedelta

import pytest

pytestmark = [pytest.mark.django_db(transaction=True), pytest.mark.e2e]

DESKTOP = {"width": 1440, "height": 900}

# Je Regionskachel: jedes gezeichnete Element liegt in seiner Kachel und in jedem abschneidenden Vorfahren
# bis zur Kachel. Der Titel kürzt sich gewollt mit Ellipse (eine Zeile) — sein Kasten muss trotzdem ganz
# in der Kachel stehen.
UEBERSTAND = """() => {
  const funde = [];
  const kacheln = Array.from(document.querySelectorAll('#feld-region .rband .spur > .kachel'));
  for (const k of kacheln) {
    for (const e of k.querySelectorAll('*')) {
      const s = getComputedStyle(e);
      if (s.display === 'none' || s.visibility === 'hidden' || e.closest('.k-erfasst')) continue;
      const r = e.getBoundingClientRect();
      if (r.width === 0 && r.height === 0) continue;
      for (let a = e.parentElement; a; a = a.parentElement) {
        const sa = getComputedStyle(a);
        const schneidet = a === k || sa.overflowX !== 'visible' || sa.overflowY !== 'visible';
        if (schneidet) {
          const ar = a.getBoundingClientRect();
          if (r.top < ar.top - 0.5 || r.bottom > ar.bottom + 0.5 || r.left < ar.left - 0.5 || r.right > ar.right + 0.5) {
            funde.push(`${k.dataset.antrag || 'live'}: ${e.tagName.toLowerCase()}.${String(e.className).trim()} `
              + `ragt ${Math.round(r.bottom - ar.bottom)} px unter ${a.tagName.toLowerCase()}.${String(a.className).trim()}`);
            break;
          }
        }
        if (a === k) break;
      }
    }
  }
  return {funde, anzahl: kacheln.length};
}"""


def _mitglied():
    from mitglieder.models import Mitglied

    return Mitglied.objects.get(username="demo1")


def _beratung_abgelaufen_in(gebiet):
    """Eine Beratung im Ort, deren Frist um ist (Fortschreibung steht aus) — eine Kachel mit Text statt Knopf."""
    from django.utils import timezone

    from verfahren.models import Antrag

    beratung = Antrag.objects.filter(phase="beratung").first()
    tage = beratung.policy().beratung_tage
    Antrag.objects.filter(pk=beratung.pk).update(
        phase_beginn=timezone.now() - timedelta(days=tage, hours=1), ebene="gemeinde", gebiet=gebiet,
    )


def _wanderin():
    """Ein Mitglied, das nach dem Einbringen eines Gemeindeantrags umgezogen ist: Die Kachel aus dem alten
    Ort steht über den festgehaltenen Teilnehmerkreis im Band und nennt ihr Gebiet (GP-054)."""
    from mitglieder.models import Gemeinde, Mitglied, Wohnsitzart
    from verfahren.models import Verfahrensordnung, antrag_einbringen
    from verfahren.test_views_aktionen import mitglied_anlegen

    ordnung = Verfahrensordnung.objects.filter(aktiv=True).first()
    # zwei Gemeinden aus dem Verzeichnis (die Migrationen füllen es), die längste als alter Wohnort
    alt, neu = sorted(Gemeinde.objects.filter(bundesland="oberoesterreich")[:40], key=lambda g: -len(g.name))[:2]
    m = mitglied_anlegen("wanderin", tage=800, gemeinde=alt.name)
    m.wohnsitz, m.wohnsitz_art = alt, Wohnsitzart.OESTERREICH
    m.save(update_fields=["wohnsitz", "wohnsitz_art"])
    antrag_einbringen(m, "Ein Gemeindeantrag aus dem alten Wohnort mit langem Titel", "Wortlaut.", "", ordnung,
                      ebene="gemeinde", neuer_teilnehmerkreis=True)
    Mitglied.objects.filter(pk=m.pk).update(wohnsitz=neu, gemeinde=neu.name)
    for i in range(2):
        antrag_einbringen(m, f"Sache in Neuort {i}", "Wortlaut.", "", ordnung, ebene="gemeinde", gebiet=neu.name)
    m.refresh_from_db()
    m.alter_ort = alt.name
    return m


def _pruefen(p, live_server, js):
    p.goto(f"{live_server.url}/parlament/")
    p.wait_for_load_state("load")
    p.wait_for_timeout(400)
    ergebnis = p.evaluate(UEBERSTAND)
    assert ergebnis["anzahl"] >= 3
    assert ergebnis["funde"] == [], ergebnis["funde"]
    # Was unter der Sichtkante des Feldes liegt, erreicht man durch Rollen des Feldes
    korpus = p.locator("#feld-region .feld-korpus")
    letzte = p.locator("#feld-region .rband .spur > .kachel").last
    letzte.scroll_into_view_if_needed()
    kr, lr = korpus.bounding_box(), letzte.bounding_box()
    assert kr["y"] - 0.5 <= lr["y"] and lr["y"] + lr["height"] <= kr["y"] + kr["height"] + 0.5


@pytest.mark.parametrize("js", [True, False], ids=["mit-js", "ohne-js"])
@pytest.mark.parametrize("angemeldet", [False, True], ids=["gast", "mitglied"])
def test_e43_regionskachel_wird_nicht_beschnitten(seite, live_server, demo, angemeldet, js):
    demo1 = _mitglied()
    _beratung_abgelaufen_in(demo1.wohnsitz.name if demo1.wohnsitz else "St. Marienkirchen an der Polsenz")
    p = seite(viewport=DESKTOP, js=js, reduziert=True, als=demo1 if angemeldet else None)
    _pruefen(p, live_server, js)
    if not angemeldet:
        # Gäste sehen den Ort jeder Regionskachel und den Weg zur Anmeldung ganz
        orte = p.locator("#feld-region .rband .spur > .kachel .rest.ort")
        assert orte.count() >= 3 and all(orte.nth(i).is_visible() for i in range(orte.count()))
        anmelden = p.locator("#feld-region .kachel a", has_text="Anmelden zum Abstimmen").first
        assert anmelden.is_visible()


@pytest.mark.parametrize("js", [True, False], ids=["mit-js", "ohne-js"])
def test_e43_gebietsname_einer_kachel_aus_fremdem_gebiet_bleibt_sichtbar(seite, live_server, demo, js):
    m = _wanderin()
    p = seite(viewport=DESKTOP, js=js, reduziert=True, als=m)
    _pruefen(p, live_server, js)
    ort = p.locator("#feld-region .rband.r1 .kachel .rest.ort", has_text=m.alter_ort)
    assert ort.count() == 1 and ort.is_visible()
    assert p.locator("#feld-region .rband.r1 .kachel .rest", has_text="Teilnehmerkreis vom").first.is_visible()
