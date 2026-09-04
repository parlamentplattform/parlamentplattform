"""Lesende Ansichten. Grundsatz F-31: Sortierung ausschließlich nach Frist und
Phase — niemals nach Beliebtheit. Ergebnisseiten sind ohne Login lesbar (F-20)."""

import json
from pathlib import Path

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.utils import timezone
from django.utils.safestring import mark_safe
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy, ngettext

from plattform_core import Phase, __version__
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
    Unterstuetzung,
    Vollzugsstatus,
)

LAUFEND = [Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value]

# Die neun offenen Regler des WeicherFilters (FB-B2, Regel v2): Wortlaut im UI und das Merkmal,
# das sie gewichten (nachrechenbar, in [0, 1]; nachzulesen unter /parameter/#weicherfilter).
REGLER_NAMEN = {
    "ja": gettext_lazy("Mehr wie das, wofür ich gestimmt habe"),
    "nein": gettext_lazy("Mehr wie das, wogegen ich gestimmt habe"),
    "unterstuetzt": gettext_lazy("Mehr wie das, was ich unterstützt habe"),
    "entdeckungen": gettext_lazy("Interessantes außerhalb meiner Favoriten"),
    "unterstuetzungsphase": gettext_lazy("Mehr Unterstützungsanträge"),
    "abstimmungen": gettext_lazy("Mehr Abstimmungen"),
    "chronologisch": gettext_lazy("Mehr chronologisch (Neues zuerst)"),
    "ablaufend": gettext_lazy("Nur noch kurz online"),
    "schwelle": gettext_lazy("Wenig fehlt"),
}
REGLER_MERKMALE = {
    "ja": gettext_lazy(
        "Anteil der Lebensbereiche des Antrags, die in Anträgen vorkommen, bei denen meine eigene Stimme Ja war "
        "(die eigene Stimme kennt nur das Mitglied selbst über das Stimmregister)"
    ),
    "nein": gettext_lazy("Anteil der Lebensbereiche des Antrags, die in Anträgen vorkommen, bei denen meine eigene Stimme Nein war"),
    "unterstuetzt": gettext_lazy("Anteil der Lebensbereiche, die in meinen unterstützten Anträgen vorkommen"),
    "entdeckungen": gettext_lazy("1, wenn kein Lebensbereich des Antrags in meinem Abo-Ast liegt; sonst 0"),
    "unterstuetzungsphase": gettext_lazy("1 in der Unterstützungsphase, sonst 0"),
    "abstimmungen": gettext_lazy("1 in der Abstimmungsphase, sonst 0"),
    "chronologisch": gettext_lazy("Altersrang: jüngster Antrag 1, ältester 0"),
    "ablaufend": gettext_lazy("Anteil der eigenen Phasendauer, der schon verstrichen ist (0 bis 1)"),
    "schwelle": gettext_lazy(
        "Unterstützung: Unterstützungen / Schwelle · Abstimmung: Beteiligung / Mindestbeteiligung (gedeckelt 1) · Beratung: 0"
    ),
}


def _abo_ids(nutzer) -> set[int]:
    """Abonnierte Lebensbereiche samt allen Unterkategorien — ein Abo gilt für den ganzen Ast."""
    ids: set[int] = set()
    if not nutzer.is_authenticated:
        return ids
    ids.update(nutzer.kategorie_abos.values_list("kategorie_id", flat=True))
    kinder: dict[int | None, list[int]] = {}
    for kid, eid in Kategorie.objects.filter(aktiv=True).values_list("id", "eltern_id"):
        kinder.setdefault(eid, []).append(kid)
    rand = list(ids)
    while rand:
        neue = [k for e in rand for k in kinder.get(e, []) if k not in ids]
        ids.update(neue)
        rand = neue
    return ids


