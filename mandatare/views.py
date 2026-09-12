"""Mandatare-Ansichten (F-71, S10): öffentlicher Bereich, Rechenschaftsregister, der Bereich
des Mandatars und die Verwaltung.

Öffentlich: Liste und Detailseite je Mandatar — Foto, Instant-Reports samt Fristen und
Sitzungstagen, verknüpfte Mandatsfragen, Berichte (§ 7 Abs 3 lit b) und Rechenschaft
(§ 7 Abs 5) mit ihren Ausständen; dazu das Register `/rechenschaft/` (auch als JSON) und der
Wahlvorschlag-Export einer beendeten Kandidatur (§ 7 Abs 1).

Bereich des Mandatars (`/mandatare/mein/`): Die Rolle ist abgeleitet — wer ein offenes Mandat
hat, liest; wer zudem mitwirken darf (Status aktiv und Identität geprüft, wie beim Einbringen),
schreibt. Nach dem Mandatsende bleibt der Bereich für die Nachfrist (`mandatare.models.NACHFRIST_TAGE`)
offen — nur noch für Sammelbericht, Rechenschaft und Monatsbericht, denn die Pflicht aus der
letzten Sitzung überlebt das Ende (§ 7 Abs 5). Jede Handlung ist ein POST auf `mein_aktion`,
prüft den Besitz des Mandats und wird auditiert (nur Kennungen, keine Werte).

Verwaltung: legt Mandate an (mit Kandidatur, § 6 Abs 3 lit a geprüft), beendet sie, kann
weiter Aufgaben und Fotos pflegen."""

from __future__ import annotations

from datetime import UTC, date, datetime, time, timedelta
from functools import wraps

from django import forms
from django.contrib import messages
from django.db.models import Count, Prefetch
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from mandatare.models import (
    FOTO_HOECHSTGROESSE,
    Aufgabe,
    Aufgabenstatus,
    Bericht,
    Berichtsart,
    Beschluss,
    Mandat,
    Rechenschaft,
    Stimmverhalten,
    foto_typ_erkennen,
)
from mitglieder.models import Identitaetsstufe, Mitglied, Mitgliedsstatus
from mitglieder.verwaltung import nur_admins
from plattform_core import Phase
from plattform_core.rechenschaft import berichtsmonate
from verfahren.models import (
    Antrag,
    Antragsart,
    AuditEintrag,
    Ebene,
    MandatsfrageFehler,
    Verfahrensordnung,
    mandatsfrage_eroeffnen,
)

LAUFEND = [Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value]
BEENDET = (Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value)

#: Grenzen des Instant-Reports (E3) und der Einträge — das Modell erlaubt mehr, das Formular nicht.
REPORT_TITEL_MAX = 120
REPORT_BESCHREIBUNG_MAX = 1000
VORSTELLUNG_MAX = 2000
BERICHT_MAX = 8000
GEGENSTAND_MAX = 200
BEGRUENDUNG_MAX = 4000
RECHENSCHAFT_AUSZUG = 5
#: Berichte auf der öffentlichen Detailseite — der Rest steht vollständig unter `berichte`.
BERICHTE_AUSZUG = 12
#: Ein zweiter, gleichlautender Report desselben Mandats binnen dieser Sekunden ist eine
#: Doppelabsendung (Doppelklick, Zurück + neu senden), kein neuer Report.
DOPPELABSENDUNG_SEKUNDEN = 120
#: Fristen des Instant-Reports müssen in diesem Jahresfenster liegen — Werte am Rand des
#: Datumsbereichs (Jahr 1, Jahr 9999) laufen sonst beim Speichern über.
FRIST_JAHR_MIN, FRIST_JAHR_MAX = 2000, 2200
#: Handlungen, die nach dem Mandatsende in der Nachfrist noch erlaubt sind (§ 7 Abs 5).
NACHFRIST_AKTIONEN = ("sammelbericht", "rechenschaft", "monatsbericht")

#: Aufgaben samt verknüpftem Antrag vorladen — `_aufgaben_sortiert` und `offene_pflichten_fuer`
#: lesen dann `aufgaben.all()` ohne weitere Abfrage.
AUFGABEN_VORGELADEN = Prefetch("aufgaben", queryset=Aufgabe.objects.select_related("antrag"))


# ── Helfer ────────────────────────────────────────────────────────────────────────────────


def _mandat_queryset():
    return Mandat.objects.select_related("mitglied").prefetch_related(AUFGABEN_VORGELADEN)


def _aufgaben_sortiert(mandat):
    """Offene und laufende Aufgaben zuerst, innerhalb dessen die nächste Frist
    vorn (ohne Frist zuletzt); Erledigtes am Ende. Nutzt das Prefetch, wo es eines gibt."""
    if "aufgaben" in getattr(mandat, "_prefetched_objects_cache", {}):
        alle = list(mandat.aufgaben.all())
    else:
        alle = list(mandat.aufgaben.select_related("antrag"))
    jetzt = timezone.now()
    fern = jetzt.replace(year=jetzt.year + 100)  # Frist ist seit 0.46 ein Zeitpunkt
    return sorted(
        alle,
        key=lambda a: (a.status == Aufgabenstatus.ERLEDIGT, a.frist or fern, -a.pk),
    )


def _frist_aus_eingabe(datum: str, zeit: str) -> datetime:
    """Datum (Pflicht) und Uhrzeit (optional, sonst 23:59) → Zeitpunkt in Wiener Zeit.
    Wirft ValueError bei unbrauchbarer Eingabe — auch bei einem Datum außerhalb des
    Jahresfensters oder am Rand des Wertebereichs (die UTC-Umrechnung liefe sonst erst beim
    Speichern über, als Serverfehler statt als Meldung)."""
    tag = date.fromisoformat((datum or "").strip())
    uhr = time.fromisoformat(zeit.strip()) if (zeit or "").strip() else time(23, 59)
    if not FRIST_JAHR_MIN <= tag.year <= FRIST_JAHR_MAX:
        raise ValueError("Frist außerhalb des zulässigen Jahresfensters")
    frist = timezone.make_aware(datetime.combine(tag, uhr))
    try:
        frist.astimezone(UTC)
    except OverflowError as fehler:
        raise ValueError("Frist außerhalb des darstellbaren Bereichs") from fehler
    return frist


