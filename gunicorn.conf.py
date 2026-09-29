"""Hintergrundfaden im bestehenden Webdienst; keine zusätzliche kostenpflichtige Instanz.

Jeder Worker prüft alle 30 Sekunden die wiederkehrenden Läufe aus `verfahren/hintergrund.py` —
vor allem den Fristen-Wächter (alle DDOE_WAECHTER_MINUTEN, D-J1a) — und danach den Postausgang
(offene Aufträge, atomar reserviert). Die Läufe sperren sich gegenseitig über eine Datenbankzeile,
sodass zwei Worker nie dasselbe zugleich tun. Nach Prozessverlust läuft jede Reservierung aus.
Es werden keine Verfahrensfristen geändert — nur fällige ausgewertet, wie ein Seitenaufruf es täte.
"""
import logging
import threading


def eine_runde():
    """Eine Runde des Fadens: zuerst der Wächter, dann der Postausgang — jede Aufgabe für sich.

    Standen beide im selben try und der Postausgang vorn, ließ eine Ausnahme des Postausgangs den
    Wächter in dieser Runde ausfallen, und ein hängender SMTP-Server verzögerte ihn um bis zu
    50 Zeitüberschreitungen je Runde."""
    from django.db import close_old_connections

    from mitglieder.postausgang import offene_zustellen
    from verfahren.hintergrund import faellige_ausfuehren

    for aufgabe in (faellige_ausfuehren, offene_zustellen):
        try:
            close_old_connections()
            aufgabe()
        except Exception:
            logging.getLogger(__name__).exception(
                "Hintergrundfaden: %s unterbrochen; neuer Versuch folgt", aufgabe.__name__
            )
        finally:
            close_old_connections()


def post_worker_init(worker):
    def hintergrund():
        warten = threading.Event()
        while worker.alive:
            eine_runde()
            warten.wait(30)
    threading.Thread(target=hintergrund, name="hintergrund", daemon=True).start()
