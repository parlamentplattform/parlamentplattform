"""Der Sitzungsmodus in den Ansichten (FB-L5, S10b; D-L5a: Ticker und Live-Beschlusslage, Stream nur als Link).

Öffentlich: `/mandatare/<id>/live/` — Ticker, Tagesordnung mit Beschlusslage, Link auf den amtlichen
Stream und der Chat der Sitzung; `/live/` — laufende Sitzungen aller Mandatsträger und die Protokolle
der letzten sieben Tage. Solange eine Sitzung läuft, lädt die Seite im Takt des Registerwerts
`live-takt-sekunden` nach: mit htmx nur der Stand, ohne JavaScript die ganze Seite (`<noscript>` mit
`meta refresh`). Wer ohne JavaScript schreibt, bekommt die Seite ohne Neuladen (`?schreiben=1`), damit
kein Text verloren geht.

Im Bereich des Mandatars (`/mandatare/mein/`) laufen die Handlungen über `mein_aktion`
(`sitzung_aktion`); die Karte „Sitzung“ baut `sitzung_karte`. Die Fachoperationen stehen in
`mandatare.sitzung`, die Rechenregeln in `plattform_core.sitzung`."""

from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy
from django.views.decorators.http import require_POST

from mandatare.models import (
    Aufgabe,
    Livemeldung,
    Mandat,
    Rechenschaft,
    Sitzung,
    Stimmverhalten,
    Tagesordnungspunkt,
    live_takt,
)
from mandatare.sitzung import (
    SitzungFehler,
    darf_live_melden,
    meldung_abgeben,
    punkt_anhaengen,
    punkt_verknuepfen,
    sitzung_beenden,
    sitzung_beginnen,
    stream_setzen,
)
from plattform_core import Phase
from plattform_core.rechenschaft import RECHENSCHAFT_TAGE
from plattform_core.sitzung import (
    LAGE_ABGELEHNT,
    LAGE_ABSTIMMUNG,
    LAGE_ANGENOMMEN,
    LAGE_KEIN_ANTRAG,
    LAGE_OHNE_BESCHLUSS,
    LAGE_VORHER,
    Meldung,
    berichtigte,
    beschlusslage,
    massgebliche_meldungen,
)
from verfahren.models import Antrag, AuditEintrag, Kommentar
from verfahren.models import Meldung as BeitragsMeldung

LAGE_NAMEN = {
    LAGE_ANGENOMMEN: gettext_lazy("angenommen"),
    LAGE_ABGELEHNT: gettext_lazy("abgelehnt"),
    LAGE_ABSTIMMUNG: gettext_lazy("in Abstimmung"),
    LAGE_VORHER: gettext_lazy("noch nicht in Abstimmung"),
    LAGE_OHNE_BESCHLUSS: gettext_lazy("ohne Beschluss beendet"),
    LAGE_KEIN_ANTRAG: gettext_lazy("kein Beschluss der Plattform"),
}


def _lage_name(status: str) -> str:
    return str(LAGE_NAMEN[status])


def _antrag_aus_eingabe(roh: str) -> tuple[Antrag | None, bool]:
    """Die Antragsnummer aus einem Formularfeld: (Antrag, ob etwas eingegeben war). Kandidaturen und
    Vertrauensfragen sind keine Beschlusslage zu einem Tagesordnungspunkt."""
    roh = (roh or "").strip().lstrip("#")
    if not roh:
        return None, False
    if not roh.isdigit():
        return None, True
    antrag = Antrag.objects.filter(pk=int(roh)).exclude(art__in=["mandat", "vertrauensfrage"]).first()
    return antrag, True


def punkt_zeilen(sitzung: Sitzung) -> list[dict]:
    """Die Tagesordnung mit Beschlusslage, maßgeblicher Meldung und — falls schon eingetragen — der
    Rechenschaft je Punkt. Verknüpfte Anträge werden vorher fortgeschrieben (lazy Phasen)."""
    from verfahren.views import _frist_fuer

    punkte = list(sitzung.punkte.select_related("antrag").order_by("nummer"))
    meldungen = list(sitzung.meldungen.all())
    massgeblich = massgebliche_meldungen(
        Meldung(m.pk, m.punkt_id, m.zeitpunkt, m.stimme, m.abgestimmt, m.berichtigt_id) for m in meldungen
    )
    nach_pk = {m.pk: m for m in meldungen}
    rechenschaft = {r.punkt_id: r for r in Rechenschaft.objects.filter(punkt__in=punkte)}
    zeilen = []
    for p in punkte:
        antrag = p.antrag
        bis = None
        if antrag is not None:
            antrag.fortschreiben()
            if antrag.phase == Phase.ABSTIMMUNG.value:
                bis = _frist_fuer(antrag)
        lage = beschlusslage(antrag.phase if antrag is not None else None, bis)
        m = massgeblich.get(p.pk)
        zeilen.append(
            {
                "punkt": p,
                "lage": lage,
                "lage_name": _lage_name(lage.status),
                "massgeblich": nach_pk[m.pk] if m is not None else None,
                "rechenschaft": rechenschaft.get(p.pk),
            }
        )
    return zeilen


