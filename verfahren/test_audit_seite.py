"""Das öffentliche Audit-Log `/audit/` (Bestandsaufnahme A7, Schritt 2 · 0.52.0; Entscheidung F2 a):
für Gäste lesbar, filterbar, blätterbar, ohne JavaScript bedienbar — Mitgliedskennungen und Personengründe
erscheinen als „•“, Verwaltungs- und Verfahrenseinträge stehen beide darin."""

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
    assert "gekürzt" in inhalt and "•" in inhalt
    assert "Test der Registerbegründung." in inhalt  # Gründe zu Parametern bleiben sichtbar
    assert reverse("verfahren:antrag", args=[12]) in inhalt


def test_neueste_zuerst_und_filter_nach_antrag_und_art(client):
    for nr in (1, 2, 3):
        AuditEintrag.anhaengen({"typ": "stimme", "antrag": nr, "pseudonym": f"pseudonym-nr-{nr}"})
    AuditEintrag.anhaengen({"art": "beitrag_gemeldet", "antrag": 2, "beitrag": 9, "grund": "thema"})
    inhalt = _seite(client)
    assert inhalt.index("pseudonym-nr-3") < inhalt.index("pseudonym-nr-1")
    nur_zwei = _seite(client, antrag="2")
    assert "pseudonym-nr-2" in nur_zwei and "pseudonym-nr-1" not in nur_zwei and "beitrag_gemeldet" in nur_zwei
    gemeldet = _seite(client, art="beitrag_gemeldet")  # ältere Art unter `art` wird gefunden
    assert "beitrag_gemeldet" in gemeldet and "pseudonym-nr-2" not in gemeldet
    assert "pseudonym-nr-1" in _seite(client, antrag="abc", art="<script>")  # Unlesbares wird übergangen


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
    assert "intakt, 1 Einträge" in inhalt
    kopf = AuditEintrag.objects.get().hash
    assert f'title="{kopf}"' in inhalt


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
    assert letzter["gekuerzt"] and letzter["ereignis"]["mitglied"] == "•" and letzter["ereignis"]["grund"] == "•"
    assert len(letzter["hash"]) == 64 and 4711 not in letzter["ereignis"].values()


def test_fusszeile_verlinkt_das_audit_log(client):
    assert reverse("verfahren:audit") in client.get(reverse("verfahren:index")).content.decode()


def test_englisch_ohne_deutsche_reste(client):
    AuditEintrag.anhaengen(AUSSCHLUSS)
    inhalt = client.get(reverse("verfahren:audit"), HTTP_ACCEPT_LANGUAGE="en").content.decode()
    assert "Audit log" in inhalt and "redacted" in inhalt and "gekürzt" not in inhalt