def _tage_bis(frist, heute: date) -> int:
    """Kalendertage bis zur Frist (negativ: seit der Frist) — der Zähler „noch n Tage"."""
    return (timezone.localdate(frist) - heute).days


def _antraege_fortschreiben(aufgaben) -> None:
    """Verknüpfte Abstimmungen auf den Stand bringen (idempotent, wie auf der Antragsseite)."""
    for a in aufgaben:
        if a.antrag_id and a.antrag.phase == Phase.ABSTIMMUNG.value:
            a.antrag.fortschreiben()


def _aufgaben_mit_lage(mandat, aufgaben, pflichten: dict, heute: date) -> list[dict]:
    """Je Aufgabe der Fristzähler und — bei vergangenen Sitzungstagen — der Stand von
    Sammelbericht und Rechenschaft (`Lage` aus `Mandat.offene_pflichten`, sonst erledigt).
    `anker` führt bei einer laufenden Abstimmung an die richtige Stelle der Antragsseite:
    Personenwahlen stimmen unter den Bewerbungen ab, alles andere im Ja-Nein-Block."""
    sammel_offen = {p["aufgabe"].pk: p for p in pflichten["sammelberichte"]}
    rechenschaft_offen = {p["aufgabe"].pk: p for p in pflichten["rechenschaften"]}
    jetzt = timezone.now()
    zeilen = []
    for a in aufgaben:
        tage = _tage_bis(a.frist, heute) if a.frist else None
        vorbei = a.sitzungstag and a.frist is not None and a.frist <= jetzt
        laeuft = a.antrag_id is not None and a.antrag.phase == Phase.ABSTIMMUNG.value
        zeilen.append(
            {
                "aufgabe": a,
                "tage": abs(tage) if tage is not None else None,
                "frist_vorbei": tage is not None and tage < 0,
                "sitzung_vorbei": vorbei,
                "sammelbericht": sammel_offen.get(a.pk) if vorbei else None,
                "rechenschaft": rechenschaft_offen.get(a.pk) if vorbei else None,
                "beendet": a.antrag_id is not None and a.antrag.phase in BEENDET,
                "abstimmung_laeuft": laeuft,
                "anker": ("#bewerbungen" if a.antrag.art == Antragsart.MANDAT else "#abstimmen") if laeuft else "",
            }
        )
    return zeilen


def _rechenschaft_zeilen(eintraege) -> list[dict]:
    """Einträge mit dem Beschluss der Plattform — bei verknüpftem Antrag live aus dessen Phase
    (`Rechenschaft.beschluss_anzeige`), damit ein Eintrag aus der Zeit vor Abstimmungsende
    nicht „kein Beschluss" behält; der gespeicherte Wert wird dabei nachgezogen."""
    zeilen = []
    for r in eintraege:
        r.beschluss_nachziehen()
        beschluss = r.beschluss_anzeige
        zeilen.append(
            {
                "r": r,
                "beschluss": beschluss,
                "beschluss_name": Beschluss(beschluss).label,
                "weicht_ab": r.weicht_ab,
            }
        )
    return zeilen


def _berichte_zeilen(berichte, heute: date, karenz: int) -> list[dict]:
    """Berichte je Bezug (Monat bzw. Sitzungstag) chronologisch, neuester Bezug zuerst; der
    erste Bericht eines Bezugs trägt die Lage gegenüber der Frist, jeder weitere ist ein
    Nachtrag (ohne Fristurteil — die Pflicht war mit dem ersten erfüllt)."""
    geordnet = sorted(berichte, key=lambda b: b.eingereicht_am)
    gesehen: set = set()
    zeilen = []
    for b in geordnet:
        schluessel = (b.art, b.monat if b.art == Berichtsart.MONATSBERICHT else b.aufgabe_id)
        nachtrag = schluessel in gesehen
        gesehen.add(schluessel)
        zeilen.append(
            {
                "b": b,
                "nachtrag": nachtrag,
                "lage": None if nachtrag else b.lage(heute, karenz),
                "bezug": b.bezugstag or timezone.localdate(b.eingereicht_am),
            }
        )
    zeilen.sort(key=lambda z: (-z["bezug"].toordinal(), z["b"].eingereicht_am))
    return zeilen


def _mit_zaehlern(pflichten: dict) -> dict:
    return {
        **pflichten,
        "rechenschaft_ausstaendig": sum(1 for p in pflichten["rechenschaften"] if p["lage"].status == "ausstaendig"),
        "sammelbericht_ausstaendig": sum(
            1 for p in pflichten["sammelberichte"] if p["lage"].status == "ausstaendig"
        ),
        "monatsbericht_ausstaendig": sum(
            1 for p in pflichten["monatsberichte"] if p["lage"].status == "ausstaendig"
        ),
    }


def _ausstaende(mandat, heute: date | None = None) -> dict:
    """Offene Pflichten eines Mandats samt Zählern für die öffentliche Anzeige."""
    return _mit_zaehlern(mandat.offene_pflichten(heute))


def _ausstaende_fuer(mandate, heute: date | None = None) -> dict[int, dict]:
    """Dasselbe für viele Mandate — die Abfragezahl hängt nicht von der Zahl der Mandate ab."""
    return {pk: _mit_zaehlern(p) for pk, p in Mandat.offene_pflichten_fuer(mandate, heute).items()}


# ── Öffentlich ────────────────────────────────────────────────────────────────────────────


