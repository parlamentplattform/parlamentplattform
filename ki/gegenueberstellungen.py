"""Ausdrückliche private Textgegenüberstellung; kein Entscheid über Einbringen."""

import hashlib
import logging

from django.utils import timezone

from ki.anbieter import SteckplatzStumm
from ki.auftraege import auftrag_laden
from ki.models import KILauf, Vergleichsanfrage, Zweck, lauf_ausfuehren
from ki.vergleichsanfragen import anlegen, kennung_lesen, reservieren
from ki.vergleichskontext import eingabe, festhalten, pruefen
from mitglieder.botschutz import drossel_zuviel
from parameter.models import zahl
from plattform_core.gegenueberstellung import pruefen as antwort_pruefen

log = logging.getLogger(__name__)


def anfordern(daten, mitglied, pruefstand, token):
    """Genau diese Anforderung einmal beginnen; Doppel-POST ist keine neue Anforderung."""
    from verfahren.hinweise import mitwirkungssperre

    if mitwirkungssperre(mitglied):
        raise ValueError("Dieses Konto darf derzeit keine Textgegenüberstellung anfordern.")
    kennung = kennung_lesen(token, daten, mitglied, pruefstand)
    rahmen = festhalten(daten, mitglied, pruefstand,
                       hoechstzeichen=max(1, min(100000, zahl("gegenueberstellung-textzeichen", 20000))),
                       hoechstpaare=max(1, min(20, zahl("gegenueberstellung-hoechstpaare", 3))))
    anfrage, _ = anlegen(kennung, rahmen, mitglied)
    if not reservieren(anfrage, mitglied):
        anfrage.refresh_from_db()
        return anfrage
    if drossel_zuviel(None, "gegenueberstellung", max(0, zahl("gegenueberstellung-je-stunde", 5)),
                     kennung=f"konto:{mitglied.pk}"):
        Vergleichsanfrage.objects.filter(pk=anfrage.pk).update(
            status="ohne_ergebnis", meldung="stundengrenze", beendet_am=timezone.now())
    else:
        auftrag = auftrag_laden(Zweck.GEGENUEBERSTELLUNG, nummer=1)
        try:
            lauf = lauf_ausfuehren(
                Zweck.GEGENUEBERSTELLUNG, auftrag.text, anfrage.eingabe, mitglied,
                auftrag_version=auftrag.version,
                kontext={"vergleichsanfrage": str(anfrage.pk), "vergleich": anfrage.kontext},
                zeitgrenze=max(1, min(45, zahl("gegenueberstellung-zeitgrenze-sekunden", 8))),
            )
        except SteckplatzStumm:
            fehlauf = KILauf.objects.filter(
                zweck=Zweck.GEGENUEBERSTELLUNG, angefordert_von=mitglied,
                kontext__vergleichsanfrage=str(anfrage.pk), erfolgreich=False,
            ).order_by("pk").first()
            Vergleichsanfrage.objects.filter(pk=anfrage.pk).update(
                status="ohne_ergebnis", meldung="steckplatz_stumm", lauf=fehlauf, beendet_am=timezone.now())
        except Exception as fehler:
            # Kein automatischer zweiter Versuch nach unbekanntem Abbruch. Der
            # bereits reservierte private Stand bleibt für die Nachlese erhalten.
            log.error("Textgegenüberstellung technisch abgebrochen (%s)", type(fehler).__name__)
            Vergleichsanfrage.objects.filter(pk=anfrage.pk).update(
                status="ohne_ergebnis", meldung="technik", beendet_am=timezone.now())
        else:
            Vergleichsanfrage.objects.filter(pk=anfrage.pk).update(
                status="fertig", lauf=lauf, beendet_am=timezone.now())
    anfrage.refresh_from_db()
    return anfrage


def auswertung(anfrage, mitglied):
    """Ausschließlich den eigenen belegten Input/Prompt und seine unveränderte Antwort lesen."""
    if anfrage.angefordert_von_id != mitglied.pk:
        raise ValueError("Private Textgegenüberstellung gehört zu einem anderen Konto.")
    grund = {"gueltig": False, "vergleiche": [], "anfrage": anfrage,
             "modell": "", "stand": anfrage.erstellt_am, "meldung": anfrage.meldung or anfrage.status}
    lauf = anfrage.lauf
    if lauf is None or not lauf.erfolgreich:
        return grund
    d = pruefen(anfrage.kontext)
    text = eingabe(anfrage.kontext)
    if (anfrage.eingabe != text or hashlib.sha256(text.encode("utf-8")).hexdigest() != anfrage.eingabe_sha256
            or lauf.eingabe != text or lauf.zweck != Zweck.GEGENUEBERSTELLUNG or lauf.antrag_id is not None
            or lauf.angefordert_von_id != mitglied.pk or lauf.auftrag_version != "gegenueberstellung-v1"
            or lauf.kontext != {"vergleichsanfrage": str(anfrage.pk), "vergleich": anfrage.kontext}):
        return {**grund, "meldung": "eingabebindung"}
    antwort = antwort_pruefen(lauf.antwort, paare=[(p["antrag"], p["fassung"]) for p in d["gegenueber"]])
    if not antwort["gueltig"]:
        return {**grund, "meldung": "antwortform", "modell": lauf.modell}
    return {**grund, **antwort, "modell": lauf.modell, "meldung": "",
            "vergleiche": [{**v, "titel": p["titel"]} for v, p in zip(antwort["vergleiche"], d["gegenueber"], strict=True)]}
