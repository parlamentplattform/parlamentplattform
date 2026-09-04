"""Parameterregister-Ansichten (F-68): öffentliche Liste, JSON-Export,
Verwaltung mit Pflicht-Grund — jede Änderung im Audit-Log."""

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from mitglieder.verwaltung import nur_admins
from parameter.models import Aenderung, Gruppe, Parameter, Status, erstbestand_sicherstellen
from verfahren.models import AuditEintrag

#: Kennung der Verfahrensordnung, wenn diese Instanz noch gar keine hat. Gibt es eine geltende
#: Fassung, wird deren Kennung weitergeführt — das Einbringen sucht die aktive Ordnung ohne
#: Rücksicht auf ihren Namen (verfahren/views_aktionen.py), und zwei Reihen nebeneinander wären
#: eine Ordnung, die niemand in Kraft setzen kann.
POLICY_ID = "sachantrag-standard"


def liste(request):
    from plattform_core.weicherfilter import REGLER
    from verfahren.views import REGLER_MERKMALE, REGLER_NAMEN

    erstbestand_sicherstellen()
    return render(
        request,
        "parameter/liste.html",
        {
            "karten": _karten(_register_eintraege()),
            "im_test": Status.IM_TEST,
            "ordnung": _aktive_ordnung(),
            # FB-B6: die offene Regel v2 des WeicherFilters, Regler für Regler nachlesbar
            "weicherfilter_regler": [
                (i + 1, REGLER_NAMEN[name], REGLER_MERKMALE[name]) for i, name in enumerate(REGLER)
            ],
        },
    )


def _offen(daten) -> JsonResponse:
    antwort = JsonResponse(daten, json_dumps_params={"ensure_ascii": False, "indent": 1})
    antwort["Access-Control-Allow-Origin"] = "*"
    return antwort


def export_json(request):
    """FB-M5 (§ 12 Abs 5): Stellgrößen und Verfahrensordnung im sprachneutralen Schema
    (docs/SCHEMA.md, ADR-009) — der Austausch zwischen den Landesinstanzen. Die bisherigen
    Felder bleiben, dazu kommen Kopf und Schema-Kennungen."""
    from django.conf import settings

    from plattform_core import __version__
    from plattform_core.schema import parameter_export
    from verfahren.models import Verfahrensordnung

    erstbestand_sicherstellen()
    parameter = [
        {
            "schluessel": p.schluessel,
            "schema_key": p.schema_key,
            "wert": p.wert,
            "einheit": p.einheit,
            "beschreibung": p.beschreibung,
            "quelle": p.quelle,
            "geaendert_am": p.geaendert_am.isoformat(),
        }
        for p in Parameter.objects.all()
    ]
    ordnungen = [
        {**(vo.regeln or {}), "id": vo.policy_id, "version": vo.version}
        for vo in Verfahrensordnung.objects.filter(aktiv=True).order_by("policy_id")
    ]
    return _offen(
        parameter_export(
            settings.DDOE_SYSTEM_ID, settings.DDOE_SYSTEM_NAME, __version__, parameter, ordnungen, timezone.now()
        )
    )


