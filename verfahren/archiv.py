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
from verfahren.models import Antragsart, AuditEintrag, Kommentar
from verfahren.templatetags.phasen import NAMEN as PHASEN_NAMEN

#: Phasen, nach denen nichts mehr läuft — ihr Block trägt kein „läuft".
ENDZUSTAENDE = (Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value)

#: Anzeigenamen der Phasen im Archiv. Sie kommen aus dem gemeinsamen Bestand
#: (`templatetags/phasen.py`), damit dieselbe Phase überall gleich heißt — und übersetzt wird.
PHASENNAMEN = {Phase.UNTERSTUETZUNG.value: gettext_lazy("Unterstützungsphase")}
#: Der Bestätigungsantrag (§ 7 Abs 10 lit f Z 3) sammelt keine Unterstützung — sein erster Block heißt so.
WARTEZEIT_NAME = gettext_lazy("Wartezeit bis zur Abstimmung")


def _ist_bestaetigung(antrag) -> bool:
    if antrag.art != Antragsart.VERTRAUENSFRAGE:
        return False
    vf = antrag._vertrauensfrage()
    return vf is not None and vf.art == "bestaetigung"


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


def _chat_je_phase(antrag, phasen: list[str] | None = None, stichzeiten: dict | None = None) -> dict[str, list[dict]]:
    """Beiträge nach der Phase geordnet, in der sie geschrieben wurden — nur für `phasen`
    (None = alle, für den Export). Die Seite lädt je Aufruf höchstens eine Phase (Befund #42);
    Zustimmungen kommen als Zähler mit, nicht als vorgeladene Reaktionen.

    `stichzeiten` (Phase → Zeitpunkt) zählt eine abgeschlossene Vorschlagsrunde zum Stand ihres
    Fristendes (§ 5 Abs 13, Prüfung 0.51.0): Eine später gespeicherte Zeile ändert nicht, was die
    Runde entschieden hat — weder die Zahlen noch die Reihung."""
    if phasen is not None and not phasen:
        return {}
    stichzeiten = {p: z for p, z in (stichzeiten or {}).items() if phasen is None or p in phasen}
    qs = antrag.kommentare.select_related("mitglied").order_by("erstellt_am", "pk")
    if phasen is not None:
        qs = qs.filter(phase__in=phasen)
    je_phase: dict[str, list[dict]] = {}
    if phasen is None or set(phasen) - set(stichzeiten):
        for k in mit_zaehlern(qs.exclude(phase__in=list(stichzeiten))):
            je_phase.setdefault(k.phase or "", []).append(_beitrag(k))
    for phase, stichzeit in stichzeiten.items():
        je_phase[phase] = [_beitrag(k) for k in mit_zaehlern(qs.filter(phase=phase), stichzeit=stichzeit)]
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


def _beendendes_ereignis(antrag, runde: int, ereignisse: list[dict] | None = None) -> dict | None:
    """Das Audit-Ereignis, das eine Vorschlagsrunde beendet hat — mit der Rechnung im Wortlaut und,
    seit 0.45, als Feld `auswertung`. None, wenn die Runde noch läuft oder nichts überliefert ist."""
    for e in ereignisse if ereignisse is not None else _rundenereignisse(antrag):
        grund = str(e.get("grund") or "")
        if e.get("typ") == "vorschlag_zurueckgegeben":
            # `zurueck_an_gruppe_1` zählt die Runde hoch, bevor es das Ereignis anhängt
            if e.get("runde") != runde + 1 or "Schwelle" not in grund:
                continue
        elif f"Runde {runde}," not in grund or "Schwelle" not in grund:
            continue
        return e
    return None


def _stichzeit(beendet: dict | None):
    """Das Fristende, zu dem eine abgeschlossene Runde gezählt wurde — `wirksam_ab` des Ereignisses,
    das sie beendet hat (seit 0.45 in beiden Ereignistypen). None ohne Ereignis oder ohne Feld."""
    from datetime import datetime

    wann = (beendet or {}).get("wirksam_ab")
    try:
        return datetime.fromisoformat(wann) if wann else None
    except (TypeError, ValueError):
        return None


