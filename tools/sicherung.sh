#!/usr/bin/env bash
# Sicherung der Datenbank und Wiederherstellungsprobe (Bestandsaufnahme A10, Schritt 2 · 0.52.0; ADR-012).
#
#   tools/sicherung.sh sichern <datenbank-url> <zielordner>
#       pg_dump im Custom-Format (komprimiert), ohne Eigentümer und Rechte, ohne die Zeilen der Sitzungen
#       und Einmal-Anmeldelinks (wer die Sicherung liest, soll sich damit nicht anmelden können); geprüft
#       mit pg_restore --list, dazu eine .sha256-Datei und eine .zahlen-Datei (Audit-Einträge, Anträge,
#       Konten). Gibt den Pfad der Sicherung aus.
#
#   tools/sicherung.sh probe <sicherungsdatei>
#       Spielt die Sicherung in die (leere) Datenbank aus POSTGRES_HOST/_PORT/_USER/_PASSWORD/_DB zurück
#       und prüft danach: keine offene Migration, Audit-Kette vollständig nachgerechnet.
#
# Die Datenbank-Adresse kommt nur als Argument oder Secret, nie aus dem Repository. Fehlermeldungen von
# pg_dump und pg_restore gehen in eine Datei, nicht ins Protokoll — das Protokoll der Actions ist öffentlich
# und nennte sonst Rechner, Benutzer oder Zeileninhalte. Aufgerufen von .github/workflows/sicherung.yml;
# Ablauf und Protokoll in docs/BETRIEB-RENDER.md.
set -euo pipefail

befehl="${1:-}"
fehlerdatei="${TMPDIR:-/tmp}/sicherung-fehler.log"

case "$befehl" in
  sichern)
    url="${2:?Datenbank-Adresse fehlt}"
    ziel="${3:?Zielordner fehlt}"
    mkdir -p "$ziel"
    datei="$ziel/ddoe-sicherung-$(date -u +%Y-%m-%dT%H%MZ).dump"
    if ! pg_dump --format=custom --compress=9 --no-owner --no-privileges \
        --exclude-table-data=django_session --exclude-table-data=mitglieder_einmaltoken \
        --file="$datei" "$url" 2> "$fehlerdatei"; then
      echo "FEHLER: pg_dump ist gescheitert (Einzelheiten nicht im öffentlichen Protokoll)." >&2
      exit 1
    fi
    # Eine Sicherung, die sich nicht lesen lässt, ist keine: das Inhaltsverzeichnis muss sich öffnen lassen.
    eintraege=$(pg_restore --list "$datei" | grep -vc '^;' || true)
    if [ "${eintraege:-0}" -lt 10 ]; then
      echo "FEHLER: Die Sicherung enthält nur ${eintraege:-0} Objekte — das ist keine vollständige Datenbank." >&2
      exit 1
    fi
    # Zahlen, an denen der Workflow eine leere oder falsche Datenbank erkennt (sie werden nie kleiner)
    psql "$url" --no-psqlrc --tuples-only --no-align --field-separator=' ' 2> "$fehlerdatei" \
      --command="select (select count(*) from verfahren_auditeintrag), (select count(*) from verfahren_antrag), (select count(*) from mitglieder_mitglied)" \
      | awk '{print "audit=" $1 " antraege=" $2 " konten=" $3}' > "$datei.zahlen"
    (cd "$ziel" && sha256sum "$(basename "$datei")" > "$(basename "$datei").sha256")
    echo "$datei"
    ;;
  probe)
    datei="${2:?Sicherungsdatei fehlt}"
    : "${POSTGRES_HOST:?}" "${POSTGRES_DB:?}" "${POSTGRES_USER:?}"
    if [ -f "$datei.sha256" ]; then
      (cd "$(dirname "$datei")" && sha256sum --check --quiet "$(basename "$datei").sha256")
    fi
    if ! PGPASSWORD="${POSTGRES_PASSWORD:-}" pg_restore --no-owner --no-privileges --exit-on-error \
        --host="$POSTGRES_HOST" --port="${POSTGRES_PORT:-5432}" --username="$POSTGRES_USER" \
        --dbname="$POSTGRES_DB" "$datei" 2> "$fehlerdatei"; then
      echo "FEHLER: pg_restore ist gescheitert (Einzelheiten nicht im öffentlichen Protokoll)." >&2
      exit 1
    fi
    python manage.py migrate --check --noinput
    python manage.py audit_pruefen --voll
    echo "Wiederherstellungsprobe bestanden: $(basename "$datei")"
    ;;
  *)
    sed -n '2,19p' "$0"
    exit 2
    ;;
esac
