"""Ausdrückliche Nachrechnung durch zuständige Gruppe1, getrennt vom Original."""

import json

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from ki.korrekturkontext import festhalten, pruefen
from ki.models import Auftragsstatus, KIAuftrag, KILauf, Zweck


def darf_anfordern(mitglied, antrag):
    from gremien.models import Gremium, Rolle
    from verfahren.hinweise import mitwirkungssperre

    return bool(getattr(mitglied, "is_authenticated", False) and mitglied.darf_mitwirken and not mitwirkungssperre(mitglied)
                and Rolle.hat_fuer(mitglied, Gremium.EXPERTENRAT_1, antrag))


def _ursprung(beanstandung):
    lauf = beanstandung.lauf
    if (lauf is None or lauf.antrag_id != beanstandung.antrag_id
            or lauf.zweck != Zweck.RECHTSBEZUG or not lauf.erfolgreich):
        raise ValueError("Kein öffentlicher erfolgreicher Rechtsbezug.")
    rahmen = festhalten(beanstandung, lauf)
    k = lauf.kontext
    job = KIAuftrag.objects.filter(
        pk=k.get("auftrag"), antrag_id=beanstandung.antrag_id, zweck=Zweck.RECHTSBEZUG,
        lauf=lauf, beanstandung__isnull=True, status=Auftragsstatus.ERLEDIGT,
    ).first()
    if job is None or job.kontext != rahmen["text"] or job.quellenkontext != rahmen["quellen"]:
        raise ValueError("Kein eindeutiger öffentlicher Ursprungsauftrag.")
    pruefen(rahmen)
    return lauf, job, rahmen


@transaction.atomic
def anfordern(beanstandung, mitglied):
    from verfahren.models import AuditEintrag, Beanstandung

    # Aus der Datenbank lesen, keine übergebenen veränderten Python-Objekte übernehmen.
    b = Beanstandung.objects.select_related("antrag", "lauf").get(pk=beanstandung.pk)
    if not darf_anfordern(mitglied, b.antrag):
        raise PermissionError("Nur die für diesen Antrag zuständige aktive Gruppe1 darf eine Nachrechnung anfordern.")
    vorhanden = KIAuftrag.objects.filter(beanstandung=b).first()
    if vorhanden:
        return vorhanden
    try:
        lauf, alt, rahmen = _ursprung(b)
    except (ValueError, KeyError, TypeError) as fehler:
        raise ValidationError(_("Für diese Beanstandung fehlt ein eindeutig festgehaltener öffentlicher Rechtsbezug. Es wird nichts nachträglich ergänzt.")) from fehler
    auftrag, neu = KIAuftrag.objects.get_or_create(beanstandung=b, defaults={
        "zweck": Zweck.KORREKTUR, "antrag": b.antrag, "angefordert_von": mitglied,
        "ursprung": lauf, "korrekturkontext": rahmen, "kontext": rahmen["text"],
        "quellenkontext": rahmen["quellen"], "quellenart": alt.quellenart,
        "fassung_nummer": alt.fassung_nummer, "vorschlagsfassung": alt.vorschlagsfassung,
    })
    if neu:
        AuditEintrag.anhaengen({"typ": "ki_korrektur_angefordert", "antrag": b.antrag_id,
            "beanstandung": b.pk, "ursprung": lauf.pk, "auftrag": auftrag.pk})
    return auftrag


def _rahmen(auftrag):
    d = pruefen(auftrag.korrekturkontext)
    alt, b = auftrag.ursprung, auftrag.beanstandung
    if (auftrag.zweck != Zweck.KORREKTUR or d["antrag"] != auftrag.antrag_id
            or d["ursprung"] != auftrag.ursprung_id or d["beanstandung"]["id"] != auftrag.beanstandung_id
            or d["text"] != auftrag.kontext or d["quellen"] != auftrag.quellenkontext
            or alt is None or alt.zweck != Zweck.RECHTSBEZUG or not alt.erfolgreich
            or alt.antrag_id != auftrag.antrag_id or alt.eingabe != d["eingabe"] or alt.antwort != d["antwort"]
            or b is None or b.antrag_id != auftrag.antrag_id or b.lauf_id != alt.pk
            or b.text != d["beanstandung"]["text"] or b.erstellt_am.isoformat() != d["beanstandung"]["erstellt_am"]):
        raise ValueError("Korrekturrahmen gehört nicht zu diesem Auftrag.")
    return d


