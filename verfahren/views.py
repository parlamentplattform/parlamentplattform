"""Lesende Ansichten. Grundsatz F-31: Sortierung ausschließlich nach Frist und
Phase — niemals nach Beliebtheit. Ergebnisseiten sind ohne Login lesbar (F-20)."""

import json

from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from plattform_core import Phase
from plattform_core.phases import (
    abstimmung_frist_ende,
    beratung_frist_ende,
    unterstuetzung_frist_ende,
)
from verfahren.models import (
    Antrag,
    Antragsart,
    BewerbungsZustimmung,
    Kategorie,
    Stimmabgabe,
    StimmRegister,
    Vollzugsstatus,
)

LAUFEND = [Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value]

# Die acht offenen Regler des WeicherFilters (P5) mit ihren Anzeigenamen.
REGLER_NAMEN = {
    "gestimmt": gettext_lazy("Mehr, wo ich schon abgestimmt habe"),
    "unterstuetzt": gettext_lazy("Mehr, wo ich unterstützt habe"),
    "entdeckungen": gettext_lazy("Entdeckungen außerhalb meiner Favoriten"),
    "unterstuetzungsphase": gettext_lazy("Mehr Unterstützungsphase"),
    "abstimmungen": gettext_lazy("Mehr laufende Abstimmungen"),
    "chronologisch": gettext_lazy("Neues zuerst"),
    "ablaufend": gettext_lazy("Bald ablaufende zuerst"),
    "schwelle": gettext_lazy("Knapp vor der Schwelle zuerst"),
}


def _weicherfilter_reihen(nutzer, laufend, jetzt, regler, abo_ids):
    """P5: Merkmale (0..1) je laufendem Antrag bauen und im offenen Kern reihen.

    Grundordnung der Eingabe = die neutrale Ordnung (Abstimmung, Beratung,
    Unterstützung; innerhalb der Phase nach Fristnähe) — bei Punktgleichheit
    bleibt sie erhalten. Die Merkmale sind absichtlich einfach und offen:
    Kategorien-Überschneidung mit dem eigenen Stimm-/Unterstützungs-Verlauf,
    Phasen-Zugehörigkeit, Alters-Rang, Fristnähe (60-Tage-Horizont),
    Schwellen-Fortschritt."""
    from plattform_core.weicherfilter import reihen

    phasen_rang = {Phase.ABSTIMMUNG.value: 0, Phase.BERATUNG.value: 1, Phase.UNTERSTUETZUNG.value: 2}
    antraege = sorted(
        laufend.prefetch_related("kategorien"),
        key=lambda a: (phasen_rang.get(a.phase, 9), a.phase_beginn),
    )
    if not antraege:
        return []
    kats = {a.pk: {k.pk for k in a.kategorien.all()} for a in antraege}
    gestimmt_kats = set(
        Kategorie.objects.filter(antraege__stimmregister__mitglied=nutzer).values_list("pk", flat=True)
    )
    unterstuetzt_kats = set(
        Kategorie.objects.filter(antraege__unterstuetzungen__mitglied=nutzer).values_list("pk", flat=True)
    )
    nach_alter = sorted(antraege, key=lambda a: a.eingebracht_am)
    chrono = {
        a.pk: (i / (len(nach_alter) - 1) if len(nach_alter) > 1 else 1.0)
        for i, a in enumerate(nach_alter)
    }
    eintraege = []
    for a in antraege:
        policy = a.policy()
        frist = _frist_fuer(a, policy)
        resttage = max(0, (frist - jetzt).days) if frist else 60
        eigene = kats[a.pk]
        merkmale = {
            "gestimmt": len(eigene & gestimmt_kats) / len(eigene) if eigene else 0.0,
            "unterstuetzt": len(eigene & unterstuetzt_kats) / len(eigene) if eigene else 0.0,
            "entdeckungen": 1.0 if eigene and not (eigene & abo_ids) else 0.0,
            "unterstuetzungsphase": 1.0 if a.phase == Phase.UNTERSTUETZUNG.value else 0.0,
            "abstimmungen": 1.0 if a.phase == Phase.ABSTIMMUNG.value else 0.0,
            "chronologisch": chrono[a.pk],
            "ablaufend": max(0.0, 1.0 - resttage / 60.0),
            "schwelle": 0.0,
        }
        if a.phase == Phase.UNTERSTUETZUNG.value:
            schwelle = max(1, policy.unterstuetzung_schwelle)
            merkmale["schwelle"] = min(1.0, a.unterstuetzungen.count() / schwelle)
        eintraege.append({"id": a.pk, "merkmale": merkmale})
    lage = reihen(eintraege, regler)
    je_pk = {a.pk: a for a in antraege}
    return [
        {
            "antrag": je_pk[e["id"]],
            "punkte": f"{e['punkte']:g}",
            "aufschluesselung": " · ".join(
                f"{REGLER_NAMEN[name]} {anteil:g}" for name, anteil in e["anteile"].items()
            ),
        }
        for e in lage
    ]