def _eigene_stimm_kategorien(nutzer):
    """Lebensbereiche der Anträge, bei denen die eigene Stimme Ja bzw. Nein war — nur dem
    Mitglied selbst bekannt (Stimmregister → Pseudonym → Stimmabgabe), nie anderen (F-15)."""
    je_pseudonym = dict(StimmRegister.objects.filter(mitglied=nutzer).values_list("pseudonym", "antrag_id"))
    if not je_pseudonym:
        return set(), set()
    ja_ids: set[int] = set()
    nein_ids: set[int] = set()
    abgaben = Stimmabgabe.objects.filter(pseudonym__in=je_pseudonym).values_list("antrag_id", "pseudonym", "stimme")
    for antrag_id, pseudonym, stimme in abgaben:
        if je_pseudonym.get(pseudonym) != antrag_id:
            continue
        if stimme == "ja":
            ja_ids.add(antrag_id)
        elif stimme == "nein":
            nein_ids.add(antrag_id)

    def kategorien(ids):
        return set(Kategorie.objects.filter(antraege__in=ids).values_list("pk", flat=True)) if ids else set()

    return kategorien(ja_ids), kategorien(nein_ids)


def _anteil(eigene: set, menge: set) -> float:
    return len(eigene & menge) / len(eigene) if eigene else 0.0


def _beteiligung(antrag):
    """(abgegebene Stimmen, Stimmberechtigte) einer laufenden Abstimmung — bei Personenwahlen
    zählen die Pseudonyme mit mindestens einer Zustimmung."""
    if antrag.art == Antragsart.MANDAT:
        abgegeben = (
            BewerbungsZustimmung.objects.filter(bewerbung__antrag=antrag).values("pseudonym").distinct().count()
        )
    else:
        abgegeben = antrag.stimmabgaben.count()
    return abgegeben, max(1, antrag.stimmberechtigte_anzahl or 1)


def _weicherfilter_reihen(nutzer, laufend, jetzt, regler, abo_ids, favoriten_zuerst=False):
    """FB-B1/B2: Merkmale (0..1) je laufendem Antrag bauen und im offenen Kern reihen (Regel v2).

    Grundordnung der Eingabe = die neutrale Ordnung (Abstimmung, Beratung, Unterstützung;
    innerhalb der Phase nach Fristnähe) — bei Punktgleichheit bleibt sie erhalten. Die
    Merkmale sind einfach und offen: Überschneidung der Lebensbereiche mit dem eigenen
    Ja-/Nein-/Unterstützungs-Verlauf, außerhalb der Favoriten, Phase, Altersrang,
    verstrichener Anteil der eigenen Phasendauer, Nähe zur Schwelle bzw. Mindestbeteiligung."""
    from plattform_core.weicherfilter import reihen

    phasen_rang = {Phase.ABSTIMMUNG.value: 0, Phase.BERATUNG.value: 1, Phase.UNTERSTUETZUNG.value: 2}
    antraege = sorted(
        laufend.prefetch_related("kategorien"),
        key=lambda a: (phasen_rang.get(a.phase, 9), a.phase_beginn),
    )
    if not antraege:
        return []
    kats = {a.pk: {k.pk for k in a.kategorien.all()} for a in antraege}
    ja_kats, nein_kats = _eigene_stimm_kategorien(nutzer)
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
        eigene = kats[a.pk]
        ablaufend = 0.0
        if frist and a.phase_beginn:
            dauer = (frist - a.phase_beginn).total_seconds()
            if dauer > 0:
                ablaufend = min(1.0, max(0.0, (jetzt - a.phase_beginn).total_seconds() / dauer))
        schwelle = 0.0
        if a.phase == Phase.UNTERSTUETZUNG.value:
            schwelle = min(1.0, a.unterstuetzungen.count() / max(1, policy.unterstuetzung_schwelle))
        elif a.phase == Phase.ABSTIMMUNG.value:
            abgegeben, basis = _beteiligung(a)
            schwelle = min(1.0, (abgegeben / basis) / max(policy.mindestbeteiligung, 0.0001))
        merkmale = {
            "ja": _anteil(eigene, ja_kats),
            "nein": _anteil(eigene, nein_kats),
            "unterstuetzt": _anteil(eigene, unterstuetzt_kats),
            "entdeckungen": 1.0 if eigene and not (eigene & abo_ids) else 0.0,
            "unterstuetzungsphase": 1.0 if a.phase == Phase.UNTERSTUETZUNG.value else 0.0,
            "abstimmungen": 1.0 if a.phase == Phase.ABSTIMMUNG.value else 0.0,
            "chronologisch": chrono[a.pk],
            "ablaufend": ablaufend,
            "schwelle": schwelle,
        }
        eintraege.append({"id": a.pk, "merkmale": merkmale, "favorit": bool(eigene & abo_ids)})
    lage = reihen(eintraege, regler, favoriten_zuerst)
    je_pk = {a.pk: a for a in antraege}
    return [
        {
            "antrag": je_pk[e["id"]],
            "punkte": e["punkte"],
            "favorit": e["favorit"],
            "anteile": [(REGLER_NAMEN[name], wert) for name, wert in e["anteile"].items()],
        }
        for e in lage
    ]