def kennzahlen_json(request):
    """FB-M5: der aggregierte Lernfortschritt dieser Instanz — Zählungen und Anteile über das
    Ganze, nie über einen Menschen (Art 9 DSGVO). Kennungen nach docs/SCHEMA.md."""
    from django.conf import settings
    from django.db.models import Count

    from mitglieder.models import Mitglied
    from plattform_core import Phase, __version__
    from plattform_core.schema import kennzahlen_export, turnout_mean
    from verfahren.models import Antrag, Kategorie, Vollzugsstatus
    from verfahren.views import _register_zeilen

    antraege = Antrag.objects.exclude(phase=Phase.ZURUECKGEWIESEN.value)
    je_phase = dict.fromkeys(("unterstuetzung", "beratung", "abstimmung", "angenommen", "abgelehnt", "verfallen"), 0)
    for zeile in antraege.values("phase").annotate(n=Count("pk")):
        if zeile["phase"] in je_phase:
            je_phase[zeile["phase"]] = zeile["n"]
    entschieden = antraege.filter(
        phase__in=[Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value], stimmberechtigte_anzahl__gt=0
    )
    anteile = [a.stimmabgaben.count() / a.stimmberechtigte_anzahl for a in entschieden]
    register = _register_zeilen()
    je_status = {wert: sum(1 for z in register if z["status"] == wert) for wert, _name in Vollzugsstatus.choices}
    werte = {
        "members.active": Mitglied.objects.filter(is_active=True).count(),
        "motions.total": antraege.count(),
        "motions.by_phase": je_phase,
        "votes.completed": entschieden.count(),
        "votes.turnout_mean": turnout_mean(anteile),
        "implementation.by_status": je_status,
        "areas_of_life.active": Kategorie.objects.filter(aktiv=True).count(),
    }
    return _offen(
        kennzahlen_export(settings.DDOE_SYSTEM_ID, settings.DDOE_SYSTEM_NAME, __version__, werte, timezone.now())
    )


def _speist_die_ordnung() -> set[str]:
    """Registerschlüssel, aus denen die Verfahrensordnung gebaut wird (FB-J1)."""
    from plattform_core.policy import REGISTER_ZUORDNUNG

    return {schluessel for schluessel, _wandler in REGISTER_ZUORDNUNG.values()}


def _karten(eintraege) -> list[dict]:
    """Ordnet die Stellgrößen zu Gruppenkarten (FB-J2).

    Zweiunddreißig Zeilen in einer Liste sind vollständig und trotzdem unbrauchbar: Niemand
    findet darin die eine Frist, die ihn angeht. Die Reihenfolge der Karten ist die von
    `Gruppe`; leere Gruppen erscheinen nicht."""
    ordnungsschluessel = _speist_die_ordnung()
    nach_gruppe: dict[str, list] = {}
    for eintrag in eintraege:
        eintrag.speist_ordnung = eintrag.schluessel in ordnungsschluessel
        nach_gruppe.setdefault(eintrag.gruppe, []).append(eintrag)
    return [
        {"schluessel": wert, "name": name, "eintraege": nach_gruppe[wert]}
        for wert, name in Gruppe.choices
        if wert in nach_gruppe
    ]


def _register_eintraege():
    """Alle Stellgrößen mit ihrer Historie — ein Zugriff statt einer je Zeile."""
    return Parameter.objects.prefetch_related("historie").all()


def _register_werte() -> dict[str, int]:
    """Die ganzzahligen Registerwerte, die eine Verfahrensordnung speisen können.

    Ein unlesbarer Wert wird ausgelassen statt geraten — `aus_register` meldet ihn dann als
    fehlend, und die Verwaltung sieht, welcher Eintrag im Weg steht."""
    werte = {}
    for eintrag in Parameter.objects.filter(schluessel__in=_speist_die_ordnung()):
        try:
            werte[eintrag.schluessel] = int(eintrag.wert)
        except (TypeError, ValueError):
            continue
    return werte


def _aktive_ordnung():
    """Die Fassung, die beim Einbringen an einen Antrag geheftet wird — genau dieselbe
    Abfrage wie in `verfahren.views_aktionen.einbringen`."""
    from verfahren.models import Verfahrensordnung

    return Verfahrensordnung.objects.filter(aktiv=True).order_by("-version").first()


def _policy_id(aktiv) -> str:
    return aktiv.policy_id if aktiv is not None else POLICY_ID


def _mehrheitsbasis(aktiv) -> str:
    """Die Mehrheitsbasis beschließt die Mitgliederversammlung, nicht das Register.

    Sie steht deshalb in keiner Stellgröße und wird aus der geltenden Fassung übernommen —
    ein Knopf in der Verwaltung darf sie nicht nebenbei umstellen."""
    return (aktiv.regeln or {}).get("mehrheitsbasis", "ja_nein") if aktiv else "ja_nein"


