"""Das öffentliche Audit-Log `/audit/` (Bestandsaufnahme A7, Schritt 2 · 0.52.0; Entscheidung F2 a):
für Gäste lesbar, filterbar, blätterbar, ohne JavaScript bedienbar — Mitgliedskennungen und Personengründe
erscheinen als „•“, Verwaltungs- und Verfahrenseinträge stehen beide darin."""

import re

import pytest
from django.urls import reverse

from verfahren.audit_pruefung import LAUF
from verfahren.hintergrund import LAEUFE, ausfuehren
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db

AUSSCHLUSS = {"typ": "verwaltung", "aktion": "ausschliessen", "mitglied": 4711, "durch": 815,
              "grund": "Frau Beispielname hat mehrfach gegen § 4 verstoßen."}


def _seite(client, **filter_):
    return client.get(reverse("verfahren:audit"), filter_).content.decode()


def test_gaeste_sehen_verwaltung_und_verfahren_ohne_personenbezug(client):
    AuditEintrag.anhaengen({"typ": "phasenwechsel", "antrag": 12, "neue_phase": "beratung"})
    AuditEintrag.anhaengen(AUSSCHLUSS)
    AuditEintrag.anhaengen({"typ": "parameter_geaendert", "schluessel": "k", "alt": "1", "neu": "2",
                            "grund": "Test der Registerbegründung."})
    inhalt = _seite(client)
    assert "phasenwechsel" in inhalt and "verwaltung" in inhalt and "parameter_geaendert" in inhalt
    # Kennungen sind Ziffern, die zufällig auch in einem Hash stehen können — geprüft wird das Feld
    assert "<dd>4711</dd>" not in inhalt and "<dd>815</dd>" not in inhalt and "Beispielname" not in inhalt
    assert "<dt>mitglied</dt><dd>•</dd>" in inhalt and "<dt>durch</dt><dd>•</dd>" in inhalt
    assert "geschwärzt" in inhalt and "•" in inhalt
    assert "Test der Registerbegründung." in inhalt  # Gründe zu Parametern bleiben sichtbar
    assert reverse("verfahren:antrag", args=[12]) in inhalt


def test_neueste_zuerst_und_filter_nach_antrag_und_art(client):
    for nr in (1, 2, 3):
        AuditEintrag.anhaengen({"typ": "stimme", "antrag": nr, "marke": f"eintrag-nr-{nr}"})
    AuditEintrag.anhaengen({"art": "beitrag_gemeldet", "antrag": 2, "beitrag": 9, "grund": "thema"})
    inhalt = _seite(client)
    assert inhalt.index("eintrag-nr-3") < inhalt.index("eintrag-nr-1")
    nur_zwei = _seite(client, antrag="2")
    assert "eintrag-nr-2" in nur_zwei and "eintrag-nr-1" not in nur_zwei and "beitrag_gemeldet" in nur_zwei
    gemeldet = _seite(client, art="beitrag_gemeldet")  # ältere Art unter `art` wird gefunden
    assert "beitrag_gemeldet" in gemeldet and "eintrag-nr-2" not in gemeldet
    assert "eintrag-nr-1" in _seite(client, antrag="abc", art="<script>")  # Unlesbares wird übergangen


def test_blaettern_ueber_links_ohne_javascript(client):
    from parameter.models import Parameter, erstbestand_sicherstellen

    erstbestand_sicherstellen()
    Parameter.objects.filter(schluessel="audit-seite-eintraege").update(wert="10")
    for i in range(25):
        AuditEintrag.anhaengen({"typ": "probe", "nr": i})
    erste = _seite(client)
    assert erste.count('class="audit-zeile"') == 10 and "Seite 1 von 3" in erste and "seite=2" in erste
    dritte = _seite(client, seite="3")
    assert dritte.count('class="audit-zeile"') == 5 and "seite=2" in dritte


def test_die_seite_nennt_das_ergebnis_der_pruefung(client):
    assert "noch nicht geprüft" in _seite(client)
    AuditEintrag.anhaengen({"typ": "probe"})
    ausfuehren(next(la for la in LAEUFE if la.name == LAUF))
    inhalt = _seite(client)
    assert re.search(r"intakt, 1 Eintrag(?!e)", inhalt)  # Einzahl, nicht „1 Einträge“
    kopf = AuditEintrag.objects.get().hash
    assert f">{kopf}</code>" in inhalt  # der volle Kopf steht sichtbar da, nicht nur im Titel


