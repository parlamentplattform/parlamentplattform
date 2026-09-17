"""Postausgang im bestehenden Webdienst; keine zusätzliche kostenpflichtige Instanz.

Jeder Worker prüft offene Aufträge. Atomare Reservierungen verhindern, dass zwei
Worker denselben Auftrag gleichzeitig senden. Nach Prozessverlust läuft die
Reservierung nach fünf Minuten aus. Es werden keine Verfahrensfristen geändert.
"""
import logging
import threading


def post_worker_init(worker):
    def postausgang():
        from django.db import close_old_connections

        from mitglieder.postausgang import offene_zustellen
        warten = threading.Event()
        while worker.alive:
            try:
                close_old_connections()
                offene_zustellen()
            except Exception:
                logging.getLogger(__name__).exception("Postausgang unterbrochen; neuer Versuch folgt")
            finally:
                close_old_connections()
            warten.wait(30)
    threading.Thread(target=postausgang, name="postausgang", daemon=True).start()
