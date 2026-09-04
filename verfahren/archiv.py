"""Das Archiv eines Antrags (FB-G7; A0-07) — der ganze Weg, zum Nachlesen und Mitnehmen.

Der Gründer verlangt „die archivierten daten von allen chats von der Antragstellung bis hin zu
den vorschlägen des expertenrats und allen vorherigen Vorgängen übersichtlich zum reinklicken …
abrufbar und exportierbar". Diese Datei sammelt beides aus einer Quelle: die Zeitleiste für die
Anzeige und dieselben Daten als JSON und Markdown zum Mitnehmen.

Gezeigt werden ausschließlich Angaben, die ohnehin öffentlich sind — Anzeigenamen wie auf der
Antragsseite, keine E-Mails, keine Kennungen von Mitgliedern. Der Chat erscheint in der Ordnung
seiner Phasen: Was bei einer Hochstufung archiviert wurde (FB-G5), steht hier unter der Phase,
in der es geschrieben wurde. Gelöscht wird nichts; entfernte Beiträge tragen ihren Vermerk
(§ 5 Abs 3 lit e, Grundregel 7).
"""

from __future__ import annotations

import json

from django.utils.text import capfirst
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from plattform_core import Phase, vorschlagschat
from verfahren.models import AuditEintrag, Kommentar, Reaktionsart
from verfahren.templatetags.phasen import NAMEN as PHASEN_NAMEN

#: Phasen, nach denen nichts mehr läuft — ihr Block trägt kein „läuft".
ENDZUSTAENDE = (Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value)

#: Anzeigenamen der Phasen im Archiv. Sie kommen aus dem gemeinsamen Bestand
#: (`templatetags/phasen.py`), damit dieselbe Phase überall gleich heißt — und übersetzt wird.
PHASENNAMEN = {Phase.UNTERSTUETZUNG.value: gettext_lazy("Unterstützungsphase")}


def phasenname(schluessel: str) -> str:
    if schluessel.startswith("vorschlag-r"):
        return _("Vorschlagsberatung — Runde %s") % schluessel.removeprefix("vorschlag-r")
    if schluessel in PHASENNAMEN:
        return str(PHASENNAMEN[schluessel])
    if schluessel in PHASEN_NAMEN:
        return capfirst(str(PHASEN_NAMEN[schluessel]))
    return schluessel or _("ohne Phase")


def _beitrag(k: Kommentar) -> dict:
    return {
        "id": k.pk,
        "verfasser": k.mitglied.anzeigename if k.mitglied_id else _("Die Plattform"),
        "system": k.system,
        "antwort_auf": k.antwort_auf_id,
        "text": k.sichtbarer_text(),
        "geschrieben_am": k.erstellt_am.isoformat(),
        "bearbeitet": bool(k.bearbeitet_am),
        "archiviert_am": k.archiviert_am.isoformat() if k.archiviert_am else None,
        "ist_kritik": k.ist_kritik,
        "bezug_absatz": k.bezug_absatz,
        "zustimmungen": sum(1 for r in k.reaktionen.all() if r.art == Reaktionsart.ZUSTIMMUNG),
        "ablehnungen": sum(1 for r in k.reaktionen.all() if r.art == Reaktionsart.ABLEHNUNG),
    }


def _chat_je_phase(antrag) -> dict[str, list[dict]]:
    """Alle Beiträge, nach der Phase geordnet, in der sie geschrieben wurden."""
    je_phase: dict[str, list[dict]] = {}
    for k in (
        antrag.kommentare.select_related("mitglied").prefetch_related("reaktionen").order_by("erstellt_am")
    ):
        je_phase.setdefault(k.phase or "", []).append(_beitrag(k))
    return je_phase


