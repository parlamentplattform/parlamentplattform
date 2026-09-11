"""Das Chatsystem der Plattform (FB-G1 bis G5) — die Schreibwege und die Fäden.

Ein Chat hängt an einem Antrag und lebt in dessen Phase: Bei jeder Hochstufung wandern die
Beiträge ins Archiv (`Antrag.chat_archivieren`), der laufende Chat beginnt leer. Der Faden ist
eine Ebene tief — eine Antwort auf eine Antwort hängt sich an denselben Wurzelbeitrag, damit
niemand in Verschachtelungen verschwindet.

Ein **Gespräch** entsteht implizit (FB-G3): sobald zwischen zwei Menschen an einem Antrag eine
Antwort liegt — ich unter seinem Beitrag oder er unter meinem. Niemand muss jemanden benennen.
Aus diesen Paaren baut das Panel „Meine Gespräche" seine Liste.
"""

from __future__ import annotations

from django.db.models import Count, Q
from django.utils import timezone
from django.utils.translation import gettext as _

from plattform_core import vorschlagschat
from verfahren.models import Kommentar, Lesestand, Reaktion, Reaktionsart

#: Rückfallwert; der gültige steht im Register unter „kritik-mindestzeichen" (FB-J2).
KRITIK_MINDESTLAENGE = 80
#: dito für die Zeichengrenze eines Beitrags
CHAT_ZEICHEN = 4000
#: dito für die Zahl der Wurzelbeiträge, die der Faden auf einmal zeigt („chat-faden-wurzeln“, Befund #42)
FADEN_WURZELN = 50


def kritik_mindestzeichen() -> int:
    """Wie lang eine Kritik mindestens sein muss — aus dem Register (FB-J2)."""
    from parameter.models import zahl

    return zahl("kritik-mindestzeichen", KRITIK_MINDESTLAENGE)


def chat_zeichen_hoechstzahl() -> int:
    """Wie lang ein Beitrag sein darf — aus dem Register (FB-J2)."""
    from parameter.models import zahl

    return zahl("chat-zeichen-hoechstzahl", CHAT_ZEICHEN)


def faden_wurzeln() -> int:
    """Wie viele Wurzelbeiträge (samt Antworten) der Faden auf einmal zeigt — aus dem Register."""
    from parameter.models import zahl

    return zahl("chat-faden-wurzeln", FADEN_WURZELN)


def mit_zaehlern(qs):
    """Zustimmungen und Ablehnungen als Annotation je Beitrag (Befund #42).

    Vorher lud `prefetch_related("reaktionen")` jede einzelne Reaktion und zählte in Python —
    bei einem umkämpften Antrag Hunderttausende Zeilen für zwei Zahlen je Beitrag."""
    return qs.annotate(
        zustimmungen=Count("reaktionen", filter=Q(reaktionen__art=Reaktionsart.ZUSTIMMUNG)),
        ablehnungen=Count("reaktionen", filter=Q(reaktionen__art=Reaktionsart.ABLEHNUNG)),
    )


def leicht(qs) -> list[dict]:
    """Nur die Zahlen der Beiträge, wie die offene Rechnung (FB-G6) sie braucht — ohne Text,
    ohne Modellobjekte: id, ja, nein, zeit, system, ist_kritik."""
    return [
        {"id": z["pk"], "ja": z["zustimmungen"], "nein": z["ablehnungen"], "zeit": z["erstellt_am"],
         "system": z["system"], "ist_kritik": z["ist_kritik"]}
        for z in mit_zaehlern(qs).order_by("erstellt_am", "pk").values(
            "pk", "zustimmungen", "ablehnungen", "erstellt_am", "system", "ist_kritik"
        )
    ]


class ChatGesperrt(Exception):
    """Der Chat dieses Antrags nimmt gerade keine Beiträge an."""