def _weicherfilter_feed(nutzer, antraege, laufend, jetzt, abo_ids, meine_stimmen, regler, favoriten_zuerst):
    """Bereich d (FB-B1): EINE punktgereihte Liste, wenn Regler gesetzt sind — sonst die neutralen
    Gruppen nach Phase und Frist; in beiden stehen Favoriten zuerst, wenn der Schalter steht.
    Jede Zeile trägt, was auch die Kachel weiß (Stand, Frist, Thema, eigene Stimme)."""
    from plattform_core.weicherfilter import ist_neutral

    def zeile(a, extra=None):
        z = _kachel(a, jetzt, meine_stimmen, abo_ids)
        z.update({"favorit": False, "anteile": [], "punkte": 0})
        z.update(extra or {})
        return z

    if nutzer.is_authenticated and not ist_neutral(regler):
        gereiht = _weicherfilter_reihen(nutzer, laufend, jetzt, regler, abo_ids, favoriten_zuerst)
        return {"gereiht": [zeile(e["antrag"], e) for e in gereiht], "gruppen": None, "leer": not gereiht}

    fav_ids: set[int] = set()
    if abo_ids and favoriten_zuerst:
        fav_ids = set(laufend.filter(kategorien__in=abo_ids).values_list("pk", flat=True))

    def ordnen(qs):
        return sorted(qs.prefetch_related("kategorien"), key=lambda a: (0 if a.pk in fav_ids else 1, a.phase_beginn))

    def gruppe(phase):
        return [zeile(a, {"favorit": a.pk in fav_ids}) for a in ordnen(laufend.filter(phase=phase))]

    abgeschlossen = antraege.filter(
        phase__in=[Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value, Phase.VERFALLEN.value]
    ).order_by("-phase_beginn")[:20]
    gruppen = [
        (_("Laufende Abstimmungen"), gruppe(Phase.ABSTIMMUNG.value)),
        (_("In Beratung"), gruppe(Phase.BERATUNG.value)),
        (_("Sammeln Unterstützung"), gruppe(Phase.UNTERSTUETZUNG.value)),
        (_("Abgeschlossen"), [zeile(a) for a in abgeschlossen.prefetch_related("kategorien")]),
    ]
    return {"gereiht": None, "gruppen": gruppen, "leer": not any(liste for _titel, liste in gruppen[:3])}


def _filter_lage(profile, aktives, regler, favoriten_zuerst):
    """Was Leiste und Overlay des WeicherFilters brauchen (FB-B3–B5)."""
    from verfahren.models import FilterProfil

    return {
        "profile": profile,
        "aktiv": aktives,
        "regler_meta": [(name, REGLER_NAMEN[name], regler[name]) for name in REGLER_NAMEN],
        "favoriten_zuerst": favoriten_zuerst,
        "hoechstzahl": FilterProfil.HOECHSTZAHL,
        "voll": len(profile) >= FilterProfil.HOECHSTZAHL,
        # der gespeicherte Stand für die Anzeige „● Ungespeichert“ (nur bekannte Schlüssel und Zahlen)
        "gespeichert_json": mark_safe(json.dumps({**regler, "favoriten_zuerst": bool(favoriten_zuerst)})),
    }


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