def _frist_fuer(antrag, policy=None):
    """Fristende der laufenden Phase — None für Endphasen."""
    policy = policy or antrag.policy()
    if antrag.phase == Phase.UNTERSTUETZUNG.value:
        return unterstuetzung_frist_ende(antrag.phase_beginn, policy)
    if antrag.phase == Phase.BERATUNG.value:
        return beratung_frist_ende(antrag.phase_beginn, policy)
    if antrag.phase == Phase.ABSTIMMUNG.value:
        return abstimmung_frist_ende(antrag.phase_beginn, policy)
    return None


def _kachel(antrag, jetzt, meine_stimmen=None):
    """Eine Kachel für P3/P4 (F-42/F-43): Frist, Resttage und der phasengerechte
    Stand. Während einer laufenden Abstimmung zeigt die Kachel NUR die
    Beteiligung — nie die Tendenz (F-15: kein Bandwagon; das Ergebnis erscheint
    nach Fristende auf der Antragsseite)."""
    policy = antrag.policy()
    frist = _frist_fuer(antrag, policy)
    resttage = max(0, (frist - jetzt).days) if frist else None
    stat = None
    if antrag.phase == Phase.UNTERSTUETZUNG.value:
        n = antrag.unterstuetzungen.count()
        schwelle = max(1, policy.unterstuetzung_schwelle)
        stat = {"typ": "unterstuetzung", "n": n, "schwelle": schwelle,
                "prozent": min(100, round(100 * n / schwelle))}
    elif antrag.phase == Phase.BERATUNG.value:
        stat = {"typ": "beratung", "beitraege": antrag.kommentare.count()}
    elif antrag.phase == Phase.ABSTIMMUNG.value:
        if antrag.art == Antragsart.MANDAT:
            abgegeben = (
                BewerbungsZustimmung.objects.filter(bewerbung__antrag=antrag)
                .values("pseudonym")
                .distinct()
                .count()
            )
        else:
            abgegeben = antrag.stimmabgaben.count()
        basis = max(1, antrag.stimmberechtigte_anzahl or 1)
        stat = {"typ": "abstimmung", "abgegeben": abgegeben,
                "prozent": min(100, round(100 * abgegeben / basis))}
    return {
        "antrag": antrag,
        "frist": frist,
        "resttage": resttage,
        "stat": stat,
        "meine_stimme": (meine_stimmen or {}).get(antrag.pk),
    }


def _meine_stimmen(nutzer, antraege):
    """Bulk: {antrag_id: eigene Sach-Stimme} für die Kachel-Markierung."""
    pks = [a.pk for a in antraege if a.phase == Phase.ABSTIMMUNG.value and a.art != Antragsart.MANDAT]
    if not (pks and nutzer.is_authenticated):
        return {}
    je_pseudonym = dict(
        StimmRegister.objects.filter(mitglied=nutzer, antrag_id__in=pks).values_list(
            "pseudonym", "antrag_id"
        )
    )
    if not je_pseudonym:
        return {}
    stimmen = {}
    for ab in Stimmabgabe.objects.filter(antrag_id__in=pks, pseudonym__in=je_pseudonym):
        stimmen[ab.antrag_id] = ab.stimme
    return stimmen