def entwurf_von(antrag):
    """Das Entwurfsfenster des Antrags — oder None, solange keines geöffnet wurde."""
    try:
        return antrag.entwurf
    except Exception:  # ObjectDoesNotExist, ohne gremien zu importieren
        return None


def ruht_wegen_werkstatt(antrag) -> bool:
    """Der Chat ruht, während der Expertenrat am Vorschlag arbeitet (FB-G6, A0-07).

    Die Sperre beginnt mit dem Öffnen des Entwurfsfensters und endet, sobald der Vorschlag
    den Unterstützern vorliegt. Gelesen wird weiter — geschrieben nicht."""
    from gremien.models import EntwurfsStatus
    from plattform_core import Phase

    if antrag.phase != Phase.BERATUNG.value:
        # Nach der Beratung arbeitet die Werkstatt nicht mehr — ein nie eingereichtes Fenster
        # darf den Chat der Abstimmung nicht sperren (Befund #34).
        return False
    entwurf = entwurf_von(antrag)
    return entwurf is not None and entwurf.status in (
        EntwurfsStatus.IN_ARBEIT,
        EntwurfsStatus.PRUEFUNG,
    )


def abstimmungschat(antrag):
    """Der Entwurf, dessen Vorschlag gerade zur Abstimmung im Chat steht — sonst None (FB-G6)."""
    from gremien.models import EntwurfsStatus

    entwurf = entwurf_von(antrag)
    return entwurf if entwurf is not None and entwurf.status == EntwurfsStatus.UNTERSTUETZER else None


def chat_phase(antrag) -> str:
    """Die Phase, unter der ein neuer Beitrag im Archiv erscheint.

    Im Abstimmungs-Chat trägt sie die Runde, damit das Archiv die Vorschlagsberatungen
    auseinanderhält („vorschlag-r1", „vorschlag-r2", …)."""
    entwurf = abstimmungschat(antrag)
    return f"vorschlag-r{entwurf.runde}" if entwurf is not None else antrag.phase


def chat_offen(antrag) -> bool:
    """Geschrieben wird, solange das Verfahren läuft und der Expertenrat nicht arbeitet.

    Nach dem Ende bleibt das Archiv lesbar (FB-G1); während der Werkstattarbeit ruht der
    Chat (FB-G6)."""
    from plattform_core import Phase

    if antrag.phase not in (Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value):
        return False
    return not ruht_wegen_werkstatt(antrag)


def beitrag_schreiben(
    antrag, mitglied, text: str, antwort_auf=None, jetzt=None, ist_kritik: bool = False,
    bezug_absatz: int | None = None,
) -> Kommentar:
    """Der einzige Schreibweg für Chat-Beiträge (FB-G1).

    Der Beitrag merkt sich die Phase, in der er entsteht — daraus lebt die Archivierung.
    Eine Antwort hängt immer am Wurzelbeitrag ihres Fadens und nur an einem Beitrag desselben,
    noch nicht archivierten Antrags."""
    jetzt = jetzt or timezone.now()
    if ruht_wegen_werkstatt(antrag):
        raise ChatGesperrt("Der Expertenrat arbeitet am Vorschlag — der Chat öffnet mit dem Vorschlag.")
    if not chat_offen(antrag):
        raise ChatGesperrt("Das Verfahren ist beendet — der Chat ist nur noch im Archiv lesbar.")
    if ist_kritik:
        if abstimmungschat(antrag) is None:
            raise ValueError("Kritik am Vorschlag gibt es nur im Abstimmungs-Chat.")
        mindestens = kritik_mindestzeichen()
        if len((text or "").strip()) < mindestens or not bezug_absatz:
            raise ValueError(
                f"Kritik braucht einen Textstellenbezug und mindestens {mindestens} Zeichen."
            )
    text = (text or "").strip()
    if not text:
        raise ValueError("Ein Beitrag braucht Text.")
    wurzel = None
    if antwort_auf is not None:
        if antwort_auf.antrag_id != antrag.pk or antwort_auf.archiviert_am:
            raise ValueError("Antworten gehen nur auf laufende Beiträge desselben Antrags.")
        wurzel = antwort_auf.wurzel()
    return Kommentar.objects.create(
        antrag=antrag,
        mitglied=mitglied,
        text=text[: chat_zeichen_hoechstzahl()],
        antwort_auf=wurzel,
        phase=chat_phase(antrag),
        erstellt_am=jetzt,
        ist_kritik=bool(ist_kritik),
        bezug_absatz=bezug_absatz if ist_kritik else None,
    )