def liste(request):
    mandate = list(
        _mandat_queryset()
        .filter(beendet__isnull=True)
        .annotate(rechenschaft_anzahl=Count("rechenschaft"))
    )
    ausstaende = _ausstaende_fuer(mandate)
    fuer_karten = []
    for m in mandate:
        fuer_karten.append(
            {
                "mandat": m,
                "aufgaben": [a for a in _aufgaben_sortiert(m) if a.status != Aufgabenstatus.ERLEDIGT][:2],
                "rechenschaft_anzahl": m.rechenschaft_anzahl,
                "rechenschaft_ausstaendig": ausstaende[m.pk]["rechenschaft_ausstaendig"],
            }
        )
    kandidaturen = (
        Antrag.objects.filter(art=Antragsart.MANDAT, phase__in=LAUFEND).order_by("phase_beginn")[:6]
    )
    return render(
        request,
        "mandatare/liste.html",
        {
            "karten": fuer_karten,
            "ehemalige": Mandat.objects.filter(beendet__isnull=False).count(),
            "kandidaturen": kandidaturen,
        },
    )


def detail(request, pk: int):
    mandat = get_object_or_404(_mandat_queryset(), pk=pk)
    aufgaben = _aufgaben_sortiert(mandat)
    _antraege_fortschreiben(aufgaben)
    heute = timezone.localdate()
    ausstaende = _ausstaende(mandat)
    rechenschaft = list(mandat.rechenschaft.select_related("antrag", "aufgabe")[:RECHENSCHAFT_AUSZUG])
    berichte = list(mandat.berichte.select_related("aufgabe"))
    zeilen = _berichte_zeilen(berichte, heute, ausstaende["karenz"])
    return render(
        request,
        "mandatare/detail.html",
        {
            "mandat": mandat,
            "aufgaben": _aufgaben_mit_lage(mandat, aufgaben, ausstaende, heute),
            "berichte": zeilen[:BERICHTE_AUSZUG],
            "berichte_anzahl": len(zeilen),
            "berichte_weitere": max(0, len(zeilen) - BERICHTE_AUSZUG),
            "ausstaende": ausstaende,
            "rechenschaft": _rechenschaft_zeilen(rechenschaft),
            "rechenschaft_anzahl": mandat.rechenschaft.count(),
        },
    )


def berichte(request, pk: int):
    """§ 7 Abs 3 lit b: alle Berichte eines Mandatars — Monats- und Sammelberichte samt
    Nachträgen, neuester Bezug zuerst; die Detailseite zeigt nur einen Auszug."""
    mandat = get_object_or_404(_mandat_queryset(), pk=pk)
    heute = timezone.localdate()
    ausstaende = _ausstaende(mandat)
    zeilen = _berichte_zeilen(list(mandat.berichte.select_related("aufgabe")), heute, ausstaende["karenz"])
    return render(
        request,
        "mandatare/berichte.html",
        {"mandat": mandat, "berichte": zeilen, "ausstaende": ausstaende},
    )


def foto(request, pk: int):
    mandat = get_object_or_404(Mandat, pk=pk)
    if not mandat.foto:
        raise Http404("Kein Foto hinterlegt.")
    antwort = HttpResponse(bytes(mandat.foto), content_type=mandat.foto_typ or "image/jpeg")
    antwort["Cache-Control"] = "public, max-age=3600"
    return antwort


def rechenschaft_mandat(request, pk: int):
    """§ 7 Abs 5: das ganze Register eines Mandatars, mit Ausständen."""
    mandat = get_object_or_404(_mandat_queryset(), pk=pk)
    eintraege = list(mandat.rechenschaft.select_related("antrag", "aufgabe"))
    return render(
        request,
        "mandatare/rechenschaft_mandat.html",
        {
            "mandat": mandat,
            "zeilen": _rechenschaft_zeilen(eintraege),
            "ausstaende": _ausstaende(mandat),
        },
    )


def _rechenschaft_gesamt(ebene: str):
    eintraege = Rechenschaft.objects.select_related("mandat__mitglied", "antrag", "aufgabe")
    if ebene in Ebene.values:
        eintraege = eintraege.filter(mandat__ebene=ebene)
    eintraege = eintraege.order_by("-sitzung_am", "-eingetragen_am")
    aktive = _mandat_queryset().filter(beendet__isnull=True)
    if ebene in Ebene.values:
        aktive = aktive.filter(ebene=ebene)
    aktive = list(aktive)
    pflichten = _ausstaende_fuer(aktive)
    ausstaende = []
    for m in aktive:
        offen = pflichten[m.pk]
        if offen["rechenschaften"]:
            ausstaende.append({"mandat": m, "rechenschaften": offen["rechenschaften"]})
    return eintraege, ausstaende


def rechenschaft(request):
    """Das Rechenschaftsregister aller Mandatare — neueste zuerst, Filter nach Ebene."""
    ebene = (request.GET.get("ebene") or "").strip()
    if ebene not in Ebene.values:
        ebene = ""
    eintraege, ausstaende = _rechenschaft_gesamt(ebene)
    return render(
        request,
        "mandatare/rechenschaft.html",
        {
            "zeilen": _rechenschaft_zeilen(list(eintraege)),
            "ausstaende": ausstaende,
            "ebene": ebene,
            "ebenen": Ebene.choices,
        },
    )


def rechenschaft_json(request):
    """Das Register maschinenlesbar — ohne Personenbezug über den Anzeigenamen hinaus."""
    ebene = (request.GET.get("ebene") or "").strip()
    if ebene not in Ebene.values:
        ebene = ""
    eintraege, ausstaende = _rechenschaft_gesamt(ebene)
    daten = {
        "eintraege": [
            {
                "id": z["r"].pk,
                "mandat": z["r"].mandat_id,
                "mandatar": z["r"].mandat.mitglied.anzeigename,
                "bezeichnung": z["r"].mandat.bezeichnung,
                "ebene": z["r"].mandat.ebene,
                "gebiet": z["r"].mandat.gebiet,
                "gegenstand": z["r"].gegenstand,
                "sitzung_am": z["r"].sitzung_am.isoformat(),
                "beschluss_plattform": z["beschluss"],
                "antrag": z["r"].antrag_id,
                "aufgabe": z["r"].aufgabe_id,
                "stimme": z["r"].stimme,
                "weicht_ab": z["weicht_ab"],
                "begruendung": z["r"].begruendung,
                "eingetragen_am": z["r"].eingetragen_am.isoformat(),
                "frist": z["r"].frist.isoformat(),
                "lage": z["r"].lage().status,
            }
            for z in _rechenschaft_zeilen(list(eintraege))
        ],
        "ausstaende": [
            {
                "mandat": block["mandat"].pk,
                "mandatar": block["mandat"].mitglied.anzeigename,
                "aufgabe": p["aufgabe"].pk,
                "sitzungstag": p["sitzungstag"].isoformat(),
                "faellig": p["faellig"].isoformat(),
                "lage": p["lage"].status,
                "seit_tagen": p["lage"].seit_tagen,
                "resttage": p["lage"].resttage,
            }
            for block in ausstaende
            for p in block["rechenschaften"]
        ],
        "ebene": ebene or None,
        "exportiert_am": timezone.now().isoformat(),
    }
    return JsonResponse(daten, json_dumps_params={"ensure_ascii": False, "indent": 1})


