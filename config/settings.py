"""Django-Konfiguration der ParlamentPlattform.

Prinzipien: Konfiguration über Umgebungsvariablen (12-Factor), sichere
Voreinstellungen, keine externen Dienste im Datenpfad. Lokal ohne Docker läuft
SQLite; setzt man POSTGRES_HOST (wie in docker-compose.yml), läuft PostgreSQL.
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get("DDOE_SECRET_KEY", "nur-fuer-entwicklung-niemals-produktiv")
DEBUG = os.environ.get("DDOE_DEBUG", "1") == "1"
ALLOWED_HOSTS = [h for h in os.environ.get("DDOE_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",") if h]
if DEBUG:
    ALLOWED_HOSTS += ["testserver"]  # Django-Testclient

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "mitglieder",
    "verfahren",
    "uebersicht",
    "anstoss",
    "mandatare",
    "gremien",
    "ki",
    "parameter",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",  # F-33: Sprache aus Sitzung/Cookie/Browser
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "uebersicht.middleware.Besuchszaehlung",  # zählt Tages-Summen, nie Personen (F-52)
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "verfahren.kontext.gespraeche",  # Zähler am Gesprächs-Griff (FB-G3)
                "gremien.kontext.rollenband",  # Lesezugang für abgelaufene Rollen (FB-I1)
            ],
        },
    },
]

if os.environ.get("POSTGRES_HOST"):
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": os.environ.get("POSTGRES_DB", "plattform"),
            "USER": os.environ.get("POSTGRES_USER", "plattform"),
            "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
            "HOST": os.environ["POSTGRES_HOST"],
            "PORT": os.environ.get("POSTGRES_PORT", "5432"),
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "entwicklung.sqlite3",
        }
    }

AUTH_USER_MODEL = "mitglieder.Mitglied"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 12}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
]

LANGUAGE_CODE = "de-at"
TIME_ZONE = "Europe/Vienna"
USE_I18N = True
USE_TZ = True

# F-33: Deutsch zuerst, Englisch dazu. Der Umschalter (DE/EN) steht in der
# Kopfzeile; ohne Wahl entscheidet die Browsersprache. Übersetzt wird die
# Oberfläche — Inhalte (Anträge, Beratungen) bleiben in ihrer Originalsprache,
# Kategorienamen werden mit dem EuroVoc-Anschluss mehrsprachig (ADR-007).
LANGUAGES = [("de", "Deutsch"), ("en", "English")]
LOCALE_PATHS = [BASE_DIR / "locale"]

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# E-Mail: Entwicklung -> Konsole; Produktion -> EU-SMTP per Umgebungsvariablen
if os.environ.get("DDOE_SMTP_HOST"):
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_HOST = os.environ["DDOE_SMTP_HOST"]
    EMAIL_PORT = int(os.environ.get("DDOE_SMTP_PORT", "587"))
    EMAIL_HOST_USER = os.environ.get("DDOE_SMTP_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("DDOE_SMTP_PASSWORT", "")
    EMAIL_USE_TLS = True
    # Hängt der Mailserver (oder blockiert das Netz den Port), soll der Request
    # nach Sekunden sauber scheitern — nicht den Worker bis zum Timeout halten.
    EMAIL_TIMEOUT = int(os.environ.get("DDOE_SMTP_TIMEOUT", "20"))
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
DEFAULT_FROM_EMAIL = os.environ.get("DDOE_MAIL_ABSENDER", "ParlamentPlattform <plattform@ddoe.at>")

LOGIN_URL = "/anmelden/"

# § 4 Abs 4 lit d: Übergangsregel für den Aufbau — Anwartschaftsfristen entfallen,
# bis die Mitgliederversammlung die erste Verfahrensordnung beschlossen hat.
DDOE_UEBERGANGSREGEL = os.environ.get("DDOE_UEBERGANGSREGEL", "1") == "1"

# F-51: Der satzungsgebende Erstzugang der Mitgliederverwaltung. Dieses Konto ist
# immer Admin, kann weder pausiert noch ausgeschlossen noch entmachtet werden —
# damit die Verwaltung nie herrenlos wird. Weitere Admins ernennen Admins einander.
DDOE_FIX_ADMIN = os.environ.get("DDOE_FIX_ADMIN", "didide@ddoe.at").lower()

# F-49/F-52 (Befund #19/#66): Welche Kopfzeile die Adresse der Verbindung trägt, wenn ein
# vertrauenswürdiger Proxy davorsteht — in META-Schreibweise, einwertig (Render hinter
# Cloudflare: HTTP_CF_CONNECTING_IP). Unbesetzt zählt ausschließlich REMOTE_ADDR;
# X-Forwarded-For wird nie gelesen, weil sein erster Eintrag vom Client frei wählbar ist.
DDOE_CLIENT_IP_KOPFZEILE = os.environ.get("DDOE_CLIENT_IP_KOPFZEILE", "")

# F-59 Beitragsabgleich: Zugang zum Kontoinformationsdienst (GoCardless Bank
# Account Data). Ohne diese Schlüssel bleibt die Bankanbindung einfach aus —
# die Plattform kennt in keinem Fall Bankzugangsdaten, nur diese Dienst-Kennungen.
DDOE_BANK_SECRET_ID = os.environ.get("DDOE_BANK_SECRET_ID", "")
DDOE_BANK_SECRET_KEY = os.environ.get("DDOE_BANK_SECRET_KEY", "")
DDOE_BASIS_URL = os.environ.get("DDOE_BASIS_URL", "https://parlament.ddoe.at")
# Kennung dieser Instanz im gemeinsamen Schema (§ 12 Abs 5, docs/SCHEMA.md): <ländercode>-<kurzname>
DDOE_SYSTEM_ID = os.environ.get("DDOE_SYSTEM_ID", "at-ddoe")
DDOE_SYSTEM_NAME = os.environ.get("DDOE_SYSTEM_NAME", "Direkte Demokratie Österreich")

# Sicherheit — greift, sobald DEBUG aus ist
if not DEBUG:
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = 60 * 60 * 24 * 30
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_REFERRER_POLICY = "same-origin"
    # Hinter einem TLS-terminierenden Proxy (z. B. Render, Traefik) sagt uns
    # dieser Header, dass die ursprüngliche Verbindung verschlüsselt war —
    # sonst schleift SECURE_SSL_REDIRECT endlos um.
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# HSTS-Preload (security.W021) ist eine eigene, schwer umkehrbare Entscheidung: Die Domain
# landet in den Browsern fest verdrahtet, auch für Subdomains, die es noch gar nicht gibt.
# Sie wird nicht nebenbei getroffen. Alles andere aus `check --deploy` muss die CI still
# halten — deshalb wird genau diese eine Warnung begründet gestillt und keine weitere.
SILENCED_SYSTEM_CHECKS = ["security.W021"]

# Protokollierung (Befund #17): Ohne eigene LOGGING-Einstellung gilt Djangos Standard, und
# der schreibt Serverfehler nur mit DEBUG=1 auf die Konsole (Filter RequireDebugTrue) bzw.
# per Mail an ADMINS — die hier leer sind. In Produktion (DDOE_DEBUG=0) erreichte der
# Traceback eines 500ers also weder stderr noch das Render-Log. Die 500-Seite verspricht
# „Er ist protokolliert" — das muss stimmen. `django.request` schreibt deshalb ungefiltert
# auf stderr (Gunicorn reicht stderr unverändert an Render weiter); alles andere ab WARNING.
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "knapp": {"format": "{levelname} {asctime} {name}: {message}", "style": "{"},
    },
    "handlers": {
        "stderr": {"class": "logging.StreamHandler", "formatter": "knapp"},
    },
    "root": {"handlers": ["stderr"], "level": "WARNING"},
    "loggers": {
        # Unbehandelte Ausnahmen jeder Anfrage (Status 500) — mit Traceback, unabhängig von DEBUG.
        "django.request": {"handlers": ["stderr"], "level": "ERROR", "propagate": False},
        # Abgewiesene Hosts, CSRF-Verstöße u. Ä.: gehören ebenfalls ins Log, nicht in eine Mail.
        "django.security": {"handlers": ["stderr"], "level": "WARNING", "propagate": False},
    },
}

# HTTPS-Ursprünge, denen Formulare vertrauen (Komma-getrennt), z. B.
# "https://plattform.ddoe.at,https://parlamentplattform.onrender.com"
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DDOE_CSRF_ORIGINS", "").split(",") if o]

# Statische Dateien in Produktion direkt aus der Anwendung (WhiteNoise),
# aktiviert per Umgebungsvariable — Entwicklung und Tests bleiben unberührt.
# Manifest-Speicher (Befund #98): Jede Datei bekommt ihren Inhalts-Hash in den Namen, dadurch
# darf WhiteNoise sie ein Jahr lang unveränderlich cachen statt 60 Sekunden — vier Skripte
# je Seitenwechsel weniger auf dem Weg zum Server. Kehrseite: `{% static %}` wirft für jede
# Datei, die im Manifest fehlt; `tests/test_betrieb.py` rendert deshalb den App-Rahmen mit
# gefülltem Manifest, und die CI führt `collectstatic` aus, bevor etwas ausgerollt wird.
if os.environ.get("DDOE_STATIK") == "whitenoise":
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
    }

# Der Modell-Steckplatz (F-60, Ring 0b) — anbieterneutral, ohne Schlüssel leer.
# Grundsatz L7: Die KI schlägt vor, sie entscheidet nie.
DDOE_KI_ANBIETER = os.environ.get("DDOE_KI_ANBIETER", "mistral")
DDOE_KI_SCHLUESSEL = os.environ.get("DDOE_KI_SCHLUESSEL", "")
DDOE_KI_MODELL = os.environ.get("DDOE_KI_MODELL", "mistral-small-latest")
DDOE_KI_MONATSTOKENS = int(os.environ.get("DDOE_KI_MONATSTOKENS", "1000000"))
