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
import re

from django.db.models import Count
from django.utils.text import capfirst
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from plattform_core import Phase, vorschlagschat
from verfahren.chat import leicht, mit_zaehlern
from verfahren.models import AuditEintrag, Kommentar
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
        "zustimmungen": k.zustimmungen,
        "ablehnungen": k.ablehnungen,
    }


def _chat_je_phase(antrag, phasen: list[str] | None = None) -> dict[str, list[dict]]:
    """Beiträge nach der Phase geordnet, in der sie geschrieben wurden — nur für `phasen`
    (None = alle, für den Export). Die Seite lädt je Aufruf höchstens eine Phase (Befund #42);
    Zustimmungen kommen als Zähler mit, nicht als vorgeladene Reaktionen."""
    if phasen is not None and not phasen:
        return {}
    qs = antrag.kommentare.select_related("mitglied").order_by("erstellt_am", "pk")
    if phasen is not None:
        qs = qs.filter(phase__in=phasen)
    je_phase: dict[str, list[dict]] = {}
    for k in mit_zaehlern(qs):
        je_phase.setdefault(k.phase or "", []).append(_beitrag(k))
    return je_phase


def _anzahl_je_phase(antrag) -> dict[str, int]:
    """Wie viele Beiträge je Phase liegen — eine GROUP-BY-Abfrage statt aller Zeilen."""
    return {
        (phase or ""): n
        for phase, n in antrag.kommentare.order_by().values_list("phase").annotate(n=Count("id"))
    }


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


#: Die Ereignisse, mit denen eine Vorschlagsrunde endet — sie tragen die Rechnung im Wortlaut.
RUNDEN_EREIGNISSE = ("vorschlag_zurueckgegeben", "phasenwechsel")
_SCHWELLE = re.compile(r"Schwelle (\d+) %")


def _rundenereignisse(antrag) -> list[dict]:
    return [
        e.ereignis
        for e in AuditEintrag.objects.filter(
            ereignis__antrag=antrag.pk, ereignis__typ__in=list(RUNDEN_EREIGNISSE)
        ).order_by("lfd")
    ]


def schwelle_der_runde(antrag, runde: int, ereignisse: list[dict] | None = None) -> float | None:
    """Die Schwelle, mit der eine **abgeschlossene** Vorschlagsrunde entschieden wurde (Befund #22).

    Das Archiv rechnete jede alte Runde mit dem heutigen Registerwert nach — nach einer Änderung
    von `vorschlag-annahme-prozent` zeigte es ein anderes Ergebnis als die Audit-Spur derselben
    Seite. Die Entscheidung steht im Audit-Ereignis, das die Runde beendet hat: bevorzugt als
    strukturiertes Feld `auswertung` (sobald `Entwurf.fortschreiben` es schreibt), sonst im
    Wortlaut der Rechnung „(Schwelle NN %)“. None, wenn die Runde noch läuft oder nichts
    überliefert ist."""
    for e in ereignisse if ereignisse is not None else _rundenereignisse(antrag):
        grund = str(e.get("grund") or "")
        if e.get("typ") == "vorschlag_zurueckgegeben":
            # `zurueck_an_gruppe_1` zählt die Runde hoch, bevor es das Ereignis anhängt
            if e.get("runde") != runde + 1 or "Schwelle" not in grund:
                continue
        elif f"Runde {runde}," not in grund or "Schwelle" not in grund:
            continue
        auswertung = e.get("auswertung")
        if isinstance(auswertung, dict) and "schwelle" in auswertung:
            return float(auswertung["schwelle"])
        treffer = _SCHWELLE.search(grund)
        if treffer:
            return int(treffer.group(1)) / 100
    return None