def wahlvorschlag(request, antrag_pk: int):
    """§ 7 Abs 1: die Reihung einer beendeten Kandidatur als Markdown — die Form für die
    Wahlbehörde richtet sich nach der jeweiligen Wahlordnung."""
    antrag = get_object_or_404(Antrag, pk=antrag_pk, art=Antragsart.MANDAT)
    antrag.fortschreiben()
    if antrag.phase not in BEENDET:
        raise Http404("Kandidatur noch nicht beendet.")
    wahl = antrag.kandidatur_auszaehlen()
    namen = {b.pk: b.mitglied.anzeigename for b in antrag.bewerbungen.select_related("mitglied")}
    ort = antrag.gebiet or antrag.get_ebene_display()
    zeilen = [
        f"# {_('Wahlvorschlag')}: {antrag.titel}",
        "",
        f"{_('Antrag')} #{antrag.pk} · {ort} · {_('Abstimmung beendet am')} "
        f"{timezone.localtime(antrag.phase_beginn):%d.%m.%Y}",
        f"{_('Stimmberechtigte')}: {antrag.stimmberechtigte_anzahl or 0} · "
        f"{_('Beteiligung')}: {wahl.beteiligung} · "
        f"{_('Mindestbeteiligung erreicht')}: {_('ja') if wahl.beteiligung_erreicht else _('nein')}",
        "",
        f"| {_('Platz')} | {_('Anzeigename')} | {_('Zustimmungen')} |",
        "|---:|---|---:|",
    ]
    for p in wahl.plaetze:
        zeilen.append(f"| {p.platz} | {namen.get(p.bewerbung_id, f'#{p.bewerbung_id}')} | {p.stimmen} |")
    if not wahl.plaetze:
        zeilen.append(f"| – | {_('keine Bewerbung')} | – |")
    zeilen += [
        "",
        _("Reihung nach § 7 Abs 1; die Form für die Wahlbehörde richtet sich nach der jeweiligen Wahlordnung."),
        "",
        f"{_('Quelle')}: {request.build_absolute_uri(reverse('verfahren:antrag', args=[antrag.pk]))} · "
        f"{_('Export zum Nachrechnen')}: {request.build_absolute_uri(reverse('verfahren:export', args=[antrag.pk]))}",
        f"{_('Erstellt am')} {timezone.localtime():%d.%m.%Y %H:%M}",
        "",
    ]
    antwort = HttpResponse("\n".join(zeilen), content_type="text/markdown; charset=utf-8")
    antwort["Content-Disposition"] = f'inline; filename="wahlvorschlag-{antrag.pk}.md"'
    return antwort


# ── Bereich des Mandatars ─────────────────────────────────────────────────────────────────


def nur_mandatare(ansicht):
    """Zugang für Inhaber eines offenen Mandats (E1, E8) — und, für die Nachfrist, eines gerade
    beendeten: anonym → Anmeldung; ohne Mandat → 403. Lesen genügt das Mandat; jede Handlung
    prüft zusätzlich Status aktiv und geprüfte Identität (§ 4 Abs 2), wie beim Einbringen."""

    @wraps(ansicht)
    def innen(request, *args, **kwargs):
        if not request.user.is_authenticated:
            return redirect("mitglieder:login")
        if not Mandat.zugaenglich_von(request.user).exists():
            return render(request, "mandatare/kein_zugang.html", status=403)
        return ansicht(request, *args, **kwargs)

    return innen


def _mitwirkung_gesperrt(request):
    """Dieselbe Antwort wie beim Einbringen: Identität ungeprüft oder Status nicht aktiv → 403."""
    from verfahren.views_aktionen import _mitwirkung_gesperrt as gesperrt

    return gesperrt(request)


def _eigene_mandate(request) -> list[Mandat]:
    return list(Mandat.zugaenglich_von(request.user).select_related("mitglied"))