def index(request):
    """Die Willkommensseite unter „/": das Schaufenster für Gäste. Leitidee P1:
    das Parlament ist zum Benutzen da, erklärt und beworben wird gesondert —
    darum sind Willkommensseite und Parlament getrennte Seiten. Angemeldete
    Mitglieder landen ohne Umweg im Parlament."""
    if request.user.is_authenticated:
        return redirect("verfahren:parlament")
    from mitglieder.models import Mitglied

    antraege = Antrag.objects.exclude(phase=Phase.ZURUECKGEWIESEN.value)
    laufend = antraege.filter(phase__in=LAUFEND)
    buehne = {
        "mitglieder": Mitglied.objects.filter(is_active=True).count(),
        "laufend": laufend.count(),
        "beschluesse": Antrag.objects.filter(phase=Phase.ANGENOMMEN.value).count(),
    }
    wichtige = laufend.filter(hervorgehoben=True).order_by("phase_beginn")[:3]
    return render(request, "verfahren/index.html", {"buehne": buehne, "wichtige": wichtige})


def parlament(request):
    """Das Parlament in vier Bereichen (§ 5 Abs 10, F-40) — die Arbeitsansicht.
    Reihung immer nur nach Phase und Frist, nie nach Beliebtheit oder
    verdeckter Gewichtung (F-31). Ohne Login lesbar (F-20), abstimmen können
    Mitglieder."""
    antraege = Antrag.objects.exclude(phase=Phase.ZURUECKGEWIESEN.value)
    laufend = antraege.filter(phase__in=LAUFEND)

    # Der Favoriten-Fächer (P2, F-46): ?fach= schaltet den Bereich a auf den
    # grafischen Themenbaum — ohne JavaScript voll klickbar, htmx als Zugabe.
    fach = request.GET.get("fach")
    faecher = None
    if fach is not None:
        from plattform_core.faecher import faecher_layout

        zeilen = list(Kategorie.objects.filter(aktiv=True).values("id", "slug", "name", "eltern_id"))
        faecher = faecher_layout(zeilen, fokus_slug=fach or None)
        faecher["abos"] = (
            set(request.user.kategorie_abos.values_list("kategorie__slug", flat=True))
            if request.user.is_authenticated
            else set()
        )

    # Bereich a — persönliche Favoriten und abonnierte Lebensbereiche (F-41, F-46)
    favoriten_abstimmung = favoriten_sonstige = themen_neu = None
    meine_favoriten: set[int] = set()
    if request.user.is_authenticated:
        meine_favoriten = set(request.user.favoriten.values_list("antrag_id", flat=True))
        eigene = laufend.filter(id__in=meine_favoriten)
        favoriten_abstimmung = eigene.filter(phase=Phase.ABSTIMMUNG.value).order_by("phase_beginn")
        favoriten_sonstige = eigene.exclude(phase=Phase.ABSTIMMUNG.value).order_by("phase_beginn")
        # Ein Abo gilt für den ganzen Ast: Unterkategorien der abonnierten Bereiche zählen mit.
        abo_ids = set(request.user.kategorie_abos.values_list("kategorie_id", flat=True))
        kinder: dict[int | None, list[int]] = {}
        for kid, eid in Kategorie.objects.filter(aktiv=True).values_list("id", "eltern_id"):
            kinder.setdefault(eid, []).append(kid)
        rand = list(abo_ids)
        while rand:
            neue = [k for e in rand for k in kinder.get(e, []) if k not in abo_ids]
            abo_ids.update(neue)
            rand = neue
        themen_neu = (
            laufend.filter(kategorien__in=abo_ids)
            .exclude(id__in=meine_favoriten)
            .distinct()
            .order_by("phase_beginn")[:6]
        )

    jetzt = timezone.now()

    # Bereich b — vom Integritätsrat hervorgehobene Abstimmungen (F-42, nie
    # algorithmisch), als Kacheln (P3): Stern, Beteiligung, Resttage.
    wichtige = list(laufend.filter(hervorgehoben=True).order_by("phase_beginn"))

    # Bereich c — Meine Region (F-43, P4): drei Zeilen Gemeinde/Bezirk/Land.
    # Mit Wohnsitz zeigt jede Zeile die EIGENE Region; ohne (Gäste, fehlendes
    # Profil) alle regionalen Anträge der jeweiligen Ebene.
    regionale = laufend.exclude(ebene="bund").order_by("phase_beginn")
    mein_ort = {"gemeinde": "", "bezirk": "", "land": ""}
    if request.user.is_authenticated:
        mein_ort["gemeinde"] = request.user.gemeinde or ""
        mein_ort["land"] = (
            request.user.get_bundesland_display() if request.user.bundesland else ""
        )
        if request.user.wohnsitz_id:
            mein_ort["bezirk"] = request.user.wohnsitz.bezirk or ""

    meine_stimmen = _meine_stimmen(request.user, list(regionale) + wichtige)

    region_zeilen = []
    for ebene, ort in (("gemeinde", mein_ort["gemeinde"]), ("bezirk", mein_ort["bezirk"]),
                       ("land", mein_ort["land"])):
        zeile = regionale.filter(ebene=ebene)
        if ort:
            zeile = zeile.filter(gebiet=ort)
        region_zeilen.append(
            {
                "ebene": ebene,
                "ort": ort,
                "kacheln": [_kachel(a, jetzt, meine_stimmen) for a in zeile],
            }
        )

    wichtige_kacheln = [_kachel(a, jetzt, meine_stimmen) for a in wichtige]

    # Bereich d — der WeicherFilter (P5): das aktive Profil reiht die laufenden
    # Verfahren nach den offenen Reglern des Mitglieds; sonst gilt die strenge
    # Voreinstellung (Phase und Frist, chronologisch — die Gruppen unten).
    filter_lage = None
    gereiht = None
    if request.user.is_authenticated:
        from plattform_core.weicherfilter import ist_neutral, regler_bereinigen
        from verfahren.models import FilterProfil

        profile = list(request.user.filterprofile.all())
        aktives = next((p for p in profile if p.aktiv), None)
        regler = regler_bereinigen(aktives.regler if aktives else {})
        if aktives and not ist_neutral(regler):
            gereiht = _weicherfilter_reihen(request.user, laufend, jetzt, regler, abo_ids)
        filter_lage = {
            "profile": profile,
            "aktiv": aktives,
            "regler_meta": [(name, REGLER_NAMEN[name], regler[name]) for name in REGLER_NAMEN],
            "hoechstzahl": FilterProfil.HOECHSTZAHL,
        }

    # Bereich d — alle Verfahren nach Phase und Frist
    gruppen = [
        (_("Laufende Abstimmungen"), antraege.filter(phase=Phase.ABSTIMMUNG.value).order_by("phase_beginn")),
        (_("In Beratung"), antraege.filter(phase=Phase.BERATUNG.value).order_by("phase_beginn")),
        (
            _("Sammeln Unterstützung"),
            antraege.filter(phase=Phase.UNTERSTUETZUNG.value).order_by("phase_beginn"),
        ),
        (
            _("Abgeschlossen"),
            antraege.filter(
                phase__in=[Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value, Phase.VERFALLEN.value]
            ).order_by("-phase_beginn")[:20],
        ),
    ]
    return render(
        request,
        "verfahren/parlament.html",
        {
            "faecher": faecher,
            "gruppen": gruppen,
            "favoriten_abstimmung": favoriten_abstimmung,
            "favoriten_sonstige": favoriten_sonstige,
            "themen_neu": themen_neu,
            "meine_favoriten": meine_favoriten,
            "filter_lage": filter_lage,
            "gereiht": gereiht,
            "wichtige_kacheln": wichtige_kacheln,
            "region_zeilen": region_zeilen,
            "region_gefiltert": any(mein_ort.values()),
        },
    )