def ticker(sitzung: Sitzung) -> list[dict]:
    """Die Meldungen der Sitzung, neueste zuerst; berichtigte tragen das Band, jede ihren Anker."""
    meldungen = list(sitzung.meldungen.select_related("punkt").order_by("-zeitpunkt", "-pk"))
    weg = berichtigte(Meldung(m.pk, m.punkt_id, m.zeitpunkt, berichtigt=m.berichtigt_id) for m in meldungen)
    return [{"m": m, "berichtigt": m.pk in weg} for m in meldungen]


def _sitzungen_fortschreiben(qs) -> None:
    for s in qs.filter(ende__isnull=True):
        s.fortschreiben()


# ── Öffentlich ────────────────────────────────────────────────────────────────────────────


def _live_kontext(request, mandat: Mandat, sitzung: Sitzung | None, fehler: str = "", entwurf: dict | None = None):
    from verfahren.chat import sitzung_faden, sitzung_gelesen_merken

    kontext = {
        "mandat": mandat,
        "sitzung": sitzung,
        "takt": live_takt(),
        "fehler": fehler,
        "entwurf": entwurf or {},
        "schreiben": request.GET.get("schreiben") == "1" or bool(fehler),
        "meldegruende": BeitragsMeldung.Grund.choices,
        "protokolle": list(mandat.sitzungen.select_related("aufgabe").order_by("-beginn")),
    }
    if sitzung is None:
        return kontext
    laeuft = sitzung.laeuft()
    ist_mandatar = request.user.is_authenticated and request.user.pk == mandat.mitglied_id
    faden = sitzung_faden(sitzung, request.user)
    sitzung_gelesen_merken(sitzung, request.user)
    kontext.update(
        {
            "laeuft": laeuft,
            "punkte": punkt_zeilen(sitzung),
            "ticker": ticker(sitzung),
            "faden": faden,
            "chat_offen": laeuft,
            "ist_mandatar": ist_mandatar,
            "darf_beantworten": ist_mandatar and darf_live_melden(mandat),
            "antwort_auf": _antwort_vorgabe(sitzung, request.GET.get("antwort_auf") or (entwurf or {}).get("antwort_auf")),
        }
    )
    return kontext


def _antwort_vorgabe(sitzung: Sitzung, roh) -> Kommentar | None:
    if not (roh and str(roh).isdigit()):
        return None
    return (
        Kommentar.objects.filter(pk=int(roh), sitzung=sitzung, geloescht=False, ausgeblendet_am__isnull=True)
        .select_related("mitglied")
        .first()
    )


def live(request, pk: int):
    """Die öffentliche Live-Seite eines Mandatars (FB-L5 B): die laufende Sitzung, sonst die jüngste —
    oder mit `?sitzung=<id>` das Protokoll einer bestimmten."""
    mandat = get_object_or_404(Mandat.objects.select_related("mitglied"), pk=pk)
    _sitzungen_fortschreiben(mandat.sitzungen.all())
    sitzung = None
    wahl = (request.GET.get("sitzung") or "").strip()
    if wahl:
        if not wahl.isdigit():
            return redirect("mandatare:live", pk=mandat.pk)
        sitzung = get_object_or_404(Sitzung, pk=int(wahl), mandat=mandat)
    else:
        sitzung = mandat.sitzungen.filter(ende__isnull=True).order_by("-beginn").first() or mandat.sitzungen.order_by(
            "-beginn"
        ).first()
    return render(request, "mandatare/live.html", _live_kontext(request, mandat, sitzung))