def _bereich(request, mandat: Mandat, mandate: list[Mandat], eingabe=None):
    """Der Bereich. `eingabe` (request.POST) belegt nach einem Validierungsfehler das betroffene
    Formular wieder vor, damit nichts Eingetipptes verloren geht (Grundregel 3: ohne Skript)."""
    aufgaben = _aufgaben_sortiert(mandat)
    _antraege_fortschreiben(aufgaben)
    heute = timezone.localdate()
    jetzt = timezone.now()
    ausstaende = _ausstaende(mandat)
    sitzungstage_vorbei = [
        a
        for a in aufgaben
        if a.sitzungstag and a.frist is not None and a.frist <= jetzt
        and (mandat.beendet is None or timezone.localdate(a.frist) <= mandat.beendet)
    ]
    ohne_sammelbericht = {p["aufgabe"].pk for p in ausstaende["sammelberichte"]}
    ohne_rechenschaft = {p["aufgabe"].pk for p in ausstaende["rechenschaften"]}
    faellig = {p["monat"] for p in ausstaende["monatsberichte"]}
    monate_nachtrag = [
        m for m in reversed(berichtsmonate(mandat.angetreten, mandat.beendet, heute)) if m not in faellig
    ]
    mitwirken = request.user.darf_mitwirken and request.user.identitaetsstufe != Identitaetsstufe.UNGEPRUEFT
    aktion = (eingabe.get("aktion") if eingabe is not None else "") or ""
    return render(
        request,
        "mandatare/mein.html",
        {
            "mandat": mandat,
            "mandate": mandate,
            "darf_schreiben": mitwirken and mandat.aktiv,
            "darf_berichten": mitwirken and (mandat.aktiv or mandat.in_nachfrist(heute)),
            "identitaet_ungeprueft": request.user.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT,
            "aufgaben": _aufgaben_mit_lage(mandat, aufgaben, ausstaende, heute),
            "ausstaende": ausstaende,
            "monate_faellig": ausstaende["monatsberichte"],
            "monate_nachtrag": monate_nachtrag,
            "sitzungstage": [
                {"aufgabe": a, "ohne_sammelbericht": a.pk in ohne_sammelbericht, "ohne_rechenschaft": a.pk in ohne_rechenschaft}
                for a in sitzungstage_vorbei
            ],
            "berichte": _berichte_zeilen(list(mandat.berichte.select_related("aufgabe")), heute, ausstaende["karenz"]),
            "rechenschaft": _rechenschaft_zeilen(list(mandat.rechenschaft.select_related("antrag", "aufgabe"))),
            "stimmen": Stimmverhalten.choices,
            "beschluesse": Beschluss.choices,
            "vorgewaehlt": ((eingabe.get("aufgabe") if aktion == "rechenschaft" else request.GET.get("aufgabe")) or "").strip(),
            "ordnung_fehlt": not Verfahrensordnung.objects.filter(aktiv=True).exists(),
            "eingabe": eingabe,
            "fehler_bei": aktion,
        },
    )


@nur_mandatare
def mein(request):
    """Ein Mandat → der Bereich; mehrere → Auswahl (wie `gremien:mein`)."""
    mandate = _eigene_mandate(request)
    if len(mandate) == 1:
        return _bereich(request, mandate[0], mandate)
    return render(request, "mandatare/mein_wahl.html", {"mandate": mandate})


@nur_mandatare
def mein_mandat(request, pk: int):
    mandat = get_object_or_404(_mandat_queryset(), pk=pk)
    if mandat.mitglied_id != request.user.pk or not (mandat.aktiv or mandat.in_nachfrist()):
        return render(request, "mandatare/kein_zugang.html", status=403)
    return _bereich(request, mandat, _eigene_mandate(request))


def _zurueck(request, mandat: Mandat):
    if Mandat.zugaenglich_von(request.user).count() == 1:
        return redirect("mandatare:mein")
    return redirect("mandatare:mein_mandat", pk=mandat.pk)


def _eigener_sitzungstag(mandat: Mandat, pk: str) -> Aufgabe | None:
    """Eine vergangene Sitzungstag-Aufgabe dieses Mandats — sonst None. Bei beendetem Mandat
    nur Sitzungstage bis zum Endtag (danach bestand keine Pflicht, § 7 Abs 5)."""
    if not (pk or "").isdigit():
        return None
    aufgabe = mandat.aufgaben.filter(pk=int(pk), sitzungstag=True, frist__isnull=False).first()
    if aufgabe is None or aufgabe.frist > timezone.now():
        return None
    if mandat.beendet is not None and timezone.localdate(aufgabe.frist) > mandat.beendet:
        return None
    return aufgabe


@require_POST
def mein_aktion(request):
    """Alle Handlungen des Mandatars — ein POST je Handlung, Dispatch über `aktion`.
    Jede prüft: eigenes Mandat (offen — oder beendet in der Nachfrist, dann nur Sammelbericht,
    Rechenschaft und Monatsbericht); Mitwirkung erlaubt (Status aktiv, Identität geprüft).
    Jede auditiert. Ein Validierungsfehler rendert den Bereich mit der Eingabe neu."""
    if not request.user.is_authenticated:
        return redirect("mitglieder:login")
    pk = (request.POST.get("mandat") or "").strip()
    mandat = Mandat.objects.filter(pk=int(pk)).first() if pk.isdigit() else None
    aktion = request.POST.get("aktion", "")
    if mandat is None or mandat.mitglied_id != request.user.pk:
        return render(request, "mandatare/kein_zugang.html", status=403)
    if not mandat.aktiv and not (mandat.in_nachfrist() and aktion in NACHFRIST_AKTIONEN):
        return render(request, "mandatare/kein_zugang.html", status=403)
    gesperrt = _mitwirkung_gesperrt(request)
    if gesperrt is not None:
        return gesperrt

    gelungen = True
    if aktion == "report":
        gelungen = _report_anlegen(request, mandat)
    elif aktion == "aufgabe_status":
        aufgabe_pk = (request.POST.get("aufgabe") or "").strip()
        if not aufgabe_pk.isdigit():
            raise Http404("Aufgabe unbekannt.")  # sonst ValueError → 500 bei verformter Eingabe
        aufgabe = get_object_or_404(Aufgabe, pk=int(aufgabe_pk), mandat=mandat)
        status = request.POST.get("status", "")
        if status in Aufgabenstatus.values:
            aufgabe.status = status
            aufgabe.save(update_fields=["status", "aktualisiert_am"])
            AuditEintrag.anhaengen({"typ": "mandats_aufgabe_status", "mandat": mandat.pk, "aufgabe": aufgabe.pk})
            messages.success(
                request, _("„%(titel)s“: %(status)s.") % {"titel": aufgabe.titel, "status": aufgabe.get_status_display()}
            )
    elif aktion == "foto":
        _foto_speichern(request, mandat)
    elif aktion == "vorstellung":
        mandat.vorstellung = (request.POST.get("vorstellung") or "").strip()[:VORSTELLUNG_MAX]
        mandat.save(update_fields=["vorstellung"])
        AuditEintrag.anhaengen({"typ": "mandat_vorstellung", "mandat": mandat.pk})
        messages.success(request, _("Vorstellung gespeichert."))
    elif aktion == "monatsbericht":
        _monatsbericht_anlegen(request, mandat)
    elif aktion == "sammelbericht":
        _sammelbericht_anlegen(request, mandat)
    elif aktion == "rechenschaft":
        gelungen = _rechenschaft_anlegen(request, mandat)
    else:
        messages.error(request, _("Unbekannte Handlung."))
    if not gelungen:
        # Kein Redirect: Das Formular kommt mit den eingegebenen Werten zurück, die Meldung dazu.
        mandat = get_object_or_404(_mandat_queryset(), pk=mandat.pk)
        return _bereich(request, mandat, _eigene_mandate(request), eingabe=request.POST)
    return _zurueck(request, mandat)


