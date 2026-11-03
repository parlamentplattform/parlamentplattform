"""Explizit eine bekannte amtliche Ressorttabelle mit Methodik übernehmen."""

from django.db import transaction
from django.utils import timezone

from faktenbasis.abrufschutz import einzelabruf
from faktenbasis.models import PersonalRessortAbruf, PersonalRessorttabelle
from faktenbasis.personalimport import _herunterladen
from faktenbasis.ressortbeleg import lesen
from verfahren.models import AuditEintrag


def _uebernehmen(lieferung, weg):
    beginn = timezone.now()
    try:
        daten = lesen(lieferung())
    except ValueError as fehler:
        code = str(fehler)
        if code not in {"personal_antwort", "personal_zeit", "personal_groesse", "personal_abruf",
                        "ressort_datei", "ressort_unbekannter_beleg", "ressort_pdf", "ressort_text",
                        "ressort_seite", "ressort_methodik", "ressort_spalten", "ressort_tabellenende",
                        "ressort_zeile", "ressort_gesamt"}:
            code = "ressort_format"
        with transaction.atomic():
            lauf = PersonalRessortAbruf.objects.create(begonnen_am=beginn, beendet_am=timezone.now(),
                erfolgreich=False, weg=weg, fehlercode=code)
            AuditEintrag.anhaengen({"typ": "personal_ressorts_import", "abruf": lauf.pk, "erfolgreich": False})
        raise ValueError(code) from fehler
    with transaction.atomic():
        inhalt, neu = PersonalRessorttabelle.objects.get_or_create(
            original_sha256=daten["original_sha256"], parser_fassung=daten["parser_fassung"],
            defaults={k: v for k, v in daten.items() if k not in {"original_sha256", "parser_fassung"}},
        )
        lauf = PersonalRessortAbruf.objects.create(inhalt=inhalt, begonnen_am=beginn, beendet_am=timezone.now(),
            erfolgreich=True, neu=neu, weg=weg)
        AuditEintrag.anhaengen({"typ": "personal_ressorts_import", "abruf": lauf.pk, "inhalt": inhalt.pk,
            "erfolgreich": True, "neu": neu})
    return lauf


def datei_importieren(inhalt):
    return _uebernehmen(lambda: inhalt, "datei")


def amtlich_importieren():
    with einzelabruf():
        return _uebernehmen(_herunterladen, "amtlich")