def live_uebersicht(request):
    """Alle laufenden Sitzungen der DDÖ-Mandatsträger und die Protokolle der letzten sieben Tage — so lange
    läuft die Frist der Rechenschaft dazu (§ 7 Abs 5). Reihung: Beginn, jüngste zuerst; nichts anderes."""
    _sitzungen_fortschreiben(Sitzung.objects.all())
    grenze = timezone.now() - timedelta(days=RECHENSCHAFT_TAGE)
    alle = list(
        Sitzung.objects.select_related("mandat__mitglied", "aufgabe")
        .filter(ende__isnull=True)
        .order_by("-beginn")
    ) + list(
        Sitzung.objects.select_related("mandat__mitglied", "aufgabe")
        .filter(ende__isnull=False, ende__gte=grenze)
        .order_by("-beginn")
    )
    return render(
        request,
        "mandatare/live_uebersicht.html",
        {"laufende": [s for s in alle if s.ende is None], "beendete": [s for s in alle if s.ende is not None]},
    )


def laufende_in_region(orte_je_ebene: dict[str, list[str]]) -> dict[str, list[Sitzung]]:
    """Für die Kachel „Live“ in „Meine Region“: laufende Sitzungen je Ebene (Gemeinde, Bezirk, Land) von
    Mandaten, deren Gebiet einer der eigenen Orte ist — ohne Orte alle der Ebene, wie bei den Anträgen.
    Reihung nach Beginn, jüngste zuerst; keine Hervorhebung (die bleibt beim Integritätsrat)."""
    _sitzungen_fortschreiben(Sitzung.objects.all())
    laufende = list(
        Sitzung.objects.filter(ende__isnull=True).select_related("mandat__mitglied").order_by("-beginn")
    )
    ergebnis: dict[str, list[Sitzung]] = {}
    for ebene, orte in orte_je_ebene.items():
        ergebnis[ebene] = [s for s in laufende if s.mandat.ebene == ebene and (not orte or s.mandat.gebiet in orte)]
    return ergebnis


# ── Der Chat der Sitzung ──────────────────────────────────────────────────────────────────


def _live_ziel(mandat: Mandat, sitzung: Sitzung, anker: str = "") -> str:
    ziel = f"{reverse('mandatare:live', kwargs={'pk': mandat.pk})}?sitzung={sitzung.pk}"
    return f"{ziel}#{anker}" if anker else ziel


def _sitzung_des_mandats(pk: int, sitzung_pk: int) -> tuple[Mandat, Sitzung]:
    mandat = get_object_or_404(Mandat.objects.select_related("mitglied"), pk=pk)
    sitzung = get_object_or_404(Sitzung, pk=sitzung_pk, mandat=mandat)
    sitzung.fortschreiben()
    return mandat, sitzung


@login_required
@require_POST
def live_beitrag(request, pk: int, sitzung_pk: int):
    """Einen Beitrag in den Chat der Sitzung schreiben — Mitglieder mit Mitwirkungsrecht, solange die
    Sitzung läuft (E1). Bei einem Fehler kommt die Seite mit Meldung und Entwurf zurück, nichts geht verloren."""
    from verfahren.chat import ChatGesperrt, sitzung_beitrag_schreiben
    from verfahren.views_aktionen import _mitwirkung_gesperrt

    mandat, sitzung = _sitzung_des_mandats(pk, sitzung_pk)
    gesperrt = _mitwirkung_gesperrt(request)
    if gesperrt is not None:
        return gesperrt
    entwurf = {"text": (request.POST.get("text") or "")[:4000], "antwort_auf": request.POST.get("antwort_auf") or ""}
    antwort_auf = None
    if entwurf["antwort_auf"]:
        antwort_auf = _antwort_vorgabe(sitzung, entwurf["antwort_auf"])
        if antwort_auf is None:
            entwurf["antwort_auf"] = ""
            return render(
                request, "mandatare/live.html",
                _live_kontext(request, mandat, sitzung, _("Der Beitrag, auf den Sie antworten wollten, gibt es hier nicht."), entwurf),
            )
    try:
        beitrag = sitzung_beitrag_schreiben(sitzung, request.user, entwurf["text"], antwort_auf)
    except (ChatGesperrt, ValueError) as fehler:
        return render(request, "mandatare/live.html", _live_kontext(request, mandat, sitzung, str(fehler), entwurf))
    return redirect(_live_ziel(mandat, sitzung, f"k-{beitrag.pk}"))