def _kachel(antrag, jetzt, meine_stimmen=None, abo_ids=None):
    """Eine Kachel für P3/P4 (F-42/F-43, FB-D2): Thema mit eigenem Stern, Titel,
    Stand, Frist mit Ring und die Direkt-Handlung der Phase. Während einer
    laufenden Abstimmung zeigt die Kachel NUR die Beteiligung — nie die Tendenz
    (F-15: kein Bandwagon; das Ergebnis erscheint nach Fristende auf der
    Antragsseite)."""
    policy = antrag.policy()
    frist = _frist_fuer(antrag, policy)
    resttage = max(0, (frist - jetzt).days) if frist else None
    # Ring: Anteil der bereits verstrichenen Phase (FB-D2 Punkt 4)
    verstrichen = None
    if frist and antrag.phase_beginn:
        ganze = (frist - antrag.phase_beginn).total_seconds()
        if ganze > 0:
            verstrichen = min(100, max(0, round(100 * (jetzt - antrag.phase_beginn).total_seconds() / ganze)))
    # Thema: der erste zugeordnete Lebensbereich, mit eigenem Abo-Stern
    thema = next(iter(antrag.kategorien.all()), None)
    stat = None
    if antrag.phase == Phase.UNTERSTUETZUNG.value:
        n = antrag.unterstuetzungen.count()
        schwelle = max(1, policy.unterstuetzung_schwelle)
        stat = {"typ": "unterstuetzung", "n": n, "schwelle": schwelle,
                "prozent": min(100, round(100 * n / schwelle))}
    elif antrag.phase == Phase.BERATUNG.value:
        # nur der laufende Chat zählt — Archiviertes gehört zur vorigen Phase (FB-G5)
        stat = {"typ": "beratung", "beitraege": antrag.kommentare.filter(archiviert_am__isnull=True).count()}
    elif antrag.phase == Phase.ABSTIMMUNG.value:
        abgegeben, basis = _beteiligung(antrag)
        stat = {"typ": "abstimmung", "abgegeben": abgegeben,
                "prozent": min(100, round(100 * abgegeben / basis))}
    return {
        "antrag": antrag,
        "frist": frist,
        "resttage": resttage,
        "verstrichen": verstrichen,
        "stat": stat,
        "thema": thema,
        "thema_abonniert": bool(thema and abo_ids and thema.pk in abo_ids),
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
    """Die Willkommensseite unter „/" — der Einstieg für alle (auch übers
    Header-Logo): Hier wird das System erklärt und jeder Bereich vorgestellt.
    Leitidee P1 bleibt: Das Parlament ist zum Benutzen da, erklärt wird hier —
    darum sind Willkommensseite und Parlament getrennte Seiten. Der frühere
    Mitglieder-Redirect ist bewusst gefallen: Der Einstieg zeigt allen die
    Übersicht, das Parlament ist von überall einen Klick entfernt."""
    from mitglieder.models import Mitglied

    antraege = Antrag.objects.exclude(phase=Phase.ZURUECKGEWIESEN.value)
    laufend = antraege.filter(phase__in=LAUFEND)
    buehne = {
        "mitglieder": Mitglied.objects.filter(is_active=True).count(),
        "laufend": laufend.count(),
        "beschluesse": Antrag.objects.filter(phase=Phase.ANGENOMMEN.value).count(),
    }
    wichtige = laufend.filter(hervorgehoben=True).order_by("phase_beginn")[:3]
    return render(
        request,
        "verfahren/index.html",
        {"buehne": buehne, "wichtige": wichtige, "meine_favoriten": _meine_favoriten(request.user)},
    )


def _meine_favoriten(nutzer) -> set[int]:
    """Antrags-IDs, die das Mitglied sich gemerkt hat — für den Stern an jeder Antragszeile (FB-C4)."""
    if not nutzer.is_authenticated:
        return set()
    return set(nutzer.favoriten.values_list("antrag_id", flat=True))


def _kategorien_suchen(suchtext: str, nutzer) -> list[dict]:
    """Die Tiefen-Ansicht als Feld-Suche (P2): findet Lebensbereiche über
    Name, Beschreibung und Schlagworte; jeder Treffer trägt Pfad, laufende
    Verfahren im ganzen Ast und den Abo-Stand — Klick öffnet den Fächer dort."""
    from verfahren.views_aktionen import _laufend_je_ast

    abonniert: set[int] = set()
    if nutzer.is_authenticated:
        abonniert = set(nutzer.kategorie_abos.values_list("kategorie_id", flat=True))
    laufend = _laufend_je_ast()
    norm = suchtext.casefold()
    treffer = []
    for k in Kategorie.objects.filter(aktiv=True):
        if (
            norm in k.name.casefold()
            or norm in k.beschreibung.casefold()
            or any(norm in wort.casefold() for wort in k.schlagworte)
        ):
            treffer.append(
                {"k": k, "laufend": laufend.get(k.pk, 0), "abonniert": k.pk in abonniert}
            )
    treffer.sort(key=lambda t: (t["k"].tiefe, t["k"].name))
    return treffer[:24]


def parlament(request):
    """Das Parlament in vier Bereichen (§ 5 Abs 10, F-40) — die Arbeitsansicht.
    Reihung immer nur nach Phase und Frist, nie nach Beliebtheit oder
    verdeckter Gewichtung (F-31). Ohne Login lesbar (F-20), abstimmen können
    Mitglieder."""
    antraege = Antrag.objects.exclude(phase=Phase.ZURUECKGEWIESEN.value)
    laufend = antraege.filter(phase__in=LAUFEND)

    # Bereich a — der Favoriten-Fächer (P2, F-46): erscheint DIREKT im Feld
    # (Vorgabe des Gründers, 1.9. abends): kein Liste/Fächer-Umschalter, keine
    # eigene Lebensbereiche-Seite mehr — oben eine Suche als Tiefen-Ansicht.
    # ?fach= steuert den Knoten, ?suche= die Suche; ohne JavaScript ist jeder
    # Klick eine Seite, mit htmx wechselt nur das Feld.
    from plattform_core.faecher import faecher_layout

    zeilen = list(
        Kategorie.objects.filter(aktiv=True).values("id", "slug", "name", "eltern_id", "reihenfolge")
    )
    for zeile in zeilen:  # die Wurzel heißt im Fächer schlicht „Lebensbereiche"
        if zeile["eltern_id"] is None:
            zeile["name"] = str(_("Lebensbereiche"))
    abo_slugs = (
        set(request.user.kategorie_abos.values_list("kategorie__slug", flat=True))
        if request.user.is_authenticated
        else set()
    )
    # FB-C3: im Ruhezustand ist der Ast des ersten Favoriten entfaltet
    faecher = faecher_layout(zeilen, fokus_slug=request.GET.get("fach") or None, abos=abo_slugs)
    faecher["abos"] = abo_slugs
    suchtext = (request.GET.get("suche") or "").strip()
    suchtreffer = _kategorien_suchen(suchtext, request.user) if suchtext else None

    meine_favoriten: set[int] = set()
    if request.user.is_authenticated:
        meine_favoriten = set(request.user.favoriten.values_list("antrag_id", flat=True))
    abo_ids = _abo_ids(request.user)  # ein Abo gilt für den ganzen Ast

    jetzt = timezone.now()

    # Bereich b — vom Integritätsrat hervorgehobene Abstimmungen (F-42, nie
    # algorithmisch), als Kacheln (P3): Stern, Beteiligung, Resttage.
    wichtige = list(
        laufend.filter(hervorgehoben=True).order_by("phase_beginn").prefetch_related("kategorien")
    )

    # Bereich c — Meine Region (F-43, P4): drei Zeilen Gemeinde/Bezirk/Land.
    # Mit Wohnsitz zeigt jede Zeile die EIGENE Region; ohne (Gäste, fehlendes
    # Profil) alle regionalen Anträge der jeweiligen Ebene.
    regionale = laufend.exclude(ebene="bund").order_by("phase_beginn").prefetch_related("kategorien")
    mein_ort = {"gemeinde": "", "bezirk": "", "land": ""}
    if request.user.is_authenticated:
        mein_ort["gemeinde"] = request.user.gemeinde or ""
        mein_ort["land"] = (
            request.user.get_bundesland_display() if request.user.bundesland else ""
        )
        if request.user.wohnsitz_id:
            mein_ort["bezirk"] = request.user.wohnsitz.bezirk or ""

    meine_stimmen = _meine_stimmen(request.user, list(laufend))  # Kacheln und Feed-Zeilen
    meine_unterstuetzungen: set[int] = set()
    if request.user.is_authenticated:
        meine_unterstuetzungen = set(
            Unterstuetzung.objects.filter(mitglied=request.user).values_list("antrag_id", flat=True)
        )

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
                "kacheln": [_kachel(a, jetzt, meine_stimmen, abo_ids) for a in zeile],
            }
        )

    wichtige_kacheln = [_kachel(a, jetzt, meine_stimmen, abo_ids) for a in wichtige]

    # Bereich d — der WeicherFilter (FB-B1–B6): das aktive Profil reiht die laufenden
    # Verfahren nach den offenen Reglern des Mitglieds (Regel v2); sonst gilt die neutrale
    # Voreinstellung (Phase und Frist, chronologisch) — Favoriten zuerst, wenn der Schalter steht.
    filter_lage = None
    regler: dict[str, int] = {}
    favoriten_zuerst = False
    if request.user.is_authenticated:
        from plattform_core.weicherfilter import regler_bereinigen

        profile = list(request.user.filterprofile.all())
        aktives = next((p for p in profile if p.aktiv), None)
        regler = regler_bereinigen(aktives.regler if aktives else {})
        favoriten_zuerst = aktives.favoriten_zuerst if aktives else request.user.favoriten_zuerst
        filter_lage = _filter_lage(profile, aktives, regler, favoriten_zuerst)
    feed = _weicherfilter_feed(
        request.user, antraege, laufend, jetzt, abo_ids, meine_stimmen, regler, favoriten_zuerst
    )
    return render(
        request,
        "verfahren/parlament.html",
        {
            "faecher": faecher,
            "suchtext": suchtext,
            "suchtreffer": suchtreffer,
            "feed": feed,
            "meine_favoriten": meine_favoriten,
            "filter_lage": filter_lage,
            "wichtige_kacheln": wichtige_kacheln,
        "meine_unterstuetzungen": meine_unterstuetzungen,
            "region_zeilen": region_zeilen,
            "region_gefiltert": any(mein_ort.values()),
        },
    )