def antrag_detail(request, pk):
    antrag = get_object_or_404(Antrag, pk=pk)
    antrag.fortschreiben()  # fällige Übergänge lazy anwenden (idempotent; Produktion: zusätzlich Cron)
    beendet = antrag.phase in (Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value)
    ergebnis = None
    if beendet and antrag.art != Antragsart.MANDAT:
        ergebnis = antrag.auszaehlen()

    # Mandats-Kandidatur (§ 7 Abs 1, F-70): Bewerbungen, eigene Zustimmungen, Ergebnis
    kandidatur = None
    if antrag.art == Antragsart.MANDAT:
        bewerbungen = list(antrag.bewerbungen.select_related("mitglied"))
        meine_bewerbung = None
        meine_zustimmungen: set[int] = set()
        if request.user.is_authenticated:
            meine_bewerbung = next((b for b in bewerbungen if b.mitglied_id == request.user.pk), None)
            reg = antrag.stimmregister.filter(mitglied=request.user).first()
            if reg:
                meine_zustimmungen = set(
                    BewerbungsZustimmung.objects.filter(
                        bewerbung__antrag=antrag, pseudonym=reg.pseudonym
                    ).values_list("bewerbung_id", flat=True)
                )
        wahl = antrag.kandidatur_auszaehlen() if beendet else None
        ergebnis_zeilen = []
        if wahl is not None:
            namen = {b.pk: b.mitglied.anzeigename for b in bewerbungen}
            ergebnis_zeilen = [
                {
                    "platz": p.platz,
                    "name": namen.get(p.bewerbung_id, f"#{p.bewerbung_id}"),
                    "stimmen": p.stimmen,
                    "gewonnen": p.bewerbung_id == wahl.gewonnen_id,
                }
                for p in wahl.plaetze
            ]
        kandidatur = {
            "aktive": [b for b in bewerbungen if not b.zurueckgezogen],
            "zurueckgezogene": [b for b in bewerbungen if b.zurueckgezogen],
            "meine_bewerbung": meine_bewerbung,
            "meine_zustimmungen": meine_zustimmungen,
            "bewerben_offen": antrag.phase
            in (Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value),
            "zustimmen_offen": antrag.phase == Phase.ABSTIMMUNG.value,
            "wahl": wahl,
            "ergebnis_zeilen": ergebnis_zeilen,
        }
    from plattform_core.phases import (
        abstimmung_frist_ende,
        beratung_frist_ende,
        unterstuetzung_frist_ende,
    )

    policy = antrag.policy()
    frist = None
    if antrag.phase == Phase.UNTERSTUETZUNG.value:
        frist = unterstuetzung_frist_ende(antrag.phase_beginn, policy)
    elif antrag.phase == Phase.BERATUNG.value:
        frist = beratung_frist_ende(antrag.phase_beginn, policy)
    elif antrag.phase == Phase.ABSTIMMUNG.value:
        frist = abstimmung_frist_ende(antrag.phase_beginn, policy)
    unterstuetzt_von_mir = (
        request.user.is_authenticated and antrag.unterstuetzungen.filter(mitglied=request.user).exists()
    )
    meine_stimme = None
    if request.user.is_authenticated:
        reg = antrag.stimmregister.filter(mitglied=request.user).first()
        if reg:
            ab = antrag.stimmabgaben.filter(pseudonym=reg.pseudonym).first()
            meine_stimme = ab.stimme if ab else None
    ist_favorit = request.user.is_authenticated and antrag.favoriten.filter(mitglied=request.user).exists()
    vollzug = None
    if antrag.phase == Phase.ANGENOMMEN.value:
        vollzug = list(antrag.vollzug.select_related("durch"))
    return render(
        request,
        "verfahren/antrag.html",
        {
            "antrag": antrag,
            "vollzug": vollzug,
            "vollzug_statuswahl": Vollzugsstatus.choices,
            "darf_vollzug": antrag.phase == Phase.ANGENOMMEN.value
            and request.user.is_authenticated
            and request.user.hat_adminrechte,
            "ist_favorit": ist_favorit,
            "policy_json": json.dumps(antrag.policy_snapshot, indent=1, ensure_ascii=False),
            "fassung": antrag.aktueller_text(),
            "ergebnis": ergebnis,
            "kandidatur": kandidatur,
            "unterstuetzungen": antrag.unterstuetzungen.count(),
            "kommentare": antrag.kommentare.select_related("mitglied"),
            "frist": frist,
            "unterstuetzt_von_mir": unterstuetzt_von_mir,
            "meine_stimme": meine_stimme,
            "phase_offen": antrag.phase in (Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value),
            "abstimmung_laeuft": antrag.phase == Phase.ABSTIMMUNG.value,
        },
    )