def _doppelter_report(mandat: Mandat, titel: str, frist: datetime) -> Aufgabe | None:
    """Denselben Report gibt es schon — gleicher Titel, gleiche Frist, eben erst angelegt."""
    seit = timezone.now() - timedelta(seconds=DOPPELABSENDUNG_SEKUNDEN)
    return (
        mandat.aufgaben.filter(titel=titel, frist=frist, erstellt_am__gte=seit)
        .select_related("antrag")
        .order_by("-erstellt_am")
        .first()
    )


def _report_anlegen(request, mandat: Mandat) -> bool:
    """Instant-Report anlegen; False bei einem Eingabefehler (der Bereich rendert dann neu)."""
    titel = (request.POST.get("titel") or "").strip()
    if not titel:
        messages.error(request, _("Der Report braucht einen Titel."))
        return False
    try:
        frist = _frist_aus_eingabe(request.POST.get("frist_datum", ""), request.POST.get("frist_zeit", ""))
    except ValueError:
        messages.error(request, _("Bitte ein gültiges Datum (und gegebenenfalls eine Uhrzeit) angeben."))
        return False
    beschreibung = (request.POST.get("beschreibung") or "").strip()[:REPORT_BESCHREIBUNG_MAX]
    bestehend = _doppelter_report(mandat, titel[:REPORT_TITEL_MAX], frist)
    if bestehend is not None:
        if bestehend.antrag_id:
            messages.info(
                request,
                format_html(
                    '{} <a href="{}">{}</a>',
                    _("Dieser Report ist bereits angelegt — kein zweites Mal."),
                    reverse("verfahren:antrag", args=[bestehend.antrag_id]),
                    _("Zur Abstimmung →"),
                ),
            )
        else:
            messages.info(request, _("Dieser Report ist bereits angelegt — kein zweites Mal."))
        return True
    aufgabe = Aufgabe.objects.create(
        mandat=mandat,
        titel=titel[:REPORT_TITEL_MAX],
        beschreibung=beschreibung,
        frist=frist,
        sitzungstag=request.POST.get("sitzungstag") == "on",
    )
    AuditEintrag.anhaengen({"typ": "instant_report", "mandat": mandat.pk, "aufgabe": aufgabe.pk})
    if request.POST.get("abstimmung") != "on":
        messages.success(request, _("Report veröffentlicht."))
        return True
    ordnung = Verfahrensordnung.objects.filter(aktiv=True).order_by("-version").first()
    if ordnung is None:
        messages.warning(
            request,
            _("Report veröffentlicht — ohne Abstimmung: Es gilt noch keine Verfahrensordnung."),
        )
        return True
    try:
        # Die gekürzten Werte der Aufgabe, nicht die rohe Eingabe: Antrag.titel fasst 200 Zeichen,
        # der Report 120 — ein längerer POST liefe auf PostgreSQL sonst in einen DataError.
        antrag = mandatsfrage_eroeffnen(mandat, aufgabe, aufgabe.titel, aufgabe.beschreibung or aufgabe.titel, ordnung)
    except MandatsfrageFehler as fehler:
        messages.warning(
            request, _("Report veröffentlicht — ohne Abstimmung: %(grund)s") % {"grund": fehler}
        )
        return True
    messages.success(
        request,
        format_html(
            '{} <a href="{}">{}</a>',
            _("Report veröffentlicht und Mandatsfrage eröffnet — sie steht jetzt in der Abstimmung."),
            reverse("verfahren:antrag", args=[antrag.pk]),
            _("Zur Abstimmung →"),
        ),
    )
    return True


def _foto_speichern(request, mandat: Mandat) -> None:
    datei = request.FILES.get("foto")
    if datei is None or datei.size > FOTO_HOECHSTGROESSE:
        messages.error(request, _("Bitte ein Bild bis 800 kB wählen (JPEG, PNG oder WebP)."))
        return
    daten = datei.read()
    typ = foto_typ_erkennen(daten)
    if typ is None:
        messages.error(request, _("Dateityp nicht erkannt — erlaubt sind JPEG, PNG und WebP."))
        return
    mandat.foto = daten
    mandat.foto_typ = typ
    mandat.save(update_fields=["foto", "foto_typ"])
    AuditEintrag.anhaengen({"typ": "mandat_foto", "mandat": mandat.pk})
    messages.success(request, _("Foto gespeichert."))


def _monatsbericht_anlegen(request, mandat: Mandat) -> None:
    """Monatsbericht für einen geschuldeten Monat — fällig oder als Nachtrag zu einem schon
    berichteten Monat (kein Bearbeiten: der Nachtrag ist ein weiterer Bericht)."""
    text = (request.POST.get("text") or "").strip()
    try:
        monat = date.fromisoformat((request.POST.get("monat") or "").strip()).replace(day=1)
    except ValueError:
        monat = None
    pflichten = mandat.offene_pflichten()
    faellig = {p["monat"] for p in pflichten["monatsberichte"]}
    geschuldet = set(berichtsmonate(mandat.angetreten, mandat.beendet, timezone.localdate()))
    if monat is None or monat not in geschuldet:
        messages.error(request, _("Bitte einen fälligen Monat wählen."))
        return
    if not text:
        messages.error(request, _("Der Bericht braucht einen Text."))
        return
    bericht = Bericht.objects.create(
        mandat=mandat, art=Berichtsart.MONATSBERICHT, monat=monat, text=text[:BERICHT_MAX]
    )
    AuditEintrag.anhaengen(
        {"typ": "mandatsbericht", "mandat": mandat.pk, "bericht": bericht.pk, "art": Berichtsart.MONATSBERICHT.value}
    )
    if monat in faellig:
        messages.success(request, _("Monatsbericht eingereicht."))
    else:
        messages.success(request, _("Nachtrag zum Monatsbericht eingereicht."))


