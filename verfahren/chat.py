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

from django.db.models import Q
from django.utils import timezone

from verfahren.models import Kommentar, Lesestand, Reaktion, Reaktionsart


class ChatGesperrt(Exception):
    """Der Chat dieses Antrags nimmt gerade keine Beiträge an."""


def chat_offen(antrag) -> bool:
    """Geschrieben wird, solange das Verfahren läuft. Nach dem Ende bleibt das Archiv lesbar.

    Während der Expertenrat am Vorschlag arbeitet, ruht der Chat (FB-G6) — diese Sperre kommt
    mit dem Abstimmungs-Chat (S7); bis dahin gilt allein die Phase."""
    from plattform_core import Phase

    return antrag.phase in (Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value)


def beitrag_schreiben(antrag, mitglied, text: str, antwort_auf=None, jetzt=None) -> Kommentar:
    """Der einzige Schreibweg für Chat-Beiträge (FB-G1).

    Der Beitrag merkt sich die Phase, in der er entsteht — daraus lebt die Archivierung.
    Eine Antwort hängt immer am Wurzelbeitrag ihres Fadens und nur an einem Beitrag desselben,
    noch nicht archivierten Antrags."""
    jetzt = jetzt or timezone.now()
    if not chat_offen(antrag):
        raise ChatGesperrt("Das Verfahren ist beendet — der Chat ist nur noch im Archiv lesbar.")
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
        text=text[:4000],
        antwort_auf=wurzel,
        phase=antrag.phase,
        erstellt_am=jetzt,
    )


def faden(antrag, nutzer=None):
    """Die laufenden Beiträge als Faden: Wurzelbeiträge chronologisch, Antworten darunter.

    Jeder Eintrag trägt, was die Anzeige braucht — eigene Reaktion, Zahl der Zustimmungen,
    ob er neu ist. `neu` bezieht sich auf den Lesestand des Mitglieds (FB-G2)."""
    beitraege = list(
        antrag.kommentare.filter(archiviert_am__isnull=True)
        .select_related("mitglied")
        .prefetch_related("reaktionen")
        .order_by("erstellt_am")
    )
    gelesen_bis = None
    meine = set()
    if nutzer is not None and nutzer.is_authenticated:
        stand = Lesestand.objects.filter(mitglied=nutzer, antrag=antrag).first()
        gelesen_bis = stand.gelesen_bis if stand else None
        meine = {
            r.kommentar_id
            for r in Reaktion.objects.filter(mitglied=nutzer, kommentar__antrag=antrag)
        }

    def schmuecken(k: Kommentar) -> dict:
        return {
            "k": k,
            "zustimmungen": sum(1 for r in k.reaktionen.all() if r.art == Reaktionsart.ZUSTIMMUNG),
            "ich_zustimme": k.pk in meine,
            "neu": bool(gelesen_bis and k.erstellt_am > gelesen_bis and k.mitglied_id != getattr(nutzer, "pk", None)),
            "eigener": nutzer is not None and getattr(nutzer, "pk", None) == k.mitglied_id,
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
    # Die Trennlinie „n neue Beiträge" steht genau einmal — vor dem ersten neuen Beitrag (FB-G2)
    for eintrag in faden:
        if eintrag["neu"]:
            eintrag["erster_neuer"] = True
            break
        treffer = next((a for a in eintrag["antworten"] if a["neu"]), None)
        if treffer is not None:
            treffer["erster_neuer"] = True
            break
    return faden


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


def gespraeche(nutzer, grenze: int = 30) -> list[dict]:
    """Meine Gespräche für das Panel (FB-G3): je Paar (ich, Gegenüber) an einem Antrag eine Zeile.

    Ein Gespräch besteht, sobald eine Antwort zwischen uns liegt — von mir unter seinem Beitrag
    oder von ihm unter meinem. Es zählt nur der laufende Chat: Was archiviert ist, verschwindet
    aus der Liste und lebt im Archiv weiter (FB-G5). Neueste Aktivität zuerst."""
    if nutzer is None or not nutzer.is_authenticated:
        return []
    # Alle Antworten, an denen ich beteiligt bin — als Verfasser der Antwort oder des Wurzelbeitrags
    antworten = (
        Kommentar.objects.filter(archiviert_am__isnull=True, antwort_auf__isnull=False)
        .filter(Q(mitglied=nutzer) | Q(antwort_auf__mitglied=nutzer))
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
    return sorted(zeilen.values(), key=lambda z: z["letzter"].erstellt_am, reverse=True)[:grenze]


def ungelesene_gespraeche(nutzer) -> int:
    """Der Zähler am Griff (FB-G3)."""
    return sum(1 for g in gespraeche(nutzer) if g["ungelesen"])