def faden_fenster(antrag, nutzer=None, nach_engagement: bool = False, ab: int | None = None, grenze=-1) -> dict:
    """Ein Fenster des laufenden Fadens (Befund #42): Wurzelbeiträge mit ihren Antworten.

    Chronologisch zeigt das Fenster die **jüngsten** `grenze` Wurzelbeiträge; ältere holt man
    über `ab=<pk>` (das Fenster vor diesem Beitrag) — als Link ohne JavaScript, mit htmx zum
    Anhängen. Im Abstimmungs-Chat (nach Engagement, FB-G6) zeigt es die **vordersten** der
    Reihung, `ab=<pk>` liefert die nächsten dahinter; die Reihung selbst rechnet über alle
    Wurzelbeiträge, aber nur über ihre Zahlen. `grenze=-1` nimmt den Registerwert, None alles.

    Jeder Eintrag trägt, was die Anzeige braucht — eigene Reaktion, Zahl der Zustimmungen,
    ob er neu ist. `neu` bezieht sich auf den Lesestand des Mitglieds (FB-G2).

    Rückgabe: faden (Liste), mehr (weitere Wurzelbeiträge außerhalb des Fensters), mehr_ab
    (der Beitrag, an dem das nächste Fenster ansetzt), richtung („aelter“ | „weiter“), ab."""
    if grenze == -1:
        grenze = faden_wurzeln()
    wurzeln = antrag.kommentare.filter(archiviert_am__isnull=True, antwort_auf__isnull=True)
    mehr, mehr_ab, rang = 0, None, None
    if nach_engagement:
        richtung = "weiter"
        ids = [b["id"] for b in vorschlagschat.reihen(leicht(wurzeln))]
        start = ids.index(ab) + 1 if ab in ids else 0
        fenster = ids[start : start + grenze] if grenze else ids[start:]
        rest = len(ids) - (start + len(fenster))
        if rest > 0 and fenster:
            mehr, mehr_ab = rest, fenster[-1]
        rang = {pk: i for i, pk in enumerate(ids)}
    else:
        richtung = "aelter"
        qs = wurzeln.order_by("-pk")
        if ab:
            qs = qs.filter(pk__lt=ab)
        fenster = list(qs.values_list("pk", flat=True)[:grenze] if grenze else qs.values_list("pk", flat=True))
        if fenster:
            mehr = wurzeln.filter(pk__lt=min(fenster)).count()
            mehr_ab = min(fenster) if mehr else None
    beitraege = list(
        mit_zaehlern(
            antrag.kommentare.filter(archiviert_am__isnull=True).filter(
                Q(pk__in=fenster) | Q(antwort_auf_id__in=fenster)
            )
        )
        .select_related("mitglied")
        .order_by("erstellt_am", "pk")
    )
    gelesen_bis = None
    meine: dict[int, str] = {}
    if nutzer is not None and nutzer.is_authenticated:
        stand = Lesestand.objects.filter(mitglied=nutzer, antrag=antrag).first()
        gelesen_bis = stand.gelesen_bis if stand else None
        meine = {
            r.kommentar_id: r.art
            for r in Reaktion.objects.filter(mitglied=nutzer, kommentar_id__in=[k.pk for k in beitraege])
        }

    def schmuecken(k: Kommentar) -> dict:
        return {
            "k": k,
            "zustimmungen": k.zustimmungen,
            "ablehnungen": k.ablehnungen,
            "engagement": k.zustimmungen + k.ablehnungen,
            "ich_zustimme": meine.get(k.pk) == Reaktionsart.ZUSTIMMUNG,
            "ich_lehne_ab": meine.get(k.pk) == Reaktionsart.ABLEHNUNG,
            "neu": bool(gelesen_bis and k.erstellt_am > gelesen_bis and k.mitglied_id != getattr(nutzer, "pk", None)),
            "eigener": nutzer is not None and k.mitglied_id is not None
            and getattr(nutzer, "pk", None) == k.mitglied_id,
        }

    je_wurzel: dict[int, list[dict]] = {}
    for k in beitraege:
        if k.antwort_auf_id:
            je_wurzel.setdefault(k.antwort_auf_id, []).append(schmuecken(k))
    faden = [
        {**schmuecken(k), "antworten": je_wurzel.get(k.pk, [])}
        for k in beitraege
        if not k.antwort_auf_id
    ]
    if rang is not None:
        # FB-G6: Im Abstimmungs-Chat steht oben, was am meisten bewegt — die Regel ist offengelegt
        faden.sort(key=lambda e: rang[e["k"].pk])
    # Die Trennlinie „n neue Beiträge" steht genau einmal — vor dem ersten neuen Beitrag (FB-G2)
    for eintrag in faden:
        if eintrag["neu"]:
            eintrag["erster_neuer"] = True
            break
        treffer = next((a for a in eintrag["antworten"] if a["neu"]), None)
        if treffer is not None:
            treffer["erster_neuer"] = True
            break
    return {"faden": faden, "mehr": mehr, "mehr_ab": mehr_ab, "richtung": richtung, "ab": ab}