def _sammelbericht_anlegen(request, mandat: Mandat) -> None:
    aufgabe = _eigener_sitzungstag(mandat, request.POST.get("aufgabe", ""))
    text = (request.POST.get("text") or "").strip()
    if aufgabe is None:
        messages.error(request, _("Bitte einen vergangenen Sitzungstag wählen."))
        return
    if not text:
        messages.error(request, _("Der Bericht braucht einen Text."))
        return
    bericht = Bericht.objects.create(
        mandat=mandat, art=Berichtsart.SAMMELBERICHT, aufgabe=aufgabe, text=text[:BERICHT_MAX]
    )
    AuditEintrag.anhaengen(
        {"typ": "mandatsbericht", "mandat": mandat.pk, "bericht": bericht.pk, "art": Berichtsart.SAMMELBERICHT.value}
    )
    messages.success(request, _("Sammelbericht eingereicht."))


def _rechenschaft_anlegen(request, mandat: Mandat) -> bool:
    """Rechenschaft eintragen; False bei einem Eingabefehler (der Bereich rendert dann neu)."""
    aufgabe = _eigener_sitzungstag(mandat, request.POST.get("aufgabe", ""))
    gegenstand = (request.POST.get("gegenstand") or "").strip()[:GEGENSTAND_MAX]
    begruendung = (request.POST.get("begruendung") or "").strip()[:BEGRUENDUNG_MAX]
    stimme = request.POST.get("stimme", "")
    if aufgabe is not None:
        sitzung_am = aufgabe.sitzungstag_datum  # der angekündigte Tag, nicht frei wählbar
        gegenstand = gegenstand or aufgabe.titel[:GEGENSTAND_MAX]
    else:
        try:
            sitzung_am = date.fromisoformat((request.POST.get("sitzung_am") or "").strip())
        except ValueError:
            messages.error(request, _("Bitte den Sitzungstag angeben."))
            return False
        if sitzung_am > timezone.localdate():
            # Rechenschaft gibt es nur über eine Abstimmung, die stattgefunden hat (§ 7 Abs 5) —
            # und ein ferner Tag ließe die Fristrechnung des Registers überlaufen.
            messages.error(request, _("Der Sitzungstag darf nicht in der Zukunft liegen."))
            return False
    if not gegenstand or not begruendung or stimme not in Stimmverhalten.values:
        messages.error(request, _("Bitte Gegenstand, Stimme und Begründung angeben."))
        return False
    antrag = None
    beschluss = Beschluss.KEINER
    if aufgabe is not None and aufgabe.antrag_id:
        # Der Antragsbezug bleibt immer erhalten — der Beschluss der Plattform wird beim Speichern
        # abgeleitet und im Register live aus dem Antrag gelesen, auch wenn die Abstimmung erst
        # nach dem Eintrag endet. Ein von Hand gewählter Beschluss wäre erfunden.
        aufgabe.antrag.fortschreiben()
        antrag = aufgabe.antrag
        if antrag.phase == Phase.ABSTIMMUNG.value:
            messages.info(request, _("Die Abstimmung läuft noch — der Eintrag steht ohne Beschluss der Plattform."))
    elif request.POST.get("beschluss_plattform") in Beschluss.values:
        beschluss = request.POST.get("beschluss_plattform")  # frei oder ohne Antrag: Angabe des Mandatars
    eintrag = Rechenschaft.objects.create(
        mandat=mandat,
        aufgabe=aufgabe,
        antrag=antrag,
        gegenstand=gegenstand,
        sitzung_am=sitzung_am,
        beschluss_plattform=beschluss,
        stimme=stimme,
        begruendung=begruendung,
    )
    ereignis = {"typ": "rechenschaft", "mandat": mandat.pk, "rechenschaft": eintrag.pk}
    if aufgabe is not None:
        ereignis["aufgabe"] = aufgabe.pk
    if antrag is not None:
        ereignis["antrag"] = antrag.pk
    AuditEintrag.anhaengen(ereignis)
    messages.success(request, _("Rechenschaft eingetragen."))
    return True


# ── Verwaltung ────────────────────────────────────────────────────────────────────────────