@login_required
@require_POST
def live_beitrag_aktion(request, pk: int, sitzung_pk: int, beitrag_pk: int):
    """Handlungen an einem Beitrag im Chat der Sitzung: zurückziehen (Verfasser), melden (Mitglieder,
    Art 16 DSA), als beantwortet markieren (der Mandatar dieser Sitzung)."""
    from verfahren.chat import als_beantwortet_markieren
    from verfahren.views_aktionen import _mitwirkung_gesperrt

    mandat, sitzung = _sitzung_des_mandats(pk, sitzung_pk)
    beitrag = get_object_or_404(Kommentar, pk=beitrag_pk, sitzung=sitzung)
    aktion = request.POST.get("aktion", "")
    anker = f"k-{beitrag.pk}"
    if aktion == "entfernen":
        if beitrag.mitglied_id != request.user.pk:
            return render(request, "mandatare/kein_zugang.html", status=403)
        if not beitrag.geloescht:
            beitrag.geloescht = True
            beitrag.save(update_fields=["geloescht"])
    elif aktion == "melden":
        grund = request.POST.get("grund", "")
        if grund not in BeitragsMeldung.Grund.values:
            messages.error(request, _("Bitte einen Grund wählen."))
            return redirect(_live_ziel(mandat, sitzung, anker))
        _meldung, neu = BeitragsMeldung.objects.get_or_create(
            kommentar=beitrag,
            mitglied=request.user,
            defaults={"grund": grund, "erlaeuterung": (request.POST.get("erlaeuterung") or "").strip()[:500]},
        )
        if neu:
            AuditEintrag.anhaengen({"typ": "beitrag_gemeldet", "sitzung": sitzung.pk, "beitrag": beitrag.pk, "grund": grund})
        messages.success(request, _("Danke — die Meldung liegt der Verwaltung vor."))
    elif aktion == "beantwortet":
        if request.user.pk != mandat.mitglied_id or not darf_live_melden(mandat):
            return render(request, "mandatare/kein_zugang.html", status=403)
        gesperrt = _mitwirkung_gesperrt(request)
        if gesperrt is not None:
            return gesperrt
        als_beantwortet_markieren(beitrag)
    else:
        messages.error(request, _("Unbekannte Handlung."))
    return redirect(_live_ziel(mandat, sitzung, anker))


# ── Im Bereich des Mandatars ──────────────────────────────────────────────────────────────


def sitzung_karte(mandat: Mandat) -> dict:
    """Was die Karte „Sitzung“ im Bereich braucht: die laufende Sitzung mit Tagesordnung, Beschlusslage,
    Ticker und offenen Fragen — oder die heutigen Sitzungstage, für die der Live-Modus eingeschaltet
    werden kann — und die beendeten Sitzungen, deren Rechenschaft noch läuft (Punkte mit Knopf)."""
    _sitzungen_fortschreiben(mandat.sitzungen.all())
    heute = timezone.localdate()
    laufend = mandat.sitzungen.filter(ende__isnull=True).select_related("aufgabe").order_by("-beginn").first()
    karte: dict = {"laufend": laufend, "stimmen": Stimmverhalten.choices}
    if laufend is not None:
        karte["punkte"] = punkt_zeilen(laufend)
        karte["ticker"] = ticker(laufend)
        karte["fragen"] = list(
            laufend.beitraege.filter(
                antwort_auf__isnull=True, beantwortet_am__isnull=True, geloescht=False, ausgeblendet_am__isnull=True
            )
            .select_related("mitglied")
            .order_by("erstellt_am")
        )
    else:
        karte["heutige"] = [
            a
            for a in mandat.aufgaben.filter(sitzungstag=True, frist__isnull=False, sitzung__isnull=True)
            if a.sitzungstag_datum == heute
        ]
    grenze = heute - timedelta(days=RECHENSCHAFT_TAGE)
    karte["beendete"] = [
        {"sitzung": s, "punkte": punkt_zeilen(s)}
        for s in mandat.sitzungen.filter(ende__isnull=False).select_related("aufgabe").order_by("-beginn")
        if s.tag >= grenze
    ]
    return karte


def _eigener_punkt(mandat: Mandat, roh: str) -> Tagesordnungspunkt | None:
    if not (roh or "").isdigit():
        return None
    return Tagesordnungspunkt.objects.filter(pk=int(roh), sitzung__mandat=mandat).select_related("sitzung").first()