def _register_zeilen():
    """Alle angenommenen Anträge mit aktuellem Vollzugsstand (F-55) — ohne Eintrag gilt „offen"."""
    angenommene = (
        Antrag.objects.filter(phase=Phase.ANGENOMMEN.value)
        .order_by("-phase_beginn")
        .prefetch_related("vollzug__durch")
    )
    zeilen = []
    for a in angenommene:
        stand = a.vollzugsstand()
        zeilen.append({"antrag": a, "stand": stand, "status": stand.status if stand else "offen"})
    return zeilen


def umsetzung(request):
    """F-55, § 6 Abs 10: das öffentliche Umsetzungsregister. Ein Beschluss, den
    niemand umsetzt, entwertet das Verfahren (L6) — deshalb steht hier zu jedem
    angenommenen Antrag der Stand der Umsetzung, offen für alle, mit voller Historie."""
    zeilen = _register_zeilen()
    zaehlung = [(wert, sum(1 for z in zeilen if z["status"] == wert)) for wert, _n in Vollzugsstatus.choices]
    gewaehlt = request.GET.get("status", "")
    if gewaehlt in Vollzugsstatus.values:
        zeilen = [z for z in zeilen if z["status"] == gewaehlt]
    else:
        gewaehlt = ""
    return render(
        request,
        "verfahren/umsetzung.html",
        {
            "zeilen": zeilen,
            "zaehlung": zaehlung,
            "gewaehlt": gewaehlt,
            "statuswahl": Vollzugsstatus.choices,
        },
    )