def stichzeiten(antrag, phasen, ereignisse: list[dict] | None = None) -> dict:
    """Phase → Fristende je abgeschlossener Vorschlagsrunde unter `phasen` (für `_chat_je_phase`).
    Die laufende Runde und Runden ohne überliefertes Ende fehlen — sie zählen den heutigen Stand."""
    from verfahren import chat as chatkern

    runden = [p for p in phasen if p.startswith("vorschlag-r")]
    if not runden:
        return {}
    laufend = chatkern.chat_phase(antrag)
    ereignisse = _rundenereignisse(antrag) if ereignisse is None else ereignisse
    ergebnis = {}
    for phase in runden:
        if phase == laufend:
            continue
        zeit = _stichzeit(_beendendes_ereignis(antrag, int(phase.removeprefix("vorschlag-r")), ereignisse))
        if zeit is not None:
            ergebnis[phase] = zeit
    return ergebnis


def schwelle_der_runde(antrag, runde: int, ereignisse: list[dict] | None = None) -> float | None:
    """Die Schwelle, mit der eine **abgeschlossene** Vorschlagsrunde entschieden wurde (Befund #22).

    Das Archiv rechnete jede alte Runde mit dem heutigen Registerwert nach — nach einer Änderung
    von `vorschlag-annahme-prozent` zeigte es ein anderes Ergebnis als die Audit-Spur derselben
    Seite. Die Entscheidung steht im Audit-Ereignis, das die Runde beendet hat: bevorzugt als
    strukturiertes Feld `auswertung` (sobald `Entwurf.fortschreiben` es schreibt), sonst im
    Wortlaut der Rechnung „(Schwelle NN %)“. None, wenn die Runde noch läuft oder nichts
    überliefert ist."""
    e = _beendendes_ereignis(antrag, runde, ereignisse)
    if e is None:
        return None
    auswertung = e.get("auswertung")
    if isinstance(auswertung, dict) and "schwelle" in auswertung:
        return float(auswertung["schwelle"])
    treffer = _SCHWELLE.search(str(e.get("grund") or ""))
    return int(treffer.group(1)) / 100 if treffer else None


#: Was aus der festgehaltenen Rechnung einer abgeschlossenen Runde übernommen wird — die Zahlen, die
#: entschieden haben, nicht eine Nachrechnung mit dem heutigen Datenstand.
_FESTGEHALTEN = ("ja", "nein", "prozent", "oben", "angenommen", "reihung")