def _naechste_version(policy_id: str) -> int:
    from django.db.models import Max

    from verfahren.models import Verfahrensordnung

    hoechste = Verfahrensordnung.objects.filter(policy_id=policy_id).aggregate(Max("version"))
    return (hoechste["version__max"] or 0) + 1


def _wesentlich(regeln: dict) -> dict:
    """Eine Ordnung ohne Kennung und Versionsnummer — zum Vergleichen des Inhalts."""
    return {k: v for k, v in (regeln or {}).items() if k not in ("id", "version")}


def _gleich(links, rechts) -> bool:
    """Vergleicht zwei Ordnungswerte. Bei Anteilen genügt Gleichheit auf sechs Stellen —
    0.05 aus dem gespeicherten JSON und 5/100 aus dem Register sind derselbe Wert."""
    if isinstance(links, float) or isinstance(rechts, float):
        return round(float(links), 6) == round(float(rechts), 6)
    return links == rechts


#: Deutsche Namen der Felder einer Verfahrensordnung. Die Feldnamen im Code sagen einem
#: Menschen wenig, und der Registerschlüssel daneben sagt etwas anderes als der Wert: Bei der
#: Mindestbeteiligung führt das Register 5 (Prozent), die Ordnung 0,05 (Anteil).
FELD_NAMEN = {
    "unterstuetzung_schwelle": "Unterstützungen bis zur Schwelle",
    "unterstuetzung_frist_tage": "Frist der Unterstützungsphase (Tage)",
    "beratung_tage": "Dauer der Beratung (Tage)",
    "abstimmung_tage": "Dauer der Abstimmung (Tage)",
    "mindestbeteiligung": "Mindestbeteiligung (Anteil)",
    "wiedereinbringung_sperre_monate": "Sperre für Wiedereinbringung (Monate)",
}


def _lesbare_ordnung(regeln: dict) -> list[dict]:
    """Eine Verfahrensordnung in Sätzen statt als roher Datensatz.

    Wer entscheiden soll, ob eine Fassung in Kraft treten darf, muss sie lesen können; ein
    hingeschriebenes Python-Wörterbuch ist keine Entscheidungsgrundlage."""
    zeilen = [
        {"name": name, "wert": regeln[feld]} for feld, name in FELD_NAMEN.items() if feld in regeln
    ]
    if "mehrheitsbasis" in regeln:
        zeilen.append(
            {
                "name": "Mehrheitsbasis",
                "wert": "Ja über Nein"
                if regeln["mehrheitsbasis"] == "ja_nein"
                else "Ja über die Hälfte aller abgegebenen Stimmen",
            }
        )
    return zeilen


def _ordnung_abgleich() -> dict:
    """Was das Register sagt und was gilt — Feld für Feld (FB-J1).

    Die Verfahrensordnung folgt dem Register absichtlich nicht von selbst: Sie wird beim
    Einbringen als Kopie an den Antrag geheftet (§ 5 Abs 5), und wer sie ändert, ändert die
    Regeln künftiger Verfahren. Dieser Abgleich macht den Abstand sichtbar, statt ihn zu
    verschweigen — eine Verwaltung, die im Register etwas ändert und glaubt, es gelte
    sofort, wäre schlimmer dran als eine, die gar nichts ändert."""
    from plattform_core.policy import REGISTER_ZUORDNUNG, PolicyFehler, aus_register
    from verfahren.models import Verfahrensordnung

    aktiv = _aktive_ordnung()
    kennung = _policy_id(aktiv)
    zeilen: list[dict] = []
    fehler = None
    try:
        erzeugt = aus_register(
            _register_werte(),
            kennung,
            _naechste_version(kennung),
            mehrheitsbasis=_mehrheitsbasis(aktiv),
        )
    except PolicyFehler as ausnahme:
        erzeugt = None
        fehler = str(ausnahme)
    if erzeugt is not None:
        gilt = aktiv.regeln if aktiv else {}
        for feld, (schluessel, _wandler) in REGISTER_ZUORDNUNG.items():
            aus_dem_register = getattr(erzeugt, feld)
            in_kraft = gilt.get(feld)
            zeilen.append(
                {
                    "feld": feld,
                    "name": FELD_NAMEN.get(feld, feld),
                    "schluessel": schluessel,
                    "register": aus_dem_register,
                    "in_kraft": in_kraft,
                    "abweichung": in_kraft is not None and not _gleich(in_kraft, aus_dem_register),
                }
            )
    return {
        "aktiv": aktiv,
        "fehler": fehler,
        "zeilen": zeilen,
        "abweichungen": sum(1 for z in zeilen if z["abweichung"]),
        "beschlussreif": [
            {"fassung": fassung, "zeilen": _lesbare_ordnung(fassung.regeln)}
            for fassung in Verfahrensordnung.objects.filter(policy_id=kennung, aktiv=False)
            .filter(version__gt=aktiv.version if aktiv else 0)
            .order_by("-version")
        ],
    }