def _regeln_lesbar(policy) -> list[tuple[str, str]]:
    """Die eingefrorenen Verfahrensregeln als lesbare Liste statt als JSON-Block (FB-F1).
    § 5 Abs 5: Was beim Einbringen galt, gilt bis zum Ende — man muss es lesen können."""
    mehrheit = (
        _("Ja mehr als Nein")
        if policy.mehrheitsbasis == "ja_nein"
        else _("Ja mehr als die Hälfte aller abgegebenen Stimmen")
    )
    return [
        (_("Unterstützungsschwelle"), ngettext("%d Unterstützung", "%d Unterstützungen", policy.unterstuetzung_schwelle) % policy.unterstuetzung_schwelle),
        (_("Frist zum Unterstützen"), ngettext("%d Tag", "%d Tage", policy.unterstuetzung_frist_tage) % policy.unterstuetzung_frist_tage),
        (_("Beratung"), ngettext("%d Tag", "%d Tage", policy.beratung_tage) % policy.beratung_tage),
        (_("Abstimmung"), ngettext("%d Tag", "%d Tage", policy.abstimmung_tage) % policy.abstimmung_tage),
        (_("Mindestbeteiligung"), f"{policy.mindestbeteiligung * 100:g} %"),
        (_("Mehrheit"), mehrheit),
        (_("Sperre für Wiedereinbringung"), ngettext("%d Monat", "%d Monate", policy.wiedereinbringung_sperre_monate) % policy.wiedereinbringung_sperre_monate),
        (_("Verfahrensordnung"), f"{policy.id} v{policy.version}"),
    ]


