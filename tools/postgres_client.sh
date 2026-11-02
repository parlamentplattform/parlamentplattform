#!/usr/bin/env bash
# PostgreSQL-17-Client für die native Debian-Laufzeit von Render (ADR-013).
# Nur im eigenen Verzeichnis entpacken, keine Systempakete oder Rootrechte ändern.
set -euo pipefail
ziel="${1:?Zielverzeichnis fehlt}"
mkdir -p "$ziel"
ziel=$(cd "$ziel" && pwd)
if [ -x "$ziel/root/usr/lib/postgresql/17/bin/pg_dump" ]; then
  exit 0
fi
. /etc/os-release
case "${VERSION_CODENAME:-}" in bookworm|trixie) ;; *) echo 'Nicht unterstützte PostgreSQL-Client-Laufzeit.' >&2; exit 1;; esac
mkdir -p "$ziel/lists/partial" "$ziel/cache/archives/partial" "$ziel/pakete" "$ziel/root"
curl --fail --silent --show-error --proto '=https' --tlsv1.2 \
  https://www.postgresql.org/media/keys/ACCC4CF8.asc -o "$ziel/pgdg.asc"
fingerabdruck=$(gpg --batch --show-keys --with-colons "$ziel/pgdg.asc" | sed -n 's/^fpr:::::::::\([^:]*\):.*/\1/p' | head -1)
[ "$fingerabdruck" = B97B0AFCAA1A47F044F244A07FCC7D46ACCC4CF8 ] || { echo 'PostgreSQL-Schlüssel stimmt nicht.' >&2; exit 1; }
printf 'deb [signed-by=%s] https://apt.postgresql.org/pub/repos/apt %s-pgdg main\n' \
  "$ziel/pgdg.asc" "$VERSION_CODENAME" > "$ziel/sources.list"
optionen=(-o "Dir::Etc::sourcelist=$ziel/sources.list" -o 'Dir::Etc::sourceparts=-'
  -o "Dir::State::lists=$ziel/lists" -o "Dir::Cache=$ziel/cache"
  -o "APT::Sandbox::User=$(id -un)" -o 'Acquire::Retries=2')
apt-get "${optionen[@]}" update -qq
cd "$ziel/pakete"
# APT prüft signierten Paketindex und SHA-256-Prüfsummen der Downloads.
apt-get "${optionen[@]}" download postgresql-client-17 libpq5
for paket in ./*.deb; do dpkg-deb --extract "$paket" "$ziel/root"; done
LD_LIBRARY_PATH="$ziel/root/usr/lib/$(dpkg-architecture -qDEB_HOST_MULTIARCH)${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}" \
  "$ziel/root/usr/lib/postgresql/17/bin/pg_dump" --version
