"""Anforderungsbindung und einmaliges Reservieren. Noch kein Anbieter- oder UI-Pfad."""

import hashlib
import secrets
import uuid

from django.core import signing
from django.utils import timezone

from ki.models import Vergleichsanfrage
from ki.vergleichskontext import eingabe, pruefen
from verfahren.einbringwahl import _fingerabdruck, pruefstand_lesen

SALT = "ki.gegenueberstellung.anforderung.v1"


def _bindungsdaten(daten, mitglied, pruefstand):
    if pruefstand_lesen(pruefstand, daten, mitglied) is None:
        raise ValueError("Kein passender Prüfstand für die Vergleichsanforderung.")
    return {"konto": mitglied.pk, "formular": _fingerabdruck(daten),
            "angebot": hashlib.sha256(pruefstand.encode("utf-8")).hexdigest()}


def anbieten(daten, mitglied, pruefstand):
    """Zufällige Anforderung an genau dieses Konto, Formular und Angebot binden.

    Das Angebot allein speichert keinen Entwurf und ruft keinen Anbieter auf.
    Signieren verschlüsselt nicht: Das Token enthält nur IDs und Fingerabdrücke.
    """
    bindung = _bindungsdaten(daten, mitglied, pruefstand)
    return signing.dumps({**bindung, "kennung": str(uuid.uuid4())}, salt=SALT, compress=True)


def kennung_lesen(token, daten, mitglied, pruefstand):
    try:
        d = signing.loads(token, salt=SALT)
        bindung = _bindungsdaten(daten, mitglied, pruefstand)
        if (not isinstance(d, dict) or set(d) != set(bindung) | {"kennung"}
                or any(d[k] != v for k, v in bindung.items())):
            raise ValueError("Anforderung passt nicht zu Konto, Text und Angebot.")
        kennung = uuid.UUID(d["kennung"])
        if str(kennung) != d["kennung"] or kennung.version != 4:
            raise ValueError("Keine eindeutige Anforderungskennung.")
        return kennung
    except (signing.BadSignature, TypeError, AttributeError) as e:
        raise ValueError("Ungültige Vergleichsanforderung.") from e


def anlegen(kennung, kontext, mitglied):
    """Erst nach ausdrücklicher Anforderung speichern; doppelte Kennung wiederverwenden.

    Der übergebene Kontext muss zuvor durch festhalten() aus dem tatsächlichen
    signierten Angebot aufgebaut sein. Diese Funktion ist keine öffentliche View.
    """
    d = pruefen(kontext)
    if d["konto"] != mitglied.pk or not isinstance(kennung, uuid.UUID) or kennung.version != 4:
        raise ValueError("Vergleichskontext gehört nicht zu diesem Konto oder dieser Kennung.")
    text = eingabe(kontext)
    sha = hashlib.sha256(text.encode("utf-8")).hexdigest()
    anfrage, neu = Vergleichsanfrage.objects.get_or_create(kennung=kennung, defaults={
        "angefordert_von": mitglied, "kontext": kontext, "eingabe": text, "eingabe_sha256": sha,
    })
    # Bei Double-POST kann erfasst_am abweichen, die eigentlichen Inputs aber nicht.
    if (anfrage.angefordert_von_id != mitglied.pk
            or anfrage.kontext.get("formular_sha256") != d["formular_sha256"]
            or not secrets.compare_digest(anfrage.eingabe_sha256, sha)
            or anfrage.eingabe != text):
        raise ValueError("Die Anforderungskennung ist bereits an einen anderen Text gebunden.")
    return anfrage, neu


def reservieren(anfrage, mitglied):
    """Ein bedingtes UPDATE, keine zweite Ausführung nach Refresh oder Doppel-POST."""
    return bool(Vergleichsanfrage.objects.filter(
        kennung=anfrage.pk, angefordert_von=mitglied, status="bereit", begonnen_am__isnull=True,
    ).update(status="laeuft", begonnen_am=timezone.now(), meldung=""))