def _einschaetzung(antrag):
    """Zone 2 (FB-F2): der Stand der Modellrechnung zu diesem Antrag — Kopfkarte und
    Beanstandungen. Die Karten mit Grafiken folgen mit der Zukunftswerkstatt (S11);
    bis dahin zeigt die Zone ehrlich, dass noch nichts vorliegt."""
    from ki.anbieter import anbieter_waehlen
    from ki.models import KILauf

    lauf = KILauf.objects.filter(antrag=antrag, erfolgreich=True).order_by("-erstellt_am").first()
    anbieter = anbieter_waehlen()
    return {
        "lauf": lauf,
        "anbieter_da": anbieter is not None,
        "modell": lauf.modell if lauf else (getattr(anbieter, "modell", "") or ""),
        "beanstandungen": list(antrag.beanstandungen.select_related("mitglied")),
        # Was die Zone zeigen wird, sobald die Werkstatt rechnet (Skelett-Umrisse, FB-F2)
        "kommende_karten": [
            _("Ähnliche Anträge"),
            _("Berührte Gesetze"),
            _("Folgen für Judikatur und Exekutive"),
            _("Aufwand, Last und Dauer"),
            _("Ausschreibung"),
        ],
    }


def gespraeche(request):
    """Meine Gespräche (FB-G3): dieselbe Liste, die das Panel zeigt — als eigene Seite, damit
    sie auch ohne JavaScript erreichbar ist. Mit htmx antwortet nur die Liste."""
    from verfahren.chat import gespraeche as gespraeche_laden

    zeilen = gespraeche_laden(request.user)
    nur_ungelesen = request.GET.get("filter") == "ungelesen"
    if nur_ungelesen:
        zeilen = [z for z in zeilen if z["ungelesen"]]
    vorlage = "verfahren/_gespraeche_liste.html" if request.headers.get("HX-Request") else "verfahren/gespraeche.html"
    return render(
        request,
        vorlage,
        {
            "gespraeche": zeilen,
            "ungelesen": sum(1 for z in gespraeche_laden(request.user) if z["ungelesen"]),
            "nur_ungelesen": nur_ungelesen,
        },
    )


