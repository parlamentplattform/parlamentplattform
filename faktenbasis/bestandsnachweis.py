"""Ein SELECT, ein Datenbank-Abfragezustand; keine Abrufe oder Schreibwirkungen."""

from django.db.models import F, Value
from django.utils import timezone

from faktenbasis.models import Norm, NormText, PersonalAggregat, PersonalRessorttabelle
from parameter.models import Parameter
from plattform_core.faktenbestand import TECHNISCHE_HOECHSTZAHL, BestandsFehler, nachweis

REGISTER = "faktenbasis-bestandsnachweis-hoechstzahl"
STANDARD = 2000


def bestandsnachweis() -> dict:
    # Hier bewusst strenger als zahl(): Ein unlesbarer vorhandener Wert darf
    # die abgeschaltete/defekte Betriebsgrenze nicht durch einen Rückfall öffnen.
    wert = Parameter.objects.filter(schluessel=REGISTER).values_list("wert", flat=True).first()
    try:
        grenze = STANDARD if wert is None else int(wert)
    except (ValueError, TypeError) as exc:
        raise BestandsFehler("grenze") from exc
    if type(grenze) is not int or not 0 < grenze <= TECHNISCHE_HOECHSTZAHL:
        raise BestandsFehler("grenze")
    teile = [
        modell.objects.order_by().annotate(sammlung=Value(art), nummer=F("pk"),
                                         pruefsumme=F(hashfeld)).values("sammlung", "nummer", "pruefsumme")
        for modell, art, hashfeld in (
            (Norm, "norm", "inhalt_hash"),
            (NormText, "normtext", "xml_hash"),
            (PersonalAggregat, "personalaggregat", "original_sha256"),
            (PersonalRessorttabelle, "personalressorttabelle", "original_sha256"),
        )
    ]
    # Erst begrenzt lesen, danach rein sortieren: kein unnötiger Sortierlauf
    # über einen bereits zu großen Gesamtbestand. Der Überlauffall hat kein Ergebnis.
    zeilen = teile[0].union(*teile[1:], all=True)[:grenze + 1]
    stand = nachweis(zeilen.iterator(), grenze)
    return {**stand, "erstellt_am": timezone.now().isoformat(), "hoechstzahl": grenze}
