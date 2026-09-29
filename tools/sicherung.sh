#!/usr/bin/env bash
# Sicherung der Datenbank und Wiederherstellungsprobe (Bestandsaufnahme A9, Schritt 2 · 0.52.0).
#
#   tools/sicherung.sh sichern <datenbank-url> <zielordner>
#       pg_dump im Custom-Format (komprimiert), ohne Eigentümer und Rechte, geprüft mit pg_restore --list,
#       dazu eine .sha256-Datei. Gibt den Pfad der Sicherung aus.
#
#   tools/sicherung.sh probe <sicherungsdatei>
#       Spielt die Sicherung in die (leere) Datenbank aus POSTGRES_HOST/_PORT/_USER/_PASSWORD/_DB zurück
#       und prüft danach: keine offene Migration, Audit-Kette vollständig nachgerechnet.
#
# Die Datenbank-Adresse kommt nur als Argument oder Secret, nie aus dem Repository (CLAUDE.md § 6).
# Aufgerufen von .github/workflows/sicherung.yml; Ablauf und Protokoll in docs/BETRIEB-RENDER.md.
set -euo pipefail

befehl="${1:-}"

case "$befehl" in
  sichern)
    url="${2:?Datenbank-Adresse fehlt}"
    ziel="${3:?Zielordner fehlt}"
    mkdir -p "$ziel"
    datei="$ziel/ddoe-sicherung-$(date -u +%Y-%m-%dT%H%MZ).dump"
    pg_dump --format=custom --compress=9 --no-owner --no-privileges --file="$datei" "$url"
    # Eine Sicherung, die sich nicht lesen lässt, ist keine: das Inhaltsverzeichnis muss sich öffnen lassen.
    eintraege=$(pg_restore --list "$datei" | grep -vc '^;')
    if [ "$eintraege" -lt 10 ]; then
      echo "FEHLER: Die Sicherung enthält nur $eintraege Objekte — das ist keine vollständige Datenbank." >&2
      exit 1
    fi
    (cd "$ziel" && sha256sum "$(basename "$datei")" > "$(basename "$datei").sha256")
    echo "$datei"
    ;;
  probe)
    datei="${2:?Sicherungsdatei fehlt}"
    : "${POSTGRES_HOST:?}" "${POSTGRES_DB:?}" "${POSTGRES_USER:?}"
    if [ -f "$datei.sha256" ]; then
      (cd "$(dirname "$datei")" && sha256sum --check --quiet "$(basename "$datei").sha256")
    fi
    PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_restore --no-owner --no-privileges --exit-on-error \
      --host="$POSTGRES_HOST" --port="${POSTGRES_PORT:-5432}" --username="$POSTGRES_USER" \
      --dbname="$POSTGRES_DB" "$datei"
    python manage.py migrate --check --noinput
    python manage.py audit_pruefen --voll
    echo "Wiederherstellungsprobe bestanden: $(basename "$datei")"
    ;;
  *)
    sed -n '2,13p' "$0"
    exit 2
    ;;
esac