def faden(antrag, nutzer=None, nach_engagement: bool = False):
    """Der **ganze** laufende Faden — Wurzelbeiträge chronologisch, Antworten darunter.

    Die Seite zeigt ein Fenster (`faden_fenster`); hier gibt es alles auf einmal, für Rechnungen
    und Tests, die den vollständigen Stand brauchen."""
    return faden_fenster(antrag, nutzer, nach_engagement, grenze=None)["faden"]


def neue_zaehlen(antrag, nutzer) -> int:
    """Wie viele laufende Beiträge seit dem letzten Lesen dazugekommen sind — ohne die eigenen."""
    if nutzer is None or not nutzer.is_authenticated:
        return 0
    stand = Lesestand.objects.filter(mitglied=nutzer, antrag=antrag).first()
    if stand is None:
        return 0
    return (
        antrag.kommentare.filter(archiviert_am__isnull=True, erstellt_am__gt=stand.gelesen_bis)
        .exclude(mitglied=nutzer)
        .count()
    )


def gelesen_merken(antrag, nutzer, jetzt=None) -> None:
    """Den Lesestand vorrücken (FB-G2) — geräteübergreifend, nie rückwärts."""
    if nutzer is None or not nutzer.is_authenticated:
        return
    jetzt = jetzt or timezone.now()
    stand, neu = Lesestand.objects.get_or_create(
        mitglied=nutzer, antrag=antrag, defaults={"gelesen_bis": jetzt}
    )
    if not neu and stand.gelesen_bis < jetzt:
        stand.gelesen_bis = jetzt
        stand.save(update_fields=["gelesen_bis"])


def reaktion_umschalten(kommentar, mitglied, art=Reaktionsart.ZUSTIMMUNG, jetzt=None):
    """Zustimmen oder die Zustimmung zurücknehmen (FB-G1, D-G1: außerhalb des Abstimmungs-Chats
    nur Zustimmung, rein informativ — die Reihung bleibt chronologisch). Rückgabe: die Reaktion
    oder None, wenn sie zurückgenommen wurde."""
    vorhanden = Reaktion.objects.filter(kommentar=kommentar, mitglied=mitglied).first()
    if vorhanden is not None:
        if vorhanden.art == art:
            vorhanden.delete()
            return None
        vorhanden.art = art
        vorhanden.save(update_fields=["art"])
        return vorhanden
    return Reaktion.objects.create(
        kommentar=kommentar, mitglied=mitglied, art=art, erstellt_am=jetzt or timezone.now()
    )