@nur_admins
def verwaltung(request):
    erstbestand_sicherstellen()
    return render(
        request,
        "parameter/verwaltung.html",
        {
            "karten": _karten(_register_eintraege()),
            "abgleich": _ordnung_abgleich(),
            "im_test": Status.IM_TEST,
        },
    )


@nur_admins
@require_POST
def verwaltung_aktion(request):
    eintrag = get_object_or_404(Parameter, pk=request.POST.get("parameter"))
    neuer_wert = (request.POST.get("wert") or "").strip()[:100]
    grund = (request.POST.get("grund") or "").strip()
    if not neuer_wert or not grund:
        messages.error(request, "Neuer Wert und Grund sind Pflicht — der Grund wird veröffentlicht.")
        return redirect("parameter:verwaltung")
    if neuer_wert == eintrag.wert:
        messages.info(request, "Der Wert ist unverändert — nichts zu tun.")
        return redirect("parameter:verwaltung")
    alt = eintrag.wert
    eintrag.wert = neuer_wert
    eintrag.geaendert_am = timezone.now()
    eintrag.save(update_fields=["wert", "geaendert_am"])
    # Die Historie steht am Parameter selbst — im Audit-Log ist sie fälschungssicher, aber
    # niemand findet sie dort (FB-J2). Beides wird geschrieben, gelöscht wird keines.
    Aenderung.objects.create(
        parameter=eintrag,
        alter_wert=alt,
        neuer_wert=neuer_wert,
        grund=grund[:1000],
        geaendert_am=eintrag.geaendert_am,
        durch="Verwaltung",
    )
    AuditEintrag.anhaengen(
        {
            "typ": "parameter_geaendert",
            "schluessel": eintrag.schluessel,
            "alt": alt,
            "neu": neuer_wert,
            "grund": grund[:500],
        }
    )
    messages.success(
        request,
        f"„{eintrag.schluessel}“: {alt} → {neuer_wert}. Grund steht im öffentlichen Audit-Log.",
    )
    return redirect("parameter:verwaltung")


