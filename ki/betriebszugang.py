"""Ein gemeinsamer nicht wartender Datenbankzugang vor tatsächlichen Anbieteraufrufen.

Keine TTL, die einen noch laufenden Anbieter parallel freigibt. Die Datenbank löst
die Transaktionssperre auch beim Verbindungs-/Prozessabbruch. Ein Betriebsflag schützt
zusätzlich verschachtelte Aufrufe derselben Verbindung; es ist kein Verbrauchsnachweis.
"""

from functools import wraps

from django.db import OperationalError, transaction
from django.utils.translation import gettext_lazy as _

from ki.anbieter import SteckplatzStumm

NAME = "anbieter"


class SteckplatzWartet(SteckplatzStumm):
    """Der Anbieter wurde nicht aufgerufen; kein verbrauchter Anbieter-Versuch."""


class SteckplatzBelegt(SteckplatzWartet):
    """Eine andere Rechnung hält den gemeinsamen betrieblichen Zugang."""


def _sperrkonflikt(fehler):
    ursprung = fehler.__cause__
    if getattr(ursprung, "sqlstate", None) == "55P03" or getattr(ursprung, "pgcode", None) == "55P03":
        return True
    code = getattr(ursprung, "sqlite_errorcode", None)
    return isinstance(code, int) and code & 255 in {5, 6}


def einzeln(funktion):
    @wraps(funktion)
    def ausfuehren(*args, **kwargs):
        from ki.models import SteckplatzZugang

        begonnen, fehler, ergebnis = False, None, None
        try:
            # Die Migration legt diese rein betriebliche Zeile an. Nach einem lokalen
            # Test-Flush kann sie idempotent wiederhergestellt werden; kein Archiv-Upsert.
            SteckplatzZugang.objects.get_or_create(name=NAME)
            with transaction.atomic():
                zugang = SteckplatzZugang.objects.select_for_update(nowait=True).get(name=NAME)
                if zugang.belegt or not SteckplatzZugang.objects.filter(name=NAME, belegt=False).update(belegt=True):
                    raise SteckplatzBelegt(_("Der Modell-Steckplatz ist bereits belegt. Dieser Aufruf wartet auf einen freien Zugang."))
                begonnen = True
                try:
                    # Monatsverbrauch erst hinter dem gemeinsamen Zugang erneut lesen.
                    ergebnis = funktion(*args, **kwargs)
                except SteckplatzStumm as ausfall:
                    # Insbesondere ein bereits angelegter Anbieter-Fehllauf muss zuerst
                    # committet werden. Die Stumm-Meldung darf ihn nicht zurückrollen.
                    fehler = ausfall
                # Bei unerwartetem Fehler lässt atomic die Flagänderung zurückrollen;
                # keine Folgeabfrage in einer bereits gebrochenen Transaktion beginnen.
                SteckplatzZugang.objects.filter(name=NAME).update(belegt=False)
        except OperationalError as konflikt:
            if not begonnen and _sperrkonflikt(konflikt):
                raise SteckplatzBelegt(_("Der Modell-Steckplatz ist bereits belegt. Dieser Aufruf wartet auf einen freien Zugang.")) from konflikt
            raise
        if fehler is not None:
            raise fehler
        return ergebnis
    return ausfuehren