def _chat_lage(antrag, nutzer) -> dict:
    """Zone 3 (FB-G1, G2, G5): der laufende Faden, was neu ist, ob geschrieben werden darf und
    wie viele Beiträge im Archiv der vorigen Phasen liegen."""
    from verfahren import chat as chatkern

    archiviert = antrag.kommentare.filter(archiviert_am__isnull=False).count()
    letzte_phase = ""
    if archiviert:
        letzter = antrag.kommentare.filter(archiviert_am__isnull=False).order_by("-archiviert_am").first()
        letzte_phase = letzter.phase if letzter else ""
    from verfahren.models import Meldung

    return {
        "faden": chatkern.faden(antrag, nutzer),
        "meldegruende": Meldung.Grund.choices,
        "anzahl": antrag.kommentare.filter(archiviert_am__isnull=True).count(),
        "neue": chatkern.neue_zaehlen(antrag, nutzer),
        "offen": chatkern.chat_offen(antrag),
        "archiviert": archiviert,
        "archiv_phase": letzte_phase,
    }


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
    # Entwurfsschleife (§ 5 Abs 12, F-66/F-67): der Vorschlag des Expertenrats am Antrag.
    entwurf = getattr(antrag, "entwurf", None)
    schleife = None
    if entwurf is not None:
        mein_votum = None
        if request.user.is_authenticated:
            mein_votum = entwurf.unterstuetzer_voten.filter(
                mitglied=request.user, runde=entwurf.runde
            ).first()
        schleife = {
            "entwurf": entwurf,
            "vorschlag": entwurf.aktuelle_fassung(),
            "pruefungen": list(entwurf.pruefungen.all()),  # § 6 Abs 7: Begründungen öffentlich
            "stand": entwurf.votum_stand(),
            "voten": list(
                entwurf.unterstuetzer_voten.filter(runde=entwurf.runde).select_related("mitglied")
            ),
            "mein_votum": mein_votum,
        }
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
            "regeln": _regeln_lesbar(policy),
            "fassung": antrag.aktueller_text(),
            "fassungen": list(antrag.fassungen.order_by("-nummer")),
            # Zone 2 entfällt bei Personenwahlen — über Menschen rechnet keine Maschine (FB-F4)
            "einschaetzung": None if antrag.art == Antragsart.MANDAT else _einschaetzung(antrag),
            "ergebnis": ergebnis,
            "kandidatur": kandidatur,
            "schleife": schleife,
            "unterstuetzungen": antrag.unterstuetzungen.count(),
            "chat": _chat_lage(antrag, request.user),
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
            "meine_favoriten": _meine_favoriten(request.user),
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


# Das Übertragungspaket (FB-M7): (Name im ZIP, Pfad relativ zur Repo-Wurzel) — alles aus dem
# Repo-Stand, nichts aus der Datenbank dieser Instanz.
PAKET_DATEIEN = (
    ("GEMEINSAME_VISION.md", "docs/partner/GEMEINSAME_VISION.md"),
    ("EINSTIEG.md", "docs/partner/EINSTIEG.md"),
    ("EINRICHTUNG.md", "docs/partner/EINRICHTUNG.md"),
    ("SATZUNG_BAUKASTEN.md", "docs/partner/SATZUNG_BAUKASTEN.md"),
    ("SCHEMA.md", "docs/SCHEMA.md"),
    ("instanz/docker-compose.yml", "docs/partner/instanz/docker-compose.yml"),
    ("instanz/env.example", "docs/partner/instanz/env.example"),
    ("instanz/render.yaml", "docs/partner/instanz/render.yaml"),
    ("policies/kategorien-v2.yaml", "policies/kategorien-v2.yaml"),
    ("policies/grundordnung-v1.yaml", "policies/grundordnung-v1.yaml"),
)
PAKET_ERZEUGT = ("README-PAKET.md", "parameter-erstbestand.json")


