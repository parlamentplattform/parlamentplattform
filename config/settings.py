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
DEFAULT_FROM_EMAIL = os.environ.get("DDOE_MAIL_ABSENDER", "plattform@ddoe.at")

LOGIN_URL = "/anmelden/"

# § 4 Abs 4 lit d: Übergangsregel für den Aufbau — Anwartschaftsfristen entfallen,
# bis die Mitgliederversammlung die erste Verfahrensordnung beschlossen hat.
DDOE_UEBERGANGSREGEL = os.environ.get("DDOE_UEBERGANGSREGEL", "1") == "1"

# F-51: Der satzungsgebende Erstzugang der Mitgliederverwaltung. Dieses Konto ist
# immer Admin, kann weder pausiert noch ausgeschlossen noch entmachtet werden —
# damit die Verwaltung nie herrenlos wird. Weitere Admins ernennen Admins einander.
DDOE_FIX_ADMIN = os.environ.get("DDOE_FIX_ADMIN", "didide@ddoe.at").lower()

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

# HTTPS-Ursprünge, denen Formulare vertrauen (Komma-getrennt), z. B.
# "https://plattform.ddoe.at,https://parlamentplattform.onrender.com"
CSRF_TRUSTED_ORIGINS = [o for o in os.environ.get("DDOE_CSRF_ORIGINS", "").split(",") if o]

# Statische Dateien in Produktion direkt aus der Anwendung (WhiteNoise),
# aktiviert per Umgebungsvariable — Entwicklung und Tests bleiben unberührt.
if os.environ.get("DDOE_STATIK") == "whitenoise":
    MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")
    STORAGES = {
        "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": "whitenoise.storage.CompressedStaticFilesStorage"},
    }