def _auswertung(antrag, phase: str, ereignisse: list[dict] | None = None) -> dict | None:
    """Die Rechnung des Abstimmungs-Chats einer Vorschlagsrunde (FB-G6) — nachrechenbar.

    Die laufende Runde rechnet über die geltenden Reaktionen mit der Schwelle der eingefrorenen
    Ordnung (`schwelle_quelle`: „ordnung“, bei einer Ordnung älter als das Feld „vorgabe“ — § 5
    Abs 5, Bestandsaufnahme A6). Eine abgeschlossene Runde zeigt, was entschieden hat: Schwelle und,
    wo festgehalten, die Zahlen aus dem Audit-Ereignis, das sie beendet hat („audit“, Befund #22).
    `weiter` sagt, wohin der Vorschlag ging — zur Endabstimmung auch dann, wenn die Höchstzahl der
    Runden erreicht war und „Passt alles“ nicht getragen hat (§ 5 Abs 12). Es kommt bei einer
    abgeschlossenen Runde nur aus dem Audit: Endete das Verfahren, bevor die Runde ausgewertet war
    (Zurückweisung, Rückzug), ist es None — „nicht ausgewertet“ (Prüfung 0.51.0). Gezählt wird eine
    abgeschlossene Runde zu ihrem Fristende (§ 5 Abs 13)."""
    if not phase.startswith("vorschlag-r"):
        return None
    from verfahren import chat as chatkern

    runde = int(phase.removeprefix("vorschlag-r"))
    laufend = chatkern.chat_phase(antrag) == phase
    beendet = None if laufend else _beendendes_ereignis(antrag, runde, ereignisse)
    roh = leicht(antrag.kommentare.filter(phase=phase), stichzeit=_stichzeit(beendet))
    schwelle, quelle = (schwelle_der_runde(antrag, runde, [beendet]) if beendet else None), "audit"
    if schwelle is None:
        schwelle, vorgabe = antrag.annahme_schwelle()
        quelle = "vorgabe" if vorgabe else "ordnung"
    ergebnis = vorschlagschat.auswerten(roh, schwelle)
    festgehalten = beendet.get("auswertung") if beendet else None
    if isinstance(festgehalten, dict):
        ergebnis.update({k: festgehalten[k] for k in _FESTGEHALTEN if k in festgehalten})
    if beendet:
        ergebnis["weiter"] = beendet.get("typ") == "phasenwechsel"
    else:
        ergebnis["weiter"] = ergebnis["angenommen"] if laufend else None
    ergebnis["kritik"] = [b["id"] for b in vorschlagschat.kritik_uebergeben(roh)]
    ergebnis["schwelle_quelle"] = quelle
    ergebnis["schwelle_prozent"] = round(schwelle * 100)
    return ergebnis


def zeitleiste(antrag, geoeffnet: str | None = None, alles: bool = False) -> list[dict]:
    """Die Blöcke des Archivs von der Antragstellung bis heute (FB-G7).

    Jeder Block trägt Anzahl und Auswertung; seine Beiträge trägt er nur, wenn er `geoeffnet`
    ist (`?archiv=<phase>` — Link ohne JavaScript, hx-get mit) oder `alles` gilt (Export,
    Grundregel 7: der bleibt vollständig). Vorher lud jeder Aufruf der Antragsseite sämtliche
    Beiträge aller Phasen ein zweites Mal (Befund #42)."""
    anzahl = _anzahl_je_phase(antrag)
    ereignisse = _rundenereignisse(antrag) if any(p.startswith("vorschlag-r") for p in anzahl) else []
    geladen = None if alles else ([geoeffnet] if geoeffnet else [])
    zeiten = stichzeiten(antrag, list(anzahl), ereignisse)
    je_phase = _chat_je_phase(antrag, geladen, zeiten)
    reihenfolge = [
        Phase.UNTERSTUETZUNG.value,
        Phase.BERATUNG.value,
        *sorted((p for p in anzahl if p.startswith("vorschlag-r")), key=lambda p: int(p.removeprefix("vorschlag-r"))),
        Phase.ABSTIMMUNG.value,
        Phase.ANGENOMMEN.value,
        Phase.ABGELEHNT.value,
    ]
    # Der Block „Unterstützungsphase“ steht auch leer — jeder Antrag beginnt dort. Nur die
    # Mandatsfrage (§ 7 Abs 9) und der Bestätigungsantrag (§ 7 Abs 10 lit f Z 3) nicht: Sie hatten
    # nie eine, also bekommen sie auch keinen leeren Block. Läuft der Bestätigungsantrag noch oder
    # wurde in seiner Wartezeit geschrieben, heißt der Block ehrlich „Wartezeit bis zur Abstimmung“.
    bestaetigung = _ist_bestaetigung(antrag)
    immer = () if antrag.art == Antragsart.MANDATSFRAGE or bestaetigung else (Phase.UNTERSTUETZUNG.value,)
    # Die Vertrauensfrage (§ 7 Abs 10 lit c) kennt keine Beratungsphase — an ihre Stelle treten die
    # Darstellung der Anlässe und das Gehör des Mandatsträgers auf der Antragsseite; kein Block.
    nie = (Phase.BERATUNG.value,) if antrag.art == Antragsart.VERTRAUENSFRAGE else ()
    bloecke = []
    for phase in reihenfolge:
        n = anzahl.get(phase, 0)
        if phase in nie or (not n and phase != antrag.phase and phase not in immer):
            continue
        bloecke.append(
            {
                "phase": phase,
                "name": (
                    str(WARTEZEIT_NAME)
                    if bestaetigung and phase == Phase.UNTERSTUETZUNG.value
                    else phasenname(phase)
                ),
                "laufend": phase == antrag.phase and phase not in ENDZUSTAENDE,
                "beitraege": je_phase.get(phase, []),
                "geladen": alles or phase == geoeffnet,
                "anzahl": n,
                "auswertung": _auswertung(antrag, phase, ereignisse),
                "stichzeit": zeiten.get(phase),  # gezählt zum Fristende der Runde (§ 5 Abs 13)
            }
        )
    return bloecke


