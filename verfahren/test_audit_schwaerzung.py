"""Die Schwärzung lässt sich nicht zurückrechnen (gegnerische Prüfung 0.52.0).

Mitgliedsnummern und Pseudonyme haben kleine Wertebereiche. Stünden Hash und Vorgänger eines geschwärzten
Eintrags offen, fände ein Gast den geschwärzten Wert durch Durchprobieren. Deshalb: Neue Einträge mit
schutzwürdigen Werten tragen ein geheimes Salz (selbst geschwärzt); ältere ohne Salz zeigen weder ihren
Hash noch den Vorgänger-Hash ihres Nachfolgers."""

import pytest
from django.urls import reverse

from plattform_core.hashchain import ereignis_hash
from verfahren.audit_oeffentlich import MASKE, SALZ
from verfahren.models import AuditEintrag

pytestmark = pytest.mark.django_db


def _durchprobieren(eintrag: dict, schluessel: str, kandidaten) -> object | None:
    """Was ein Gast täte: jeden Kandidaten einsetzen und gegen den veröffentlichten Hash rechnen."""
    if not eintrag.get("hash") or not eintrag.get("vorgaenger"):
        return None
    for kandidat in kandidaten:
        versuch = {**eintrag["ereignis"], schluessel: kandidat}
        versuch = {k: v for k, v in versuch.items() if v != MASKE}  # ein geschwärztes Salz kennt er nicht
        if ereignis_hash(eintrag["vorgaenger"], versuch) == eintrag["hash"]:
            return kandidat
    return None


def _oeffentlich(client):
    return {e["lfd"]: e for e in client.get(reverse("verfahren:audit_json")).json()["eintraege"]}


def test_ein_neuer_eintrag_mit_mitgliedsnummer_traegt_ein_salz_und_bleibt_geschwaerzt(client):
    AuditEintrag.anhaengen({"typ": "verwaltung", "aktion": "beitrag", "mitglied": 4711})
    gespeichert = AuditEintrag.objects.get()
    assert len(gespeichert.ereignis[SALZ]) == 32  # 128 Bit
    oeffentlich = _oeffentlich(client)[gespeichert.lfd]
    assert oeffentlich["ereignis"][SALZ] == MASKE and oeffentlich["ereignis"]["mitglied"] == MASKE
    assert oeffentlich["hash"] == gespeichert.hash  # darf offen stehen: ohne Salz nicht nachzurechnen
    assert _durchprobieren(oeffentlich, "mitglied", range(1, 10_000)) is None


def test_ein_eintrag_ohne_schutzwuerdige_werte_bekommt_kein_salz():
    AuditEintrag.anhaengen({"typ": "phasenwechsel", "antrag": 3, "neue_phase": "beratung"})
    assert SALZ not in AuditEintrag.objects.get().ereignis


def test_eine_stimme_traegt_ein_salz():
    AuditEintrag.anhaengen({"typ": "stimme", "antrag": 1, "pseudonym": "ab" * 16})
    assert SALZ in AuditEintrag.objects.get().ereignis


def _alter_eintrag(ereignis):
    """Wie ein Eintrag aus der Zeit vor 0.52.0 — ohne Salz, am selben Kopf wie jeder andere."""
    from django.utils import timezone

    from plattform_core.hashchain import GENESIS

    letzter = AuditEintrag.objects.order_by("-lfd").first()
    vorgaenger = letzter.hash if letzter else GENESIS
    versiegelt = {**ereignis, "zeit": timezone.now().isoformat()}
    return AuditEintrag.objects.create(
        zeit=timezone.now(), ereignis=versiegelt, vorgaenger=vorgaenger, hash=ereignis_hash(vorgaenger, versiegelt)
    )


def test_ein_alter_geschwaerzter_eintrag_zeigt_weder_hash_noch_den_vorgaenger_des_nachfolgers(client):
    davor = _alter_eintrag({"typ": "phasenwechsel", "antrag": 1})
    alt = _alter_eintrag({"typ": "verwaltung", "aktion": "beitrag", "mitglied": 17})
    danach = _alter_eintrag({"typ": "phasenwechsel", "antrag": 2})
    oeffentlich = _oeffentlich(client)
    assert oeffentlich[alt.lfd]["hash"] is None and oeffentlich[alt.lfd]["vorgaenger"] == davor.hash
    assert oeffentlich[danach.lfd]["vorgaenger"] is None and oeffentlich[danach.lfd]["hash"] == danach.hash
    assert _durchprobieren(oeffentlich[alt.lfd], "mitglied", range(1, 100)) is None
    # der ungeschwärzte Eintrag davor bleibt einzeln nachrechenbar
    assert oeffentlich[davor.lfd]["hash"] == davor.hash


def test_der_kopf_eines_alten_geschwaerzten_eintrags_wird_nicht_veroeffentlicht(client):
    from verfahren.audit_pruefung import LAUF
    from verfahren.hintergrund import LAEUFE, ausfuehren

    _alter_eintrag({"typ": "stimme", "antrag": 1, "pseudonym": "cd" * 16})
    ausfuehren(next(la for la in LAEUFE if la.name == LAUF))
    werte = {k["schema_key"]: k["wert"] for k in client.get("/kennzahlen.json").json()["kennzahlen"]}
    assert werte["audit.chain_intact"] == 1 and werte["audit.head"] is None
    seite = client.get(reverse("verfahren:audit")).content.decode()
    assert AuditEintrag.objects.get().hash not in seite


def test_der_gemeldete_beitrag_bleibt_bis_zur_entscheidung_verborgen():
    from verfahren.audit_oeffentlich import ereignis_oeffentlich

    sichtbar, geschwaerzt = ereignis_oeffentlich({"typ": "beitrag_gemeldet", "antrag": 1, "beitrag": 9, "grund": "recht"})
    assert sichtbar["beitrag"] == MASKE and geschwaerzt and sichtbar["grund"] == "recht"


def test_eine_anzahl_unter_konten_ist_keine_kennung():
    from verfahren.audit_oeffentlich import ereignis_oeffentlich

    assert ereignis_oeffentlich({"typ": "post_einwilligung_bestand", "konten": 12}) == (
        {"typ": "post_einwilligung_bestand", "konten": 12}, False
    )