class MandatFormular(forms.Form):
    mitglied = forms.ModelChoiceField(
        queryset=Mitglied.objects.filter(is_active=True, status=Mitgliedsstatus.AKTIV).order_by(
            "last_name", "first_name", "username"
        ),
        label=gettext_lazy("Mitglied"),
    )
    bezeichnung = forms.CharField(label=gettext_lazy("Mandat"), max_length=120)
    kandidatur = forms.ModelChoiceField(
        queryset=Antrag.objects.filter(art=Antragsart.MANDAT).order_by("-eingebracht_am"),
        required=False,
        label=gettext_lazy("Kandidatur-Antrag"),
        help_text=gettext_lazy("Ebene und Gebiet werden aus der Kandidatur übernommen, wenn sie hier leer bleiben."),
    )
    ebene = forms.ChoiceField(label=gettext_lazy("Ebene"), choices=[], required=False)
    gebiet = forms.CharField(label=gettext_lazy("Gebiet"), max_length=120, required=False)
    angetreten = forms.DateField(label=gettext_lazy("Angetreten am"), initial=timezone.localdate)
    vorstellung = forms.CharField(
        label=gettext_lazy("Vorstellung (öffentlich)"), widget=forms.Textarea(attrs={"rows": 3}), required=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ebene"].choices = [("", gettext_lazy("— aus der Kandidatur —")), *Ebene.choices]

    def clean(self):
        d = super().clean()
        kandidatur = d.get("kandidatur")
        if kandidatur is not None:
            d["ebene"] = d.get("ebene") or kandidatur.ebene
            d["gebiet"] = d.get("gebiet") or kandidatur.gebiet  # exakt wie der Antrag — das Regionsband vergleicht Text
        if not d.get("ebene"):
            self.add_error("ebene", gettext_lazy("Bitte eine Ebene wählen oder eine Kandidatur verknüpfen."))
        return d


@nur_admins
def verwaltung(request):
    form = MandatFormular()
    mandate = Mandat.objects.select_related("mitglied", "kandidatur").prefetch_related("aufgaben")
    return render(request, "mandatare/verwaltung.html", {"form": form, "mandate": mandate})


def _im_integritaetsrat(mitglied) -> bool:
    from gremien.models import Gremium, Rolle

    return Rolle.hat(mitglied, Gremium.INTEGRITAETSRAT)


@nur_admins
@require_POST
def verwaltung_aktion(request):
    """Eine Verwaltungsseite, mehrere kleine Handlungen — jede auditiert."""
    aktion = request.POST.get("aktion", "")

    if aktion == "anlegen":
        form = MandatFormular(request.POST)
        if not form.is_valid():
            messages.error(request, _("Bitte alle Pflichtfelder prüfen."))
            return redirect("mandatare:verwaltung")
        d = form.cleaned_data
        if _im_integritaetsrat(d["mitglied"]):
            # § 6 Abs 3 lit a: Mitglieder des Integritätsrats üben kein Mandat für die DDÖ aus.
            messages.error(
                request,
                _("Unvereinbar: Dieses Mitglied sitzt im Integritätsrat (§ 6 Abs 3 lit a) — kein Mandat möglich."),
            )
            return redirect("mandatare:verwaltung")
        mandat = Mandat.objects.create(
            mitglied=d["mitglied"],
            bezeichnung=d["bezeichnung"],
            ebene=d["ebene"],
            gebiet=d["gebiet"],
            angetreten=d["angetreten"],
            vorstellung=d["vorstellung"],
            kandidatur=d["kandidatur"],
        )
        ereignis = {"typ": "mandat_angelegt", "mandat": mandat.pk, "bezeichnung": mandat.bezeichnung}
        if mandat.kandidatur_id:
            ereignis["kandidatur"] = mandat.kandidatur_id
        AuditEintrag.anhaengen(ereignis)
        messages.success(
            request, _("Mandat „%(bezeichnung)s“ angelegt — öffentlich sichtbar.") % {"bezeichnung": mandat.bezeichnung}
        )

    elif aktion == "beenden":
        mandat = get_object_or_404(Mandat, pk=request.POST.get("mandat"))
        mandat.beendet = timezone.localdate()
        mandat.save(update_fields=["beendet"])
        AuditEintrag.anhaengen({"typ": "mandat_beendet", "mandat": mandat.pk})
        messages.info(
            request,
            _("Mandat „%(bezeichnung)s“ als beendet vermerkt — bleibt dokumentiert.")
            % {"bezeichnung": mandat.bezeichnung},
        )

    elif aktion == "foto":
        mandat = get_object_or_404(Mandat, pk=request.POST.get("mandat"))
        datei = request.FILES.get("foto")
        if datei is None or datei.size > FOTO_HOECHSTGROESSE:
            messages.error(request, _("Bitte ein Bild bis 800 kB wählen (JPEG, PNG oder WebP)."))
            return redirect("mandatare:verwaltung")
        daten = datei.read()
        typ = foto_typ_erkennen(daten)
        if typ is None:
            messages.error(request, _("Dateityp nicht erkannt — erlaubt sind JPEG, PNG und WebP."))
            return redirect("mandatare:verwaltung")
        mandat.foto = daten
        mandat.foto_typ = typ
        mandat.save(update_fields=["foto", "foto_typ"])
        AuditEintrag.anhaengen({"typ": "mandat_foto", "mandat": mandat.pk, "durch": "verwaltung"})
        messages.success(request, _("Foto gespeichert."))

    elif aktion == "aufgabe":
        mandat = get_object_or_404(Mandat, pk=request.POST.get("mandat"))
        titel = (request.POST.get("titel") or "").strip()
        if not titel:
            messages.error(request, _("Die Aufgabe braucht einen Titel."))
            return redirect("mandatare:verwaltung")
        antrag = None
        antrag_pk = (request.POST.get("antrag") or "").strip()
        if antrag_pk.isdigit():
            antrag = Antrag.objects.filter(pk=int(antrag_pk)).first()
        frist = None
        if (request.POST.get("frist") or "").strip():
            # Die Verwaltung nimmt weiterhin ein reines Datum an (dann 23:59 Ortszeit);
            # eine Uhrzeit ist seit 0.46 möglich (Aufgabe.frist ist ein Zeitpunkt).
            try:
                frist = _frist_aus_eingabe(request.POST["frist"], request.POST.get("frist_zeit", ""))
            except ValueError:
                messages.error(request, _("Bitte ein gültiges Datum (und gegebenenfalls eine Uhrzeit) angeben."))
                return redirect("mandatare:verwaltung")
        aufgabe = Aufgabe.objects.create(
            mandat=mandat,
            titel=titel[:200],
            beschreibung=(request.POST.get("beschreibung") or "")[:4000],
            frist=frist,
            sitzungstag=request.POST.get("sitzungstag") == "on" and frist is not None,
            antrag=antrag,
        )
        AuditEintrag.anhaengen({"typ": "mandats_aufgabe", "mandat": mandat.pk, "aufgabe": aufgabe.pk})
        messages.success(request, _("Aufgabe „%(titel)s“ veröffentlicht.") % {"titel": aufgabe.titel})

    elif aktion == "aufgabe_status":
        aufgabe = get_object_or_404(Aufgabe, pk=request.POST.get("aufgabe"))
        status = request.POST.get("status", "")
        if status in Aufgabenstatus.values:
            aufgabe.status = status
            aufgabe.save(update_fields=["status", "aktualisiert_am"])
            AuditEintrag.anhaengen(
                {"typ": "mandats_aufgabe_status", "mandat": aufgabe.mandat_id, "aufgabe": aufgabe.pk, "durch": "verwaltung"}
            )
            messages.success(
                request, _("„%(titel)s“: %(status)s.") % {"titel": aufgabe.titel, "status": aufgabe.get_status_display()}
            )

    return redirect("mandatare:verwaltung")