def zustandekommen(antrag, bloecke: list[dict]) -> dict | None:
    """Der Block „So kam der Vorschlag zustande“ in der Endabstimmung (D-G5, FB-G5).

    Die Abstimmenden sollen die Kritik sehen: Die letzte Vorschlagsrunde erscheint eingefroren in
    Zone 3 — mit der Rechnung, die entschieden hat (`_auswertung`, bei abgeschlossenen Runden aus
    dem Audit), und den Beiträgen in der Reihung, die bei Fristende galt (Regel `engagement-v1`,
    § 5 Abs 13 letzter Satz), Antworten chronologisch unter ihrem Beitrag. Die Zahl der Beiträge
    ist gedeckelt wie der Faden (Registerwert „chat-faden-wurzeln“); der Rest liegt im Archiv.
    None außerhalb der Endabstimmung und ohne Entwurfsschleife — nach dem Ergebnis bleibt das
    Archiv (Entscheidung E2 zum Bauplan 0.51.0)."""
    if antrag.phase != Phase.ABSTIMMUNG.value:
        return None
    runden = [b for b in bloecke if b["phase"].startswith("vorschlag-r")]
    if not runden:
        return None
    from verfahren import chat as chatkern

    runde = runden[-1]
    beitraege = (
        runde["beitraege"]
        if runde["geladen"]
        else _chat_je_phase(antrag, [runde["phase"]], {runde["phase"]: runde["stichzeit"]} if runde.get("stichzeit") else None).get(
            runde["phase"], []
        )
    )
    wurzeln = vorschlagschat.reihen(
        [{**b, "ja": b["zustimmungen"], "nein": b["ablehnungen"], "zeit": b["geschrieben_am"]}
         for b in beitraege if not b["antwort_auf"]]
    )
    grenze = chatkern.faden_wurzeln()
    gezeigt = wurzeln[:grenze] if grenze else wurzeln
    antworten: dict[int, list[dict]] = {}
    for b in beitraege:
        if b["antwort_auf"]:
            antworten.setdefault(b["antwort_auf"], []).append(b)
    geordnet = []
    for w in gezeigt:
        geordnet.append(w)
        geordnet.extend(antworten.get(w["id"], []))
    return {
        "runde": runde,
        "beitraege": geordnet,
        "mehr": len(wurzeln) - len(gezeigt),
        "fruehere": runden[:-1],
    }


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
    # Mit `grenze` schneidet die Datenbank (0.51.0): Seit jede Reaktion im Abstimmungs-Chat einen
    # Eintrag schreibt (Bestandsaufnahme A8), wüchse die Spur eines umkämpften Antrags mit jedem Klick.
    from verfahren.audit_oeffentlich import mit_vorgaenger

    eintraege = mit_vorgaenger(AuditEintrag.objects.filter(ereignis__antrag=antrag.pk))
    if grenze:
        eintraege = reversed(list(eintraege.order_by("-lfd")[:grenze]))
    else:
        eintraege = eintraege.order_by("lfd")
    # Voller Hash, Vorgänger und Inhalt (Bestandsaufnahme A7, 0.52.0): Jeder ungeschwärzte Eintrag lässt sich
    # mit verify/nachrechnen.py einzeln nachrechnen; bis 0.51 trug der Export nur `hash[:12]`.
    from verfahren.audit_oeffentlich import eintrag_oeffentlich

    return [eintrag_oeffentlich(eintrag) for eintrag in eintraege]