def entwurf_bloecke(antrag) -> list[dict]:
    """Der Weg durch die Werkstatt: Fassungen, Prüfungen und die Auswertung je Runde."""
    entwurf = getattr(antrag, "entwurf", None)
    if entwurf is None:
        return []
    fassungen = [
        {
            "nummer": f.nummer,
            "wortlaut": f.wortlaut,
            "begruendung": f.begruendung,
            "verfasst_von": f.verfasst_von.anzeigename,
            "erstellt_am": f.erstellt_am.isoformat(),
        }
        for f in entwurf.fassungen.select_related("verfasst_von").order_by("nummer")
    ]
    pruefungen = [
        {
            "runde": p.runde,
            "ergebnis": p.get_ergebnis_display(),
            "begruendung": p.begruendung,
            "korat_entscheid": p.korat_entscheid,
            "erstellt_am": p.erstellt_am.isoformat(),
        }
        for p in entwurf.pruefungen.order_by("erstellt_am")
    ]
    return [
        {
            "runde": entwurf.runde,
            "status": entwurf.get_status_display(),
            "vollzugsbezug": entwurf.vollzugsbezug,
            "fassungen": fassungen,
            "pruefungen": pruefungen,
        }
    ]


def _auswertung(antrag, phase: str, beitraege: list[dict]) -> dict | None:
    """Die Rechnung des Abstimmungs-Chats einer Vorschlagsrunde (FB-G6) — nachrechenbar."""
    if not phase.startswith("vorschlag-r"):
        return None
    roh = [
        {"id": b["id"], "ja": b["zustimmungen"], "nein": b["ablehnungen"],
         "zeit": b["geschrieben_am"], "system": b["system"], "ist_kritik": b["ist_kritik"]}
        for b in beitraege
    ]
    from parameter.models import zahl

    ergebnis = vorschlagschat.auswerten(roh, zahl("vorschlag-annahme-prozent", 50) / 100)
    ergebnis["kritik"] = [b["id"] for b in vorschlagschat.kritik_uebergeben(roh)]
    return ergebnis


def zeitleiste(antrag) -> list[dict]:
    """Die Blöcke des Archivs von der Antragstellung bis heute (FB-G7)."""
    je_phase = _chat_je_phase(antrag)
    reihenfolge = [
        Phase.UNTERSTUETZUNG.value,
        Phase.BERATUNG.value,
        *sorted((p for p in je_phase if p.startswith("vorschlag-r")), key=lambda p: int(p.removeprefix("vorschlag-r"))),
        Phase.ABSTIMMUNG.value,
        Phase.ANGENOMMEN.value,
        Phase.ABGELEHNT.value,
    ]
    bloecke = []
    for phase in reihenfolge:
        beitraege = je_phase.get(phase, [])
        if not beitraege and phase not in (antrag.phase, Phase.UNTERSTUETZUNG.value):
            continue
        bloecke.append(
            {
                "phase": phase,
                "name": phasenname(phase),
                "laufend": phase == antrag.phase and phase not in ENDZUSTAENDE,
                "beitraege": beitraege,
                "anzahl": len(beitraege),
                "auswertung": _auswertung(antrag, phase, beitraege),
            }
        )
    return bloecke


#: Rückfallwert; der gültige steht im Register unter „archiv-audit-anzeige" (FB-J2).
AUDIT_ANZEIGE = 60


def audit_anzeige() -> int:
    """Wie viele Ereignisse die Zeitleiste zeigt — der Export bekommt immer alle."""
    from parameter.models import zahl

    return zahl("archiv-audit-anzeige", AUDIT_ANZEIGE)


def audit_spur(antrag, grenze: int | None = None) -> list[dict]:
    """Die Audit-Ereignisse dieses Antrags mit Hash-Kurzform (F-22).

    Ohne `grenze` kommt die **vollständige** Spur — so muss es für den Export sein (FB-G7,
    Grundregel 7). Die Seite reicht `AUDIT_ANZEIGE` herein, weil eine Zeitleiste mit
    zweihundert Zeilen niemandem hilft; dass gekürzt wurde, sagt sie dann auch dazu."""
    spur = []
    for eintrag in AuditEintrag.objects.order_by("lfd"):
        if eintrag.ereignis.get("antrag") != antrag.pk:
            continue
        spur.append(
            {
                "lfd": eintrag.lfd,
                "typ": eintrag.ereignis.get("typ", ""),
                "zeit": eintrag.zeit.isoformat(),
                "hash": eintrag.hash[:12],
                "grund": eintrag.ereignis.get("grund", ""),
            }
        )
    return spur[-grenze:] if grenze else spur