def _auswertung(antrag, phase: str, ereignisse: list[dict] | None = None) -> dict | None:
    """Die Rechnung des Abstimmungs-Chats einer Vorschlagsrunde (FB-G6) — nachrechenbar.

    Rechnet über die Zahlen aller Beiträge der Runde (ohne Texte). Für die laufende Runde gilt
    der Registerwert; für abgeschlossene die Schwelle aus dem Audit-Ereignis der Entscheidung
    (`schwelle_quelle`: „audit“) — nur wenn nichts überliefert ist, das Register (Befund #22)."""
    if not phase.startswith("vorschlag-r"):
        return None
    from parameter.models import zahl
    from verfahren import chat as chatkern

    runde = int(phase.removeprefix("vorschlag-r"))
    roh = leicht(antrag.kommentare.filter(phase=phase))
    schwelle, quelle = None, "register"
    if chatkern.chat_phase(antrag) != phase:
        schwelle = schwelle_der_runde(antrag, runde, ereignisse)
        if schwelle is not None:
            quelle = "audit"
    if schwelle is None:
        schwelle = zahl("vorschlag-annahme-prozent", 50) / 100
    ergebnis = vorschlagschat.auswerten(roh, schwelle)
    ergebnis["kritik"] = [b["id"] for b in vorschlagschat.kritik_uebergeben(roh)]
    ergebnis["schwelle_quelle"] = quelle
    return ergebnis


def zeitleiste(antrag, geoeffnet: str | None = None, alles: bool = False) -> list[dict]:
    """Die Blöcke des Archivs von der Antragstellung bis heute (FB-G7).

    Jeder Block trägt Anzahl und Auswertung; seine Beiträge trägt er nur, wenn er `geoeffnet`
    ist (`?archiv=<phase>` — Link ohne JavaScript, hx-get mit) oder `alles` gilt (Export,
    Grundregel 7: der bleibt vollständig). Vorher lud jeder Aufruf der Antragsseite sämtliche
    Beiträge aller Phasen ein zweites Mal (Befund #42)."""
    anzahl = _anzahl_je_phase(antrag)
    je_phase = _chat_je_phase(antrag, None if alles else ([geoeffnet] if geoeffnet else []))
    reihenfolge = [
        Phase.UNTERSTUETZUNG.value,
        Phase.BERATUNG.value,
        *sorted((p for p in anzahl if p.startswith("vorschlag-r")), key=lambda p: int(p.removeprefix("vorschlag-r"))),
        Phase.ABSTIMMUNG.value,
        Phase.ANGENOMMEN.value,
        Phase.ABGELEHNT.value,
    ]
    ereignisse = _rundenereignisse(antrag) if any(p.startswith("vorschlag-r") for p in anzahl) else []
    bloecke = []
    for phase in reihenfolge:
        n = anzahl.get(phase, 0)
        if not n and phase not in (antrag.phase, Phase.UNTERSTUETZUNG.value):
            continue
        bloecke.append(
            {
                "phase": phase,
                "name": phasenname(phase),
                "laufend": phase == antrag.phase and phase not in ENDZUSTAENDE,
                "beitraege": je_phase.get(phase, []),
                "geladen": alles or phase == geoeffnet,
                "anzahl": n,
                "auswertung": _auswertung(antrag, phase, ereignisse),
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
    # Der Filter läuft in der Datenbank (Befund #41): Vorher zog jeder Antragsaufruf das gesamte
    # Audit-Log — jede Stimme, jede Unterstützung plattformweit — und siebte es in Python.
    spur = []
    for eintrag in AuditEintrag.objects.filter(ereignis__antrag=antrag.pk).order_by("lfd"):
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
            "unterstuetzungen": antrag.unterstuetzungen.filter(zurueckgezogen_am__isnull=True).count(),
        },
        "fassungen": fassungen,
        "zeitleiste": zeitleiste(antrag, alles=True),
        "entwurf": entwurf_bloecke(antrag),
        "audit": audit_spur(antrag),
    }


def als_json(antrag) -> str:
    from django.core.serializers.json import DjangoJSONEncoder

    # Übersetzbare Beschriftungen (gettext_lazy) sind Proxy-Objekte — der Standard-Encoder
    # kennt sie nicht, Djangos schreibt sie als Text.
    return json.dumps(archiv(antrag), ensure_ascii=False, indent=2, cls=DjangoJSONEncoder)


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