def audit_anzahl(antrag) -> int:
    """Wie viele Audit-Ereignisse dieser Antrag hat — gezählt in der Datenbank."""
    return AuditEintrag.objects.filter(ereignis__antrag=antrag.pk).count()


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
    daten = {
        "antrag": {
            "id": antrag.pk,
            "titel": antrag.titel,
            "art": antrag.get_art_display(),
            "ebene": antrag.get_ebene_display(),
            "phase": antrag.phase,
            "phase_name": phasenname(antrag.phase),
            "eingebracht_am": antrag.eingebracht_am.isoformat(),
            "unterstuetzungen": antrag.unterstuetzungen.filter(zurueckgezogen_am__isnull=True, mitglied__testkonto=False).count(),
        },
        "fassungen": fassungen,
        "zeitleiste": zeitleiste(antrag, alles=True),
        "entwurf": entwurf_bloecke(antrag),
        "audit": audit_spur(antrag),
    }
    vf = _vertrauensfrage(antrag)
    if vf is not None:
        daten["vertrauensfrage"] = vf
    return daten


def _vertrauensfrage(antrag) -> dict | None:
    """Die Fachdaten einer Vertrauensfrage fürs Archiv (§ 7 Abs 10): Art, Mandat und Mandatar (Anzeigename
    wie auf der Antragsseite), die mit dem Antrag veröffentlichten Zahlen (lit c), das Erreichen der
    Schwelle, Sperrhinweis und Feststellung (lit b, g), das Ergebnis in Satzungsworten (lit e), der
    Rechtsschutz (lit h) und alle Stellungnahmen im Wortlaut (lit d — sie bleiben dauerhaft einsehbar).
    None für jede andere Antragsart."""
    vf = antrag._vertrauensfrage()
    if vf is None:
        return None
    vf.antrag = antrag
    return {
        "art": vf.get_art_display(),
        "mandat": vf.mandat.bezeichnung,
        "mandatar": vf.mandat.mitglied.anzeigename,
        "anlaesse": [
            {
                "gegenstand": r.gegenstand,
                "sitzung_am": r.sitzung_am.isoformat(),
                "beschluss_plattform": r.beschluss_anzeige,
                "stimme": r.get_stimme_display(),
                "begruendung": r.begruendung,
            }
            for r in vf.anlaesse.select_related("antrag").order_by("-sitzung_am", "-eingetragen_am")
        ],
        "ausstaende": list(vf.anlass_ausstaende),
        "stimmberechtigte_am_einbringungstag": vf.stimmberechtigte_partei_am_einbringungstag,
        "schwelle": vf.schwelle_partei,
        "schwelle_erreicht_am": vf.schwelle_erreicht_am.isoformat() if vf.schwelle_erreicht_am else None,
        "sperrhinweis": vf.sperrhinweis,
        "nicht_eroeffnet": vf.nicht_eroeffnet,
        "ergebnis": vf.ergebnis_wort,
        "rechtsschutz": vf.rechtsschutz_stand,
        "stellungnahmen": [
            {"text": st.text, "erstellt_am": st.erstellt_am.isoformat()} for st in vf.stellungnahmen.all()
        ],
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
    # Der Bestätigungsantrag (§ 7 Abs 10 lit f Z 3) kennt weder Unterstützung noch Anlässe noch die Zahlen
    # nach lit c — lit b, c und g gelten für ihn nicht; der Export sagt das statt „0 Unterstützungen · Schwelle: 0“.
    bestaetigung = _ist_bestaetigung(antrag)
    eingebracht = a["eingebracht_am"][:10]
    if antrag.art == Antragsart.MANDATSFRAGE:
        kopf = f"{_('Eröffnet')}: {eingebracht} · {_('ohne Unterstützungs- und Beratungsphase (§ 7 Abs 9)')}"
    elif bestaetigung:
        kopf = f"{_('Eingebracht')}: {eingebracht}"
    else:
        kopf = f"{_('Eingebracht')}: {eingebracht} · {a['unterstuetzungen']} {_('Unterstützungen')}"
    zeilen = [
        f"# {a['titel']}",
        "",
        f"Antrag {a['id']} · {a['art']} · {a['ebene']} · {_('Phase')}: {a['phase_name']}",
        kopf,
        "",
    ]
    vf = d.get("vertrauensfrage")
    if vf:
        # § 7 Abs 10: Wer betroffen ist, die Zahlen des Einbringungstags, keine Beratungsphase, das Ergebnis
        if bestaetigung:
            zahlen = str(_("ohne Unterstützungs- und Beratungsphase (§ 7 Abs 10 lit f Z 3)"))
        else:
            zahlen = (
                f"{_('Anlässe')}: {len(vf['anlaesse']) + len(vf['ausstaende'])} · "
                f"{_('Stimmberechtigte am Einbringungstag')}: {vf['stimmberechtigte_am_einbringungstag']} · "
                f"{_('Schwelle')}: {vf['schwelle']} · {_('ohne Beratungsphase (§ 7 Abs 10 lit c)')}"
            )
        zeilen += [
            f"{vf['art']} · {_('Mandatar')}: {vf['mandatar']} ({vf['mandat']}) · {zahlen}"
            + (f" · **{vf['ergebnis']}**" if vf["ergebnis"] else "")
            + (f" · {vf['rechtsschutz']}" if vf["rechtsschutz"] else ""),
            "",
        ]
        if vf["stellungnahmen"]:
            zeilen += [f"## {_('Stellungnahme des Mandatsträgers')}", ""]
            for st in vf["stellungnahmen"]:
                zeilen += [f"- ({st['erstellt_am'][:16].replace('T', ' ')})", f"  {st['text']}".replace("\n", "\n  "), ""]
    for f in d["fassungen"]:
        zeilen += [f"## {_('Fassung')} {f['nummer']} ({f['erstellt_am'][:10]})", "", f["wortlaut"], ""]
        if f["begruendung"]:
            zeilen += [f"*{f['begruendung']}*", ""]
    for block in d["zeitleiste"]:
        zeilen += [f"## {block['name']} — {block['anzahl']} {_('Beiträge')}", ""]
        auswertung = block["auswertung"]
        if auswertung:
            vorgabe = f" ({_('Vorgabe')})" if auswertung["schwelle_quelle"] == "vorgabe" else ""
            weiter = (
                _("nicht ausgewertet — das Verfahren endete vorher")
                if auswertung["weiter"] is None
                else _("zur Endabstimmung") if auswertung["weiter"] else _("zurück an den Expertenrat")
            )
            zeilen += [
                f"*{_('Auswertung')}: „Passt alles“ {auswertung['ja']}:{auswertung['nein']} "
                f"= {auswertung['prozent']} % · {_('Schwelle')} {auswertung['schwelle_prozent']} %{vorgabe} · "
                f"{_('an erster Stelle') if auswertung['oben'] else _('nicht an erster Stelle')} · "
                f"{weiter} "
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
        zeilen += [f"- {e['zeit'][:16].replace('T', ' ')} · {e['typ']} · `{e['hash'] or '•'}`" for e in d["audit"]]
        zeilen.append("")
    return "\n".join(zeilen)