def gespraeche(nutzer, grenze: int | None = -1) -> list[dict]:
    """Meine Gespräche für das Panel (FB-G3). `grenze=-1` nimmt den Registerwert, None hebt sie auf: je Paar (ich, Gegenüber) an einem Antrag eine Zeile.

    Ein Gespräch besteht, sobald eine Antwort zwischen uns liegt — von mir unter seinem Beitrag
    oder von ihm unter meinem. Es zählt nur der laufende Chat: Was archiviert ist, verschwindet
    aus der Liste und lebt im Archiv weiter (FB-G5). Neueste Aktivität zuerst."""
    if nutzer is None or not nutzer.is_authenticated:
        return []
    # Alle Antworten, an denen ich beteiligt bin — als Verfasser der Antwort oder des Wurzelbeitrags
    antworten = (
        Kommentar.objects.filter(archiviert_am__isnull=True, antwort_auf__isnull=False)
        .filter(Q(mitglied=nutzer) | Q(antwort_auf__mitglied=nutzer))
        .filter(mitglied__isnull=False, antwort_auf__mitglied__isnull=False)
        .exclude(Q(mitglied=nutzer) & Q(antwort_auf__mitglied=nutzer))  # Selbstgespräche zählen nicht
        .select_related("antrag", "mitglied", "antwort_auf__mitglied")
        .prefetch_related("antrag__kategorien")
        .order_by("-erstellt_am")
    )
    staende = {
        s.antrag_id: s.gelesen_bis for s in Lesestand.objects.filter(mitglied=nutzer)
    }
    zeilen: dict[tuple[int, int], dict] = {}
    for antwort in antworten:
        gegenueber = antwort.antwort_auf.mitglied if antwort.mitglied_id == nutzer.pk else antwort.mitglied
        schluessel = (antwort.antrag_id, gegenueber.pk)
        eintrag = zeilen.get(schluessel)
        if eintrag is None:
            gelesen = staende.get(antwort.antrag_id)
            fremd = antwort.mitglied_id != nutzer.pk
            zeilen[schluessel] = {
                "antrag": antwort.antrag,
                "thema": next(iter(antwort.antrag.kategorien.all()), None),
                "gegenueber": gegenueber,
                "letzter": antwort,
                "beitraege": 1,
                "ungelesen": bool(fremd and (gelesen is None or antwort.erstellt_am > gelesen)),
            }
        else:
            eintrag["beitraege"] += 1
    gereiht = sorted(zeilen.values(), key=lambda z: z["letzter"].erstellt_am, reverse=True)
    if grenze == -1:  # Vorgabe: die Zahl steht im Register (FB-J2)
        from parameter.models import zahl

        grenze = zahl("gespraeche-liste-hoechstzahl", 30)
    return gereiht[:grenze] if grenze else gereiht


def ungelesene_gespraeche(nutzer) -> int:
    """Der Zähler am Griff (FB-G3) — über **alle** Gespräche, nicht nur die angezeigten.

    Die Liste im Panel ist auf `grenze` gekürzt; der Zähler darf das nicht sein. Sonst zeigt
    er ausgerechnet dann zu wenig, wenn viel los ist — und verschweigt die Gespräche, für die
    er da wäre."""
    return sum(1 for g in gespraeche(nutzer, grenze=None) if g["ungelesen"])


# ── Der Abstimmungs-Chat zum Vorschlag des Expertenrats (FB-G6) ──────────────────────────