def umsetzung_json(request):
    """F-23: das Umsetzungsregister maschinenlesbar — Stand und volle Historie."""
    daten = [
        {
            "antrag": z["antrag"].pk,
            "titel": z["antrag"].titel,
            "angenommen_am": z["antrag"].phase_beginn.isoformat(),
            "status": z["status"],
            "historie": [
                {
                    "status": v.status,
                    "vermerk": v.vermerk,
                    "am": v.erstellt_am.isoformat(),
                    "durch": v.durch.anzeigename,
                }
                for v in reversed(list(z["antrag"].vollzug.all()))
            ],
        }
        for z in _register_zeilen()
    ]
    antwort = JsonResponse(
        {"register": daten, "exportiert_am": timezone.now().isoformat()},
        json_dumps_params={"ensure_ascii": False, "indent": 1},
    )
    antwort["Content-Disposition"] = 'attachment; filename="umsetzungsregister.json"'
    return antwort


def gesund(request):
    return JsonResponse({"status": "ok"})


def zukunftswerkstatt(request):
    """Die öffentliche Seite zur Zukunftswerkstatt (§ 6 Abs 11) — Aufklärung
    für alle und Einladung an die verwandten Bewegungen weltweit (§ 12).
    Reiner Inhalt, keine Datenbankabfragen; Strategie im Repository."""
    return render(request, "verfahren/zukunftswerkstatt.html")