def test_audit_json_blaettert_aufsteigend_und_blendet_aus(client):
    from parameter.models import Parameter, erstbestand_sicherstellen

    erstbestand_sicherstellen()
    Parameter.objects.filter(schluessel="audit-seite-eintraege").update(wert="10")
    for i in range(12):
        AuditEintrag.anhaengen({"typ": "probe", "nr": i})
    AuditEintrag.anhaengen(AUSSCHLUSS)
    erste = client.get(reverse("verfahren:audit_json")).json()
    assert [e["ereignis"]["nr"] for e in erste["eintraege"]] == list(range(10))
    assert erste["weiter"] and "ab=" in erste["weiter"]
    zweite = client.get(erste["weiter"]).json()
    assert len(zweite["eintraege"]) == 3 and zweite["weiter"] is None
    letzter = zweite["eintraege"][-1]
    assert letzter["geschwaerzt"] and letzter["ereignis"]["mitglied"] == "•" and letzter["ereignis"]["grund"] == "•"
    assert len(letzter["hash"]) == 64 and 4711 not in letzter["ereignis"].values()


def test_fusszeile_verlinkt_das_audit_log(client):
    assert reverse("verfahren:audit") in client.get(reverse("verfahren:index")).content.decode()


def test_englisch_ohne_deutsche_reste(client):
    from django.utils import translation

    AuditEintrag.anhaengen(AUSSCHLUSS)
    try:
        inhalt = client.get(reverse("verfahren:audit"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    finally:
        translation.activate("de")  # die Sprache der Anfrage bleibt sonst am Faden hängen
    assert "Audit log" in inhalt and "redacted" in inhalt and "geschwärzt" not in inhalt


@pytest.mark.parametrize("wert", ["²", "9" * 5000, "-3", "1e5"])
def test_unlesbare_nummern_werden_uebergangen_nicht_500(client, wert):
    """Prüfung 0.52.0 (zeit): `str.isdigit` ließ „²“ und überlange Zahlen durch, `int()` warf."""
    AuditEintrag.anhaengen({"typ": "probe"})
    assert client.get(reverse("verfahren:audit"), {"antrag": wert}).status_code == 200
    assert client.get(reverse("verfahren:audit_json"), {"ab": wert, "antrag": wert}).status_code == 200


def test_die_arten_kommen_mit_einer_kleinen_abfrage(client, django_assert_max_num_queries):
    """Prüfung 0.52.0 (zeit): DISTINCT griff wegen der Standard-Reihung nicht — jede Anfrage lud das ganze
    Log. Jetzt eine Zeile je Art, einmal je Anfrage."""
    from verfahren.views_audit import arten

    for i in range(30):
        AuditEintrag.anhaengen({"typ": "probe" if i % 2 else "stimme", "nr": i})
    AuditEintrag.anhaengen({"art": "beitrag_gemeldet"})
    assert arten() == ["beitrag_gemeldet", "probe", "stimme"]
    with django_assert_max_num_queries(12):
        client.get(reverse("verfahren:audit"), {"art": "probe"})
    assert 'class="audit-zeile"' not in _seite(client, art="unbekannt")  # keine Treffer, kein Fehler


def test_ein_bruch_nennt_grund_und_fuehrt_zur_stelle(client):
    eintraege = [AuditEintrag.anhaengen({"typ": "probe", "nr": i}) for i in range(3)]
    AuditEintrag.objects.filter(pk=eintraege[1].pk).update(ereignis={**eintraege[1].ereignis, "nr": 99})
    ausfuehren(next(la for la in LAEUFE if la.name == LAUF))
    inhalt = _seite(client)
    assert f"gebrochen bei Eintrag {eintraege[1].lfd}" in inhalt
    assert f'#e-{eintraege[1].lfd}"' in inhalt and "Inhalt passt nicht zum Hash" in inhalt


def test_die_seite_nennt_bis_wohin_geprueft_ist_und_den_vollen_kopf(client):
    eintraege = [AuditEintrag.anhaengen({"typ": "probe", "nr": i}) for i in range(2)]
    ausfuehren(next(la for la in LAEUFE if la.name == LAUF))
    AuditEintrag.anhaengen({"typ": "probe", "nr": 9})  # nach der Prüfung
    inhalt = _seite(client)
    assert f"bis Eintrag {eintraege[-1].lfd}" in inhalt and f">{eintraege[-1].hash}</code>" in inhalt