@nur_admins
@require_POST
def verwaltung_ordnung_entwurf(request):
    """Erzeugt aus dem Register eine neue Fassung der Verfahrensordnung — ohne Kraft (FB-J1).

    Zwei Schritte statt einem: Erzeugen ist eine Rechnung, In-Kraft-Setzen eine Entscheidung.
    Die Satzung weist die Entscheidung der Mitgliederversammlung zu (§ 5 Abs 7); solange die
    Plattform diese Abstimmung nicht führen kann, handelt die Verwaltung stellvertretend —
    und jeder Schritt steht mit Grund im öffentlichen Audit-Log."""
    from plattform_core.policy import PolicyFehler, aus_register
    from verfahren.models import Verfahrensordnung

    aktiv = _aktive_ordnung()
    kennung = _policy_id(aktiv)
    version = _naechste_version(kennung)
    try:
        erzeugt = aus_register(
            _register_werte(), kennung, version, mehrheitsbasis=_mehrheitsbasis(aktiv)
        )
    except PolicyFehler as ausnahme:
        messages.error(request, f"Keine Fassung erzeugt: {ausnahme}")
        return redirect("parameter:verwaltung")
    # Verglichen wird mit der juengsten vorhandenen Fassung, nicht nur mit der geltenden:
    # Sonst haette ein zweiter Klick eine zweite, wortgleiche Fassung erzeugt, und die
    # Versionsnummern haetten Aenderungen behauptet, die es nie gab.
    juengste = (
        Verfahrensordnung.objects.filter(policy_id=kennung).order_by("-version").first()
    )
    if juengste is not None and _wesentlich(juengste.regeln) == _wesentlich(erzeugt.als_dict()):
        if juengste.aktiv:
            messages.info(request, "Register und geltende Fassung sagen dasselbe — nichts zu erzeugen.")
        else:
            messages.info(
                request,
                f"Fassung {juengste.version} sagt bereits genau das und wartet auf den zweiten Schritt.",
            )
        return redirect("parameter:verwaltung")
    Verfahrensordnung.objects.create(
        policy_id=kennung, version=version, regeln=erzeugt.als_dict(), aktiv=False
    )
    AuditEintrag.anhaengen(
        {
            "typ": "verfahrensordnung_erzeugt",
            "policy_id": kennung,
            "version": version,
            "regeln": erzeugt.als_dict(),
        }
    )
    messages.success(
        request,
        f"Fassung {version} erzeugt. Sie gilt noch nicht — dafür braucht es den zweiten Schritt.",
    )
    return redirect("parameter:verwaltung")


@nur_admins
@require_POST
def verwaltung_ordnung_inkraft(request):
    """Setzt eine erzeugte Fassung in Kraft (FB-J1).

    Laufende Verfahren berührt das nicht: Sie tragen ihre eigene Kopie (§ 5 Abs 5). Die alte
    Fassung wird nicht gelöscht, nur abgelöst (Grundregel 7) — sonst wäre später nicht mehr
    nachvollziehbar, nach welchen Regeln ein abgeschlossenes Verfahren gelaufen ist."""
    from verfahren.models import Verfahrensordnung

    fassung = get_object_or_404(Verfahrensordnung, pk=request.POST.get("ordnung"))
    vorher = _aktive_ordnung()
    # Nur innerhalb derselben Reihe: Eine fremde Kennung waere ein anderes Regelwerk, und der
    # Weg dorthin fuehrt nicht ueber einen Knopf in der Parameterverwaltung.
    if vorher is not None and fassung.policy_id != vorher.policy_id:
        messages.error(
            request,
            f"„{fassung.policy_id}“ ist eine andere Verfahrensordnung als die geltende "
            f"„{vorher.policy_id}“ — ein Wechsel gehört nicht in die Parameterverwaltung.",
        )
        return redirect("parameter:verwaltung")
    grund = (request.POST.get("grund") or "").strip()
    if not grund:
        messages.error(request, "Ohne Grund tritt keine Fassung in Kraft — er wird veröffentlicht.")
        return redirect("parameter:verwaltung")
    if fassung.aktiv:
        messages.info(request, f"Fassung {fassung.version} gilt bereits.")
        return redirect("parameter:verwaltung")
    # Alle geltenden Fassungen abloesen, nicht nur die mit derselben Kennung: Das Einbringen
    # nimmt die aktive Ordnung ohne Rücksicht auf den Namen — zwei aktive wären ein Zufall.
    Verfahrensordnung.objects.filter(aktiv=True).update(aktiv=False)
    fassung.aktiv = True
    fassung.beschlossen_am = timezone.now()
    fassung.save(update_fields=["aktiv", "beschlossen_am"])
    AuditEintrag.anhaengen(
        {
            "typ": "verfahrensordnung_in_kraft",
            "policy_id": fassung.policy_id,
            "version": fassung.version,
            "vorher": vorher.version if vorher else None,
            "grund": grund[:500],
        }
    )
    messages.success(
        request,
        f"Fassung {fassung.version} gilt ab jetzt für neu eingebrachte Anträge. "
        "Laufende Verfahren behalten ihre Fassung.",
    )
    return redirect("parameter:verwaltung")
