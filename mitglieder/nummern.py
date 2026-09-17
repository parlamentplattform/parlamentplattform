"""Mitgliedsnummern sind dauerhaft und unabhängig von technischen Konto-IDs."""
from django.db import transaction
from django.db.models import F

from mitglieder.models import Mitglied, Mitgliedsnummernkreis


def sicherstellen(mitglied):
    if mitglied.testkonto:
        return None
    if mitglied.mitgliedsnummer is not None:
        return mitglied.mitgliedsnummer
    with transaction.atomic():
        Mitgliedsnummernkreis.objects.get_or_create(pk=1)
        # UPDATE sperrt denselben Zähler auch bei parallelen Erstvergaben.
        Mitgliedsnummernkreis.objects.filter(pk=1).update(naechste=F("naechste") + 1)
        m = Mitglied.objects.get(pk=mitglied.pk)
        if m.testkonto:
            raise ValueError("Testkonten erhalten keine Mitgliedsnummer.")
        if m.mitgliedsnummer is None:
            m.mitgliedsnummer = Mitgliedsnummernkreis.objects.get(pk=1).naechste - 1
            m.save(update_fields=["mitgliedsnummer"])
        else:
            Mitgliedsnummernkreis.objects.filter(pk=1).update(naechste=F("naechste") - 1)
        mitglied.mitgliedsnummer = m.mitgliedsnummer
    return mitglied.mitgliedsnummer