def ausfuehren(auftrag):
    from ki.auftraege import auftrag_laden
    from ki.models import lauf_ausfuehren

    d = _rahmen(auftrag)
    prompt = auftrag_laden("korrektur", nummer=1)
    # Ausschließlich der festgehaltene alte Wortlaut; kein Zugriff auf aktuelle Antragstexte/Quellen.
    eingabe = json.dumps({"urspruengliche_eingabe": d["eingabe"], "urspruengliche_antwort": d["antwort"],
                         "beanstandung": d["beanstandung"]["text"]}, ensure_ascii=False, sort_keys=True)
    return lauf_ausfuehren(Zweck.KORREKTUR, prompt.text, eingabe, auftrag.angefordert_von,
        antrag=auftrag.antrag, auftrag_version=prompt.version,
        kontext={"text": d["text"], "quellen": d["quellen"], "korrektur": auftrag.korrekturkontext,
                 "auftrag": auftrag.pk, "versuch": auftrag.versuche})


def _oeffentlicher_lauf(auftrag, lauf=None):
    """Betriebliche lauf_id nicht als Freibrief für einen fremden/interne Lauf behandeln."""
    k = lauf if lauf is not None else auftrag.lauf
    if k is None:
        return None
    if (k.zweck != Zweck.KORREKTUR or k.antrag_id != auftrag.antrag_id or not isinstance(k.kontext, dict)
            or k.kontext.get("auftrag") != auftrag.pk
            or k.kontext.get("korrektur") != auftrag.korrekturkontext):
        raise ValueError("Kein zugehöriger Korrekturlauf.")
    return k


def stand(auftrag):
    from ki.rechtsbezug import antwort_parsen

    try:
        d = _rahmen(auftrag)
        k = _oeffentlicher_lauf(auftrag)
    except (ValueError, TypeError, KeyError):
        return {"zustand": "fehler"}
    return {"zustand": auftrag.status, "auftrag": auftrag, "ursprung": auftrag.ursprung_id,
            "hash": auftrag.korrekturkontext["sha256"], "fassung": d["text"]["fassung_nummer"],
            "ergebnis": antwort_parsen(k.antwort) if k and k.erfolgreich else None, "lauf": k}


def hinzufuegen(antrag, beanstandungen, mitglied=None):
    if not beanstandungen:
        return beanstandungen
    jobs = {a.beanstandung_id: a for a in KIAuftrag.objects.filter(
        antrag=antrag, zweck=Zweck.KORREKTUR, beanstandung__in=beanstandungen,
    ).select_related("lauf", "ursprung", "beanstandung")}
    erlaubt = darf_anfordern(mitglied, antrag)
    for b in beanstandungen:
        job = jobs.get(b.pk)
        b.korrekturstand = stand(job) if job else {"zustand": "keiner"}
        b.darf_korrektur_anfordern = bool(erlaubt and job is None and b.lauf
            and b.lauf.zweck == Zweck.RECHTSBEZUG and isinstance(b.lauf.kontext, dict) and b.lauf.kontext.get("text"))
    return beanstandungen


def export(antrag):
    ergebnis = []
    gueltig = {}
    for a in KIAuftrag.objects.filter(antrag=antrag, zweck=Zweck.KORREKTUR).select_related("lauf", "ursprung", "beanstandung"):
        s = stand(a)
        if s["zustand"] == "fehler":
            ergebnis.append({"auftrag": a.pk, "zustand": "fehler"})
            continue
        k = s["lauf"]
        zeile = {"auftrag": a.pk, "beanstandung": a.beanstandung_id, "ursprung": a.ursprung_id,
            "zustand": a.status, "erstellt_am": a.erstellt_am.isoformat(), "versuche": a.versuche,
            "kontext": a.korrekturkontext, "lauf": _laufdaten(k) if k else None, "laeufe": []}
        ergebnis.append(zeile)
        gueltig[a.pk] = (a, zeile)
    if gueltig:
        # Ein Stapel für alle Versuche, keine Abfrage je Beanstandung.
        for k in KILauf.objects.filter(antrag=antrag, zweck=Zweck.KORREKTUR,
                kontext__auftrag__in=list(gueltig)).order_by("erstellt_am", "pk"):
            a, zeile = gueltig[k.kontext["auftrag"]]
            try:
                _oeffentlicher_lauf(a, k)
            except ValueError:
                continue
            zeile["laeufe"].append(_laufdaten(k))
    return ergebnis


def _laufdaten(k):
    from plattform_core.modellantwort import pruefen as form_pruefen

    return {"id": k.pk, "auftrag_version": k.auftrag_version, "modell": k.modell, "anbieter": k.anbieter,
            "erstellt_am": k.erstellt_am.isoformat(), "erfolgreich": k.erfolgreich,
            "eingabe": k.eingabe, "antwort": k.antwort, "kontext": k.kontext,
            "antwortformat": form_pruefen(k.antwort) if k.erfolgreich else None,
            "tokens_ein": k.tokens_ein, "tokens_aus": k.tokens_aus, "dauer_ms": k.dauer_ms}
