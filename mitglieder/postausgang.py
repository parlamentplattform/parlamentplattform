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
#: Kontobriefe: gehören zum Konto und gehen ohne E-Mail-Einwilligung — sofort nach dem Commit.
KONTO_ARTEN = ("willkommen", "freischaltung", *VORSCHAU_ARTEN)
#: Verfahrenspost: nur mit `Mitglied.post_einwilligung`, je Anlass (`bezug`) genau einmal; sie wird nur
#: angelegt und vom Hintergrundlauf zugestellt — ein Antrag löst nie hunderte SMTP-Sendungen in einer
#: Anfrage aus.
EINWILLIGUNG_ARTEN = ("neuer_antrag", "beitragserinnerung", "rechtsbezug")
#: Verfahrenspost, die zu einem Antrag gehört: Bezug `antrag:<pk>`, Auftrag mit Antrag.
ANTRAGS_ARTEN = ("neuer_antrag", "rechtsbezug")
#: Grenze der Maschine, keine Verfahrensgröße: Nach so vielen gescheiterten Versuchen (2, 4, 8, 16, 32
#: Minuten, danach stündlich — zusammen rund 20 Stunden) gibt der Postausgang die Verfahrenspost auf und
#: stempelt den Auftrag als erledigt ohne Versand (nicht gelöscht). Eine dauerhaft abgewiesene Adresse
#: liefe sonst je Antrag und je Jahr stündlich und ohne Ende und belegte vorne den Durchsatz. Die
#: Kontobriefe bleiben ohne Grenze: Sie gehören zum Konto und sind wenige.
HOECHSTVERSUCHE_VERFAHRENSPOST = 24


def _empfangsbereit(mitglied) -> bool:
    """Testkonten, inaktive, ausgetretene und ausgeschlossene Konten und Konten ohne Adresse bekommen nichts."""
    return bool(
        not mitglied.testkonto
        and mitglied.is_active
        and mitglied.email
        and mitglied.status not in (Mitgliedsstatus.AUSGETRETEN, Mitgliedsstatus.AUSGESCHLOSSEN)
    )


def beauftragen(mitglied, art, antrag=None, bezug=""):
    """Legt den Auftrag an (True) — oder nicht (False): schon beauftragt, schon versendet, für dieses
    Konto nicht zulässig oder ohne die nötige Einwilligung. `antrag` und `bezug` gehören zur Verfahrenspost:
    `neuer_antrag` und `rechtsbezug` brauchen den Antrag (Bezug `antrag:<pk>`), `beitragserinnerung` den
    Bezug `jahr:<Jahr>`."""
    if art not in (*KONTO_ARTEN, *EINWILLIGUNG_ARTEN):
        raise ValueError("Unbekannte Postart")
    if art in ANTRAGS_ARTEN:
        if antrag is None:
            raise ValueError(f"„{art}“ braucht den Antrag")
        bezug = bezug or f"antrag:{antrag.pk}"
    elif art == "beitragserinnerung" and not bezug:
        raise ValueError("„beitragserinnerung“ braucht den Bezug jahr:<Jahr>")
    stempel = art + "_post_am" if art in ("willkommen", "freischaltung") else None
    if not _empfangsbereit(mitglied) or (stempel and getattr(mitglied, stempel) is not None):
        return False
    if art in EINWILLIGUNG_ARTEN and not mitglied.post_einwilligung:
        return False
    if art == "freischaltung" and mitglied.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT:
        return False
    auftrag, neu = Postauftrag.objects.get_or_create(
        mitglied=mitglied, art=art, bezug=bezug, defaults={"antrag": antrag if art in ANTRAGS_ARTEN else None}
    )
    if auftrag.erledigt:
        return False
    if art in KONTO_ARTEN:
        transaction.on_commit(lambda: zustellen(auftrag.pk))
    return neu


def zustellen(pk, jetzt=None):
    from mitglieder.post import (
        _ausweis_anhang,
        _freischaltung_brief,
        _senden,
        _willkommen_brief,
        beitragserinnerung_brief,
        neuer_antrag_brief,
        rechtsbezug_brief,
    )

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
        if not _empfangsbereit(m):
            update["erledigt"] = True
            return False
        if a.art in EINWILLIGUNG_ARTEN:
            if not m.post_einwilligung:
                # Einwilligung seit der Beauftragung zurückgenommen: kein Brief, Auftrag gestempelt (nicht gelöscht).
                update["erledigt"] = True
                return False
            if a.art == "neuer_antrag":
                ok = neuer_antrag_brief(m, a.antrag)
            elif a.art == "rechtsbezug":
                ok = rechtsbezug_brief(m, a.antrag)
            else:
                ok = beitragserinnerung_brief(m)
            if ok:
                update.update(versandt_am=jetzt, erledigt=True)
            return ok
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
        if a.art in EINWILLIGUNG_ARTEN and not update.get("erledigt") and a.versuche >= HOECHSTVERSUCHE_VERFAHRENSPOST:
            log.warning("Postauftrag %s nach %s Versuchen ohne Versand abgeschlossen", pk, a.versuche)
            update["erledigt"] = True
        update.update(sperrcode="", gesperrt_bis=None,
                      naechster_versuch=jetzt + timedelta(minutes=min(60, 2 ** min(a.versuche, 6))))
        Postauftrag.objects.filter(pk=pk, sperrcode=token).update(**update)


def offene_zustellen():
    jetzt = timezone.now()
    ids = list(Postauftrag.objects.filter(erledigt=False).filter(
        Q(naechster_versuch__isnull=True) | Q(naechster_versuch__lte=jetzt)
    ).order_by("pk").values_list("pk", flat=True)[:50])
    return sum(bool(zustellen(pk, jetzt)) for pk in ids)