def passt_alles_text() -> str:
    """Der Wortlaut des Systembeitrags — hier, damit er an einer Stelle steht."""
    return str(_("✓ Passt alles — der Vorschlag kann so zur Endabstimmung."))


def passt_alles_anlegen(antrag, entwurf, jetzt=None) -> Kommentar:
    """Beim Öffnen des Abstimmungs-Chats legt die Plattform den Beitrag an, auf den sich
    die Auswertung bezieht (FB-G6) — ohne Verfasser, deutlich als Systembeitrag.

    Idempotent: Ein zweiter Aufruf in derselben Runde gibt den vorhandenen Beitrag zurück."""
    jetzt = jetzt or timezone.now()
    phase = f"vorschlag-r{entwurf.runde}"
    vorhanden = antrag.kommentare.filter(system=True, phase=phase, archiviert_am__isnull=True).first()
    if vorhanden is not None:
        return vorhanden
    return Kommentar.objects.create(
        antrag=antrag, mitglied=None, text=passt_alles_text(), phase=phase, system=True, erstellt_am=jetzt,
    )


def darf_reagieren(antrag, mitglied) -> bool:
    """Im Abstimmungs-Chat reagieren nur die Unterstützer des Antrags — das ist ihre
    Abstimmung über den Vorschlag (A0-03, § 5 Abs 12). Sonst darf jedes Mitglied zustimmen."""
    if mitglied is None or not mitglied.is_authenticated:
        return False
    if abstimmungschat(antrag) is None:
        return True
    return antrag.unterstuetzungen.filter(mitglied=mitglied, zurueckgezogen_am__isnull=True).exists()


def abstimmung_stand(antrag, entwurf=None, schwelle: float | None = None) -> dict | None:
    """Die Rechnung des Abstimmungs-Chats (FB-G6) — offen, damit sie jeder nachvollziehen kann.

    Gibt None zurück, wenn gerade kein Vorschlag zur Abstimmung steht."""
    entwurf = entwurf or abstimmungschat(antrag)
    if entwurf is None:
        return None
    if schwelle is None:
        from parameter.models import zahl

        schwelle = zahl("vorschlag-annahme-prozent", 50) / 100
    beitraege = [
        {"id": k.pk, "ja": k.zustimmungen, "nein": k.ablehnungen,
         "zeit": k.erstellt_am, "system": k.system, "ist_kritik": k.ist_kritik, "text": k.sichtbarer_text(),
         "absatz": k.bezug_absatz}
        for k in mit_zaehlern(
            antrag.kommentare.filter(archiviert_am__isnull=True, phase=f"vorschlag-r{entwurf.runde}")
        ).order_by("erstellt_am", "pk")
    ]
    ergebnis = vorschlagschat.auswerten(beitraege, schwelle)
    ergebnis["kritik"] = vorschlagschat.kritik_uebergeben(beitraege)
    ergebnis["runde"] = entwurf.runde
    return ergebnis


def kritik_der_runde(antrag, runde: int) -> list[dict]:
    """Die Kritik-Beiträge einer Vorschlagsrunde — auch die schon archivierten (FB-G6).

    Sie sind die „Wünsche der Unterstützer", mit denen der Expertenrat in die nächste Runde
    geht; gereiht nach Engagement, damit oben steht, was die meisten bewegt."""
    beitraege = [
        {"id": k.pk, "ja": k.zustimmungen, "nein": k.ablehnungen,
         "zeit": k.erstellt_am, "system": k.system, "ist_kritik": k.ist_kritik,
         "text": k.sichtbarer_text(), "absatz": k.bezug_absatz,
         "name": k.mitglied.anzeigename if k.mitglied_id else ""}
        for k in mit_zaehlern(antrag.kommentare.filter(phase=f"vorschlag-r{runde}", ist_kritik=True))
        .select_related("mitglied").order_by("erstellt_am", "pk")
    ]
    return vorschlagschat.kritik_uebergeben(beitraege)
