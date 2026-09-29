"""Hintergrundfaden im bestehenden Webdienst; keine zusätzliche kostenpflichtige Instanz.

Jeder Worker prüft alle 30 Sekunden den Postausgang (offene Aufträge, atomar reserviert) und
danach die wiederkehrenden Läufe aus `verfahren/hintergrund.py` — vor allem den Fristen-Wächter
(alle DDOE_WAECHTER_MINUTEN, D-J1a). Die Läufe sperren sich gegenseitig über eine Datenbankzeile,
sodass zwei Worker nie dasselbe zugleich tun. Nach Prozessverlust läuft jede Reservierung aus.
Es werden keine Verfahrensfristen geändert — nur fällige ausgewertet, wie ein Seitenaufruf es täte.
"""
import logging
import threading


def post_worker_init(worker):
    def hintergrund():
        from django.db import close_old_connections

        from mitglieder.postausgang import offene_zustellen
        from verfahren.hintergrund import faellige_ausfuehren
        warten = threading.Event()
        while worker.alive:
            try:
                close_old_connections()
                offene_zustellen()
                faellige_ausfuehren()
            except Exception:
                logging.getLogger(__name__).exception("Hintergrundfaden unterbrochen; neuer Versuch folgt")
            finally:
                close_old_connections()
            warten.wait(30)
    threading.Thread(target=hintergrund, name="hintergrund", daemon=True).start()
