"""Ein SELECT, ein Datenbank-Abfragezustand; keine Abrufe oder Schreibwirkungen."""

from django.db.models import F, Value
from django.utils import timezone

from faktenbasis.models import (
    Kundmachungsnachweis,
    Norm,
    NormText,
    PersonalAggregat,
    PersonalRessorttabelle,
    RisAenderungsseite,
    VfghEntscheidungsstand,
)
from parameter.models import Parameter
from plattform_core.faktenbestand import TECHNISCHE_HOECHSTZAHL, BestandsFehler, nachweis

REGISTER = "faktenbasis-bestandsnachweis-hoechstzahl"
STANDARD = 2000
#: Ab welchem Anteil der Nachweisgrenze (in Prozent) die Verwaltung gewarnt wird (GP-147).
#: Registerwert folgt; 100 warnt erst, wenn der nächste Import den Nachweis ausfallen ließe.
WARNANTEIL_PROZENT = 100


def bestandsgrenze() -> int:
    # Hier bewusst strenger als zahl(): Ein unlesbarer vorhandener Wert darf
    # die abgeschaltete/defekte Betriebsgrenze nicht durch einen Rückfall öffnen.
    wert = Parameter.objects.filter(schluessel=REGISTER).values_list("wert", flat=True).first()
    try:
        grenze = STANDARD if wert is None else int(wert)
    except (ValueError, TypeError) as exc:
        raise BestandsFehler("grenze") from exc
    if type(grenze) is not int or not 0 < grenze <= TECHNISCHE_HOECHSTZAHL:
        raise BestandsFehler("grenze")
    return grenze


SAMMLUNGEN = (
    (Norm, "norm", "inhalt_hash"),
    (NormText, "normtext", "xml_hash"),
    (Kundmachungsnachweis, "kundmachung", "original_sha256"),
    (PersonalAggregat, "personalaggregat", "original_sha256"),
    (PersonalRessorttabelle, "personalressorttabelle", "original_sha256"),
    (VfghEntscheidungsstand, "vfgh_metadaten", "original_sha256"),
    (RisAenderungsseite, "ris_aenderungsseite", "original_sha256"),
)


def bestandszahl() -> int:
    """Alle Schnappschüsse, die der Nachweis zählt — dieselben Sammlungen wie `bestandsnachweis`."""
    return sum(modell.objects.order_by().count() for modell, _art, _hash in SAMMLUNGEN)


def grenzstand() -> dict:
    """Bestand gegen Nachweisgrenze für Verwaltung und Fehlerkarte (GP-147). `grenze` ist None, wenn
    der Registerwert ungültig oder 0 ist; dann gibt es ohnehin keinen Nachweis."""
    bestand = bestandszahl()
    try:
        grenze = bestandsgrenze()
    except BestandsFehler:
        return {"bestand": bestand, "grenze": None, "warnung": False, "ausfall": True}
    return {"bestand": bestand, "grenze": grenze, "ausfall": bestand > grenze,
            "warnung": bestand * 100 >= grenze * WARNANTEIL_PROZENT}


def bestandsnachweis() -> dict:
    grenze = bestandsgrenze()
    teile = [
        modell.objects.order_by().annotate(sammlung=Value(art), nummer=F("pk"),
                                         pruefsumme=F(hashfeld)).values("sammlung", "nummer", "pruefsumme")
        for modell, art, hashfeld in SAMMLUNGEN
    ]
    # Erst begrenzt lesen, danach rein sortieren: kein unnötiger Sortierlauf
    # über einen bereits zu großen Gesamtbestand. Der Überlauffall hat kein Ergebnis.
    zeilen = teile[0].union(*teile[1:], all=True)[:grenze + 1]
    stand = nachweis(zeilen.iterator(), grenze)
    return {**stand, "erstellt_am": timezone.now().isoformat(), "hoechstzahl": grenze}
