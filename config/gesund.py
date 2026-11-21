"""Der Gesundheitscheck des Dienstes (Befund #94).

Render (`render.yaml: healthCheckPath: /gesund/`) und die Docker-Vorlage der Partnerinstanzen
fragen diese Adresse, um zu entscheiden, ob eine Instanz Anfragen bekommen darf und ob ein
Deploy gelungen ist. Eine Antwort, die nur sagt „Gunicorn läuft", hält einen Dienst ohne
Datenbank für gesund — dann sehen Mitglieder die 500-Seite, während das Dashboard „Healthy"
zeigt und nichts neu startet. Deshalb eine billige Berührung der Datenbank: `SELECT 1`.

Bewusst ohne Vorlage und ohne Kontextprozessoren — der Check darf nichts brauchen, was
selbst ausfallen könnte, außer dem, was er prüft.
"""

from __future__ import annotations

from django.db import connection
from django.http import JsonResponse


def gesund(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:  # noqa: BLE001 — jeder Datenbankfehler heißt: nicht gesund
        # 503 heißt für Render: Instanz neu starten bzw. Deploy nicht übernehmen — beides gewollt.
        return JsonResponse({"status": "datenbank"}, status=503)
    return JsonResponse({"status": "ok"})