def sitzung_aktion(request, mandat: Mandat, aktion: str) -> None:
    """Die Handlungen der Karte „Sitzung“ — Besitz und Mitwirkung hat `mein_aktion` schon geprüft; die
    Fachoperation prüft Mandat, Befugnis und Lauf der Sitzung. Ein Fehler geht als Meldung zurück."""
    post = request.POST
    laufend = mandat.sitzungen.filter(ende__isnull=True).order_by("-beginn").first()
    try:
        if aktion == "sitzung_beginnen":
            roh = (post.get("aufgabe") or "").strip()
            aufgabe = Aufgabe.objects.filter(pk=int(roh), mandat=mandat).first() if roh.isdigit() else None
            if aufgabe is None:
                raise SitzungFehler(_("Bitte den Sitzungstag wählen."))
            punkte = (post.get("tagesordnung") or "").splitlines()
            sitzung_beginnen(mandat, aufgabe, post.get("stream", ""), punkte)
            messages.success(request, _("Live-Modus eingeschaltet — die Live-Seite ist öffentlich."))
            return
        if laufend is None:
            raise SitzungFehler(_("Es läuft keine Sitzung."))
        if aktion == "sitzung_meldung":
            punkt = _eigener_punkt(mandat, post.get("punkt", ""))
            if punkt is not None and punkt.sitzung_id != laufend.pk:
                punkt = None
            berichtigt = None
            roh = (post.get("berichtigt") or "").strip()
            if roh.isdigit():
                berichtigt = Livemeldung.objects.filter(pk=int(roh), sitzung=laufend).first()
            meldung_abgeben(
                laufend, post.get("text", ""), punkt, post.get("stimme", ""), post.get("abgestimmt") == "on", berichtigt
            )
            messages.success(request, _("Gemeldet."))
        elif aktion == "sitzung_punkt":
            antrag, eingegeben = _antrag_aus_eingabe(post.get("antrag", ""))
            if eingegeben and antrag is None:
                raise SitzungFehler(_("Diese Antragsnummer gibt es nicht — oder sie ist keine Sach- oder Mandatsfrage."))
            punkt_anhaengen(laufend, post.get("titel", ""), antrag)
            messages.success(request, _("Punkt angehängt."))
        elif aktion == "sitzung_verknuepfen":
            punkt = _eigener_punkt(mandat, post.get("punkt", ""))
            antrag, _eingegeben = _antrag_aus_eingabe(post.get("antrag", ""))
            if punkt is None or antrag is None:
                raise SitzungFehler(_("Diese Antragsnummer gibt es nicht — oder sie ist keine Sach- oder Mandatsfrage."))
            punkt_verknuepfen(punkt, antrag)
            messages.success(request, _("Antrag verknüpft."))
        elif aktion == "sitzung_stream":
            stream_setzen(laufend, post.get("stream", ""))
            messages.success(request, _("Stream-Link gespeichert."))
        elif aktion == "sitzung_beenden":
            sitzung_beenden(laufend)
            messages.success(request, _("Sitzung beendet — die Live-Seite ist jetzt ihr Protokoll."))
        else:
            messages.error(request, _("Unbekannte Handlung."))
    except SitzungFehler as fehler:
        messages.error(request, str(fehler))


def rechenschaft_vorbefuellung(mandat: Mandat, roh: str) -> dict | None:
    """`?punkt=<id>` im Bereich: das Rechenschaftsformular aus dem Ticker vorbefüllen (FB-L5, § 7 Abs 5) —
    Gegenstand aus dem Punkt, Stimme und Begründung aus der maßgeblichen Meldung. Eingetragen wird erst
    mit dem Absenden; die Plattform trägt nichts selbst ein."""
    punkt = _eigener_punkt(mandat, roh)
    if punkt is None:
        return None
    zeile = next((z for z in punkt_zeilen(punkt.sitzung) if z["punkt"].pk == punkt.pk), None)
    if zeile is None or zeile["rechenschaft"] is not None:
        return None
    m = zeile["massgeblich"]
    return {
        "punkt": punkt,
        "gegenstand": punkt.titel,
        "stimme": m.stimme if m is not None else "",
        "begruendung": m.text if m is not None else "",
        "aufgabe": punkt.sitzung.aufgabe_id,
    }


def sammelbericht_vorlage(aufgabe: Aufgabe) -> str:
    """Der Sammelbericht aus dem Ticker vorbefüllt (§ 7 Abs 3 lit b): je Punkt Titel, Beschlusslage der
    Plattform und die maßgebliche Meldung. Der Mandatar ergänzt und reicht ein; nichts geht von selbst."""
    sitzung = Sitzung.objects.filter(aufgabe=aufgabe).first()
    if sitzung is None:
        return ""
    zeilen = []
    for z in punkt_zeilen(sitzung):
        p = z["punkt"]
        zeile = _("Punkt %(n)d · %(titel)s — Beschluss der Plattform: %(lage)s") % {
            "n": p.nummer, "titel": p.titel, "lage": z["lage_name"],
        }
        m = z["massgeblich"]
        if m is not None:
            wort = _("abgestimmt") if m.abgestimmt else _("angekündigt")
            zeile += " — " + _("meine Stimme: %(stimme)s (%(wort)s)") % {"stimme": m.get_stimme_display(), "wort": wort}
        zeilen.append(zeile)
    return "\n".join(zeilen)