def archiv(antrag) -> dict:
    """Das ganze Archiv eines Antrags als schlichte Abbildung — Grundlage für Anzeige und Export."""
    fassungen = [
        {
            "nummer": f.nummer,
            "wortlaut": f.wortlaut,
            "begruendung": f.begruendung,
            "erstellt_am": f.erstellt_am.isoformat(),
        }
        for f in antrag.fassungen.order_by("nummer")
    ]
    return {
        "antrag": {
            "id": antrag.pk,
            "titel": antrag.titel,
            "art": antrag.get_art_display(),
            "ebene": antrag.get_ebene_display(),
            "phase": antrag.phase,
            "phase_name": phasenname(antrag.phase),
            "eingebracht_am": antrag.eingebracht_am.isoformat(),
            "unterstuetzungen": antrag.unterstuetzungen.count(),
        },
        "fassungen": fassungen,
        "zeitleiste": zeitleiste(antrag),
        "entwurf": entwurf_bloecke(antrag),
        "audit": audit_spur(antrag),
    }


def als_json(antrag) -> str:
    return json.dumps(archiv(antrag), ensure_ascii=False, indent=2)


def als_markdown(antrag) -> str:
    """Dieselbe Gliederung, lesbar — zum Ablegen, Ausdrucken, Zitieren."""
    d = archiv(antrag)
    a = d["antrag"]
    zeilen = [
        f"# {a['titel']}",
        "",
        f"Antrag {a['id']} · {a['art']} · {a['ebene']} · {_('Phase')}: {a['phase_name']}",
        f"{_('Eingebracht')}: {a['eingebracht_am'][:10]} · {a['unterstuetzungen']} {_('Unterstützungen')}",
        "",
    ]
    for f in d["fassungen"]:
        zeilen += [f"## {_('Fassung')} {f['nummer']} ({f['erstellt_am'][:10]})", "", f["wortlaut"], ""]
        if f["begruendung"]:
            zeilen += [f"*{f['begruendung']}*", ""]
    for block in d["zeitleiste"]:
        zeilen += [f"## {block['name']} — {block['anzahl']} {_('Beiträge')}", ""]
        auswertung = block["auswertung"]
        if auswertung:
            zeilen += [
                f"*{_('Auswertung')}: „Passt alles“ {auswertung['ja']}:{auswertung['nein']} "
                f"= {auswertung['prozent']} % · "
                f"{_('an erster Stelle') if auswertung['oben'] else _('nicht an erster Stelle')} · "
                f"{_('angenommen') if auswertung['angenommen'] else _('zurückgegeben')} "
                f"({auswertung['grund']}, {auswertung['reihung']})*",
                "",
            ]
        for b in block["beitraege"]:
            kopf = f"- **{b['verfasser']}** ({b['geschrieben_am'][:16].replace('T', ' ')})"
            if b["ist_kritik"]:
                kopf += f" · {_('Kritik')}" + (f" {_('Absatz')} {b['bezug_absatz']}" if b["bezug_absatz"] else "")
            if b["antwort_auf"]:
                kopf += f" · {_('Antwort auf')} #{b['antwort_auf']}"
            if b["zustimmungen"] or b["ablehnungen"]:
                kopf += f" · 👍 {b['zustimmungen']} / 👎 {b['ablehnungen']}"
            zeilen += [kopf, f"  {b['text']}".replace("\n", "\n  "), ""]
    for e in d["entwurf"]:
        zeilen += [f"## {_('Expertenrat')} — {_('Runde')} {e['runde']} ({e['status']})", ""]
        for f in e["fassungen"]:
            zeilen += [f"### {_('Entwurfsfassung')} {f['nummer']} · {f['verfasst_von']}", "", f["wortlaut"], ""]
        for p in e["pruefungen"]:
            zeilen += [f"- {_('Prüfung')} ({p['ergebnis']}): {p['begruendung']}", ""]
    if d["audit"]:
        zeilen += [f"## {_('Audit-Spur')}", ""]
        zeilen += [f"- {e['zeit'][:16].replace('T', ' ')} · {e['typ']} · `{e['hash']}`" for e in d["audit"]]
        zeilen.append("")
    return "\n".join(zeilen)