def partner(request):
    """§ 12, FB-M1/M6/M7/M8 („Labor der Demokratien"): die Einladung an die verwandten
    Parteien weltweit — gemeinsame Vision, das Modell „ein Kern, viele Instanzen" mit
    Schaubild, die Schnittstelle, der Einstiegs-Fahrplan in zwei Spuren, das
    Übertragungspaket, Kontakt. Unaufdringlich über die Fußzeile erreichbar; das
    Partner-Konto mit eigener Oberfläche folgt (S14b)."""
    return render(
        request,
        "verfahren/partner.html",
        {
            "version": __version__,
            "system_id": settings.DDOE_SYSTEM_ID,
            "paket": [name for name, _pfad in PAKET_DATEIEN] + list(PAKET_ERZEUGT),
        },
    )


def _paket_readme() -> str:
    zeilen = "\n".join(f"- `{name}`" for name in [n for n, _p in PAKET_DATEIEN] + list(PAKET_ERZEUGT))
    return (
        f"# ParlamentPlattform — Übertragungspaket {__version__}\n\n"
        "Alles, was eine Schwesterpartei braucht, um die ParlamentPlattform und die Satzung für das\n"
        "eigene Land zu übernehmen (Satzung § 12, Fahrtenbuch FB-M7). Reihenfolge: EINSTIEG.md lesen,\n"
        "SATZUNG_BAUKASTEN.md anpassen, EINRICHTUNG.md abarbeiten, Instanz aus `instanz/` starten,\n"
        "SCHEMA.md für den Austausch. Quellcode und aktuelle Fassung:\n"
        "https://github.com/parlamentplattform/parlamentplattform — Kontakt: plattform@ddoe.at\n\n"
        "Everything a sister party needs to adopt the ParlamentPlattform and the statutes for its own\n"
        "country. Order: read EINSTIEG.md, adapt SATZUNG_BAUKASTEN.md, work through EINRICHTUNG.md,\n"
        "start an instance from `instanz/`, use SCHEMA.md for the exchange between instances.\n\n"
        f"## Inhalt / Contents\n\n{zeilen}\n"
    )


def partner_paket(request):
    """FB-M7: das Übertragungspaket als ZIP — Satzungs-Baukasten, Einstiegs-Fahrplan, Checkliste,
    Instanz-Vorlage, Schema, Kategorienbaum, Verfahrensordnung und der Erstbestand der Stellgrößen
    mit Schema-Kennungen. Erzeugt aus dem Repo-Stand, ohne Daten dieser Instanz."""
    import io
    import zipfile

    from parameter.models import ERSTBESTAND
    from plattform_core.schema import SCHEMA_VERSION, schema_key

    wurzel = Path(__file__).resolve().parent.parent
    puffer = io.BytesIO()
    with zipfile.ZipFile(puffer, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("README-PAKET.md", _paket_readme())
        for name, pfad in PAKET_DATEIEN:
            zf.write(wurzel / pfad, name)
        erstbestand = [{**e, "schema_key": schema_key(e["schluessel"])} for e in ERSTBESTAND]
        zf.writestr(
            "parameter-erstbestand.json",
            json.dumps({"schema_version": SCHEMA_VERSION, "parameter": erstbestand}, ensure_ascii=False, indent=1),
        )
    antwort = HttpResponse(puffer.getvalue(), content_type="application/zip")
    antwort["Content-Disposition"] = f'attachment; filename="parlamentplattform-paket-{__version__}.zip"'
    return antwort


def zukunftswerkstatt(request):
    """Die öffentliche Seite zur Zukunftswerkstatt (§ 6 Abs 11) — Aufklärung
    für alle und Einladung an die verwandten Bewegungen weltweit (§ 12).
    Seit Ring 0b (F-60) zeigt sie zusätzlich die Rechenschaft des
    Modell-Steckplatzes: angeschlossen?, Läufe, Tokenverbrauch, Budget."""
    from ki.models import KILauf, steckplatz_stand

    return render(
        request,
        "verfahren/zukunftswerkstatt.html",
        {
            "steckplatz": steckplatz_stand(),
            "letzte_laeufe": list(KILauf.objects.select_related("antrag")[:8]),
        },
    )
