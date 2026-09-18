"""Dauerhafter Postausgang mit atomarer Reservierung und begrenzter Rückstellung.

SMTP garantiert keine Exactly-once-Zustellung: Geht nach Annahme durch den Server
aber vor unserem Erfolgsstempel der Prozess verloren, kann ein erneuter Versuch
nötig sein. Erfolgreich verbuchte Briefe werden nicht wiederholt; eine fehlende
PDF-Beilage wird getrennt nachgeliefert. Der Auftrag speichert keine Mailadresse.
"""
import logging
import secrets
from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q
from django.utils import timezone, translation
from django.utils.translation import gettext as _

from mitglieder.models import Identitaetsstufe, Mitgliedsstatus, Postauftrag

log = logging.getLogger(__name__)
AUSWEIS_VORSCHAU = "ausweis_vorschau_4"
VORSCHAU_ARTEN = ("ausweis_vorschau", "ausweis_vorschau_2", "ausweis_vorschau_3", AUSWEIS_VORSCHAU)


def beauftragen(mitglied, art):
    if art not in ("willkommen", "freischaltung", *VORSCHAU_ARTEN):
        raise ValueError("Unbekannte Postart")
    stempel = None if art in VORSCHAU_ARTEN else art + "_post_am"
    if (mitglied.testkonto or not mitglied.is_active or not mitglied.email
        or mitglied.status in (Mitgliedsstatus.AUSGETRETEN, Mitgliedsstatus.AUSGESCHLOSSEN)
        or (stempel and getattr(mitglied, stempel) is not None)):
        return False
    if art == "freischaltung" and mitglied.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT:
        return False
    auftrag, neu = Postauftrag.objects.get_or_create(mitglied=mitglied, art=art)
    if auftrag.erledigt:
        return False
    transaction.on_commit(lambda: zustellen(auftrag.pk))
    return neu


def zustellen(pk, jetzt=None):
    from mitglieder.post import _ausweis_anhang, _freischaltung_brief, _senden, _willkommen_brief

    jetzt = jetzt or timezone.now()
    token = secrets.token_hex(16)
    frei = Q(gesperrt_bis__isnull=True) | Q(gesperrt_bis__lte=jetzt)
    faellig = Q(naechster_versuch__isnull=True) | Q(naechster_versuch__lte=jetzt)
    qs = Postauftrag.objects.filter(pk=pk, erledigt=False).filter(frei, faellig)
    if not qs.update(sperrcode=token, gesperrt_bis=jetzt + timedelta(minutes=5), versuche=F("versuche") + 1):
        return False
    a = Postauftrag.objects.select_related("mitglied").get(pk=pk)
    m = a.mitglied
    update = {}
    try:
        if (m.testkonto or not m.is_active or not m.email or m.status in
            (Mitgliedsstatus.AUSGETRETEN, Mitgliedsstatus.AUSGESCHLOSSEN)):
            update["erledigt"] = True
            return False
        if a.art == "freischaltung" and m.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT:
            return False
        anhang = _ausweis_anhang(m)
        if a.art in VORSCHAU_ARTEN:
            if anhang is None:
                return False
            brief = _willkommen_brief if m.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT else _freischaltung_brief
            ok = brief(m, anhang, vorschau=True)
            if ok:
                update.update(versandt_am=jetzt, anhang_versandt_am=jetzt, erledigt=True)
            return ok
        if a.versandt_am is None:
            senden = _willkommen_brief if a.art == "willkommen" else _freischaltung_brief
            ok = senden(m, anhang)
        elif anhang is not None:
            with translation.override("de"):
                ok = _senden(m, "ausweis_nachlieferung",
                    _("Ihr Mitgliedsausweis – ParlamentPlattform"),
                    _("Im Anhang erhalten Sie Ihren Mitgliedsausweis. Den aktuellen Stand finden Sie in Ihrem Profil."),
                    anhang)
        else:
            ok = False
        if ok:
            update["versandt_am"] = a.versandt_am or jetzt
            if anhang is not None:
                update.update(anhang_versandt_am=jetzt, erledigt=True)
            m.__class__.objects.filter(pk=m.pk).update(**{a.art + "_post_am": update["versandt_am"]})
        return ok
    except Exception:
        log.exception("Postauftrag %s fehlgeschlagen", pk)
        return False
    finally:
        update.update(sperrcode="", gesperrt_bis=None,
                      naechster_versuch=jetzt + timedelta(minutes=min(60, 2 ** min(a.versuche, 6))))
        Postauftrag.objects.filter(pk=pk, sperrcode=token).update(**update)


def offene_zustellen():
    jetzt = timezone.now()
    ids = list(Postauftrag.objects.filter(erledigt=False).filter(
        Q(naechster_versuch__isnull=True) | Q(naechster_versuch__lte=jetzt)
    ).order_by("pk").values_list("pk", flat=True)[:50])
    return sum(bool(zustellen(pk, jetzt)) for pk in ids)
