"""Feld-Wächter über den persönlichen Datenexport (GP-162, GP-089; Art 15/20 DSGVO).

Die Wächter in `test_profil.py` prüfen, dass jede Rückbeziehung des Mitglieds einen Ordner im
Export hat. Dieser hier prüft die Felder: Zu jedem Pfad mit Ordner — direkt am Mitglied und
mittelbar über Mandat, Aufgabe, Sitzung, Antrag … — legt die Markenfabrik eine Zeile an, in der
jedes gespeicherte Feld einen unverwechselbaren Wert trägt. Danach muss jede Marke im Ordner des
Exports stehen, oder das Feld steht mit Grund in `AUSNAHMEN_FELDER`. Wer ein Feld an einem Modell
mit Mitgliedsbezug ergänzt, zieht den Export nach oder begründet die Auslassung — sonst ist der
Test rot. Nur synthetische Werte; läuft auf SQLite und PostgreSQL.

Geprüft werden die gespeicherten Datenfelder. Verweise auf andere Zeilen (Fremdschlüssel) nennt der
Export teils unter anderem Namen (Antrag statt Entwurf, Gemeindekennziffer statt Gemeinde); über sie
wachen die Beziehungs-Wächter in `test_profil.py`, nicht dieser.
"""

import itertools
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

import pytest
from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder
from django.db import IntegrityError, models, transaction
from django.utils import timezone

from mitglieder.models import Identitaetsstufe, Mitglied
from mitglieder.profil import daten_export
from mitglieder.test_profil import DIREKT_OHNE_ORDNER, DIREKT_ORDNER, MITTELBAR_ORDNER

pytestmark = pytest.mark.django_db

_VERFAHREN = "öffentliche Verfahrensdaten des Antrags — auf der Antragsseite und im Verfahrensexport nachlesbar"
_BESCHLUSS = "Verfahrensdaten des Ratsbeschlusses — im Beschlussregister nachlesbar; der Export nennt den Verweis"
_KI = "Ein- und Ausgabe des KI-Laufs: Verfahrenstext im KI-Archiv, kein Datum über den Menschen; der Export nennt den Lauf"

#: Gespeicherte Felder, die der Export bewusst auslässt: „Modell.feld“ → Grund. Kein Eintrag ohne Grund,
#: keiner für ein Feld, das der Export doch führt (der Wächter meldet beides).
AUSNAHMEN_FELDER = {
    "Adresswechsel.einspruch_hash": "Hash des Einspruchslinks: Schlüssel, kein Datum über den Menschen",
    "Adresswechsel.neue_email": (
        "von der Verwaltung eingetragene Adresse: Bis der Wechsel wirksam ist, ist nicht belegt, dass sie "
        "diesem Menschen gehört (F-51: womöglich die Adresse eines Dritten); wirksam geworden steht sie als "
        "E-Mail in den Stammdaten"
    ),
    "Beitragseingang.umsatz_id": "Kennung des Bankumsatzes: Schlüssel der Buchhaltung gegen Doppelbuchung",
    "Postauftrag.gesperrt_bis": "technische Sperre des Versandlaufs, kein Datum über den Menschen",
    "Postauftrag.sperrcode": "technische Sperre des Versandlaufs, kein Datum über den Menschen",
    "KIAuftrag.gesperrt_bis": "technische Sperre der Warteschlange, kein Datum über den Menschen",
    "KIAuftrag.sperrcode": "technische Sperre der Warteschlange, kein Datum über den Menschen",
    "Mandat.foto": "Lichtbild als Binärdatei, vom Mandatar selbst hochgeladen und an seinem Mandat sichtbar; der Export nennt den Dateityp",
    **{f"Antrag.{feld}": _VERFAHREN for feld in (
        "phase_beginn", "policy_snapshot", "stimmberechtigte_anzahl", "stimmberechtigung_stichtag",
        "teilnahmegebiet", "teilnehmerkreis_am",
    )},
    **{f"GremienBeschluss.{feld}": _BESCHLUSS for feld in (
        "beschreibung", "optionen", "frist", "ergebnis", "regel_version", "zustand_vorher", "entschieden_am", "anlass",
    )},
    **{f"KILauf.{feld}": _KI for feld in ("eingabe", "antwort", "auftrag_version", "fehler")},
}

#: Felder, deren Wert sich nicht als Marke wiederfinden lässt (Wahrheitswert, Auswahl, kurze Zahl) und
#: die im Export unter einem anderen Schlüssel stehen als ihrem Feldnamen: „Modell.feld“ → Schlüssel.
SCHLUESSEL_ANDERS: dict[str, str] = {}

#: Vorgaben für Zeilen, deren Datenbankregeln die Markenwerte nicht zulassen: „Modell“ → {feld: wert}.
FESTWERTE: dict[str, dict] = {
    # Ein offener Adresswechsel blendet den Stimmregister-Teil aus (F-51) — geprüft wird der volle Export.
    "Adresswechsel": {"status": "wirksam"},
    "KIAuftrag": {"korrekturkontext": {}},  # Regel kiauftrag_korrekturbezug: ohne Korrektur leer
    "Gemeindehaushaltsquelle": {"jahr": 2001, "bis_jahr": None},  # Regeln haushaltsquelle_jahr und _zeitraum
}

#: Leerbare Bezüge, die eine Datenbankregel dennoch verlangt: „Modell“ → Feldnamen.
PFLICHTBEZUEGE: dict[str, tuple] = {
    "Kommentar": ("antrag",),  # Regel kommentar_genau_ein_bezug: Antrag oder Sitzung
}

#: Felder des Kontos selbst: Feldname → Pfad im Export.
KONTO_PFADE = {
    "id": ("mitglied",),
    "username": ("stammdaten", "anmeldename"),
    "email": ("stammdaten", "email"),
    "first_name": ("stammdaten", "vorname"),
    "last_name": ("stammdaten", "nachname"),
    "pseudonym_oeffentlich": ("stammdaten", "anzeigename"),
    "klarname_oeffentlich": ("stammdaten", "klarname_oeffentlich"),
    "post_einwilligung": ("stammdaten", "post_einwilligung"),
    "beitritt": ("stammdaten", "beitritt"),
    "identitaetsstufe": ("stammdaten", "identitaetsstufe"),
    "geprueft_seit": ("stammdaten", "geprueft_seit"),
    "status": ("stammdaten", "status"),
    "status_grund": ("stammdaten", "status_grund"),
    "status_seit": ("stammdaten", "status_seit"),
    "beitrag_zuletzt_am": ("stammdaten", "beitrag_zuletzt_am"),
    "beitragsreferenz_stamm": ("stammdaten", "beitragsreferenz_stamm"),
    "ist_admin": ("stammdaten", "ist_admin"),
    "favoriten_zuerst": ("stammdaten", "favoriten_zuerst"),
    "date_joined": ("stammdaten", "registriert_am"),
    "last_login": ("stammdaten", "zuletzt_angemeldet"),
    "is_active": ("stammdaten", "konto_aktiv"),
    "parteikonto": ("stammdaten", "parteikonto"),
    "is_staff": ("stammdaten", "is_staff"),
    "is_superuser": ("stammdaten", "is_superuser"),
    "willkommen_post_am": ("post", "willkommen_am"),
    "freischaltung_post_am": ("post", "freischaltung_am"),
    "mitgliedsnummer": ("mitgliedsnummer",),
    "testkonto": ("testkonto",),
    "ausweis_code": ("ausweis", "code"),
    "ausweis_schluessel": ("ausweis", "schluessel"),
    "ausweis_ausgestellt_am": ("ausweis", "ausgestellt_am"),
    "wohnsitz_art": ("wohnsitz_art",),
    "wohnsitz": ("wohnsitz",),
    "gemeinde": ("wohnsitz",),
    "bundesland": ("bundesland",),
    "wiener_bezirk": ("wiener_bezirk",),
    "nebenwohnsitz": ("nebenwohnsitz",),
}
KONTO_AUSNAHMEN = {
    "password": "Kennwortfeld: unbrauchbar gesetzt (Anmeldung per Link), Schlüssel und kein Datum über den Menschen",
}

_ZAEHLER = itertools.count(1)


def _marke(n: int) -> str:
    return f"ZQ{n:05d}X"


def _feldwert(f, n: int):
    """(Wert, Suchtext oder None). Ohne Suchtext lässt sich der Wert nicht wiederfinden — dann
    zählt der Schlüsselname im Ordner."""
    if getattr(f, "choices", None):
        erste = f.choices[0]
        return (erste[1][0][0] if isinstance(erste[1], list | tuple) else erste[0]), None
    if isinstance(f, models.BooleanField):
        return True, None
    if isinstance(f, models.EmailField):
        return f"zq{n:05d}x@example.org", f"zq{n:05d}x@example.org"
    if isinstance(f, models.URLField):
        return f"https://example.org/{_marke(n)}", _marke(n)
    if isinstance(f, models.UUIDField):
        wert = uuid.UUID(int=(0x5A51 << 112) + n)
        return wert, wert.hex
    if isinstance(f, models.GenericIPAddressField):
        return "192.0.2.77", None
    if isinstance(f, models.CharField | models.TextField):
        text = _marke(n)
        if f.max_length and f.max_length < len(text):
            return text[: f.max_length], None
        return text, text
    if isinstance(f, models.DateTimeField):
        wert = datetime(2002, 1, 1, tzinfo=UTC) + timedelta(minutes=n)
        return wert, wert.strftime("%Y-%m-%dT%H:%M")
    if isinstance(f, models.DateField):
        wert = date(2001, 1, 1) + timedelta(days=n)
        return wert, wert.isoformat()
    if isinstance(f, models.DecimalField):
        if f.max_digits - f.decimal_places < 6:
            return Decimal(1), None
        return Decimal(100_000 + n), str(100_000 + n)
    if isinstance(f, models.SmallIntegerField | models.PositiveSmallIntegerField):
        return 1, None
    if isinstance(f, models.IntegerField):
        return 7_000_000 + n, str(7_000_000 + n)
    if isinstance(f, models.FloatField):
        return float(7_000_000 + n), str(7_000_000 + n)
    if isinstance(f, models.JSONField):
        return {"zq": _marke(n)}, _marke(n)
    if isinstance(f, models.BinaryField):
        return b"zq", None
    if isinstance(f, models.DurationField):
        return timedelta(seconds=n), None
    raise AssertionError(f"Markenfabrik kennt den Feldtyp nicht: {f.model.__name__}.{f.name} ({type(f).__name__})")


def _datenfelder(modell):
    return [f for f in modell._meta.get_fields() if f.concrete and not f.is_relation and not f.primary_key]


def _bezuege(modell):
    return [f for f in modell._meta.get_fields() if f.concrete and f.is_relation and (f.many_to_one or f.one_to_one)]


class Fabrik:
    """Legt je Pfad eine Markenzeile an. `eigene` hält je Modell die erste Zeile der Probe: Ein
    Pflichtbezug zeigt dorthin, damit die neue Zeile im Export der Probe landet."""

    def __init__(self, probe, anderer):
        self.probe, self.anderer = probe, anderer
        self.eigene: dict = {}
        self.hilfen: dict = {}
        self.zeilen: list = []  # (pfad, modell, [(feld, suchtext)])

    def _bezug(self, f, frisch: bool):
        if f.related_model is Mitglied:
            return self.anderer
        if not frisch and f.related_model in self.eigene:
            return self.eigene[f.related_model]
        if frisch or f.related_model not in self.hilfen:
            self.hilfen[f.related_model] = self._zeile(f.related_model, {}, frisch=False)[0]
        return self.hilfen[f.related_model]

    def _zeile(self, modell, fest: dict, frisch: bool):
        werte, gemerkt, nachtragen = {}, [], {}
        for f in _bezuege(modell):
            if f.name in fest:
                werte[f.name] = fest[f.name]
            elif not f.null or f.name in PFLICHTBEZUEGE.get(modell.__name__, ()):
                werte[f.name] = self._bezug(f, frisch or f.one_to_one or f.unique)
        vorgaben = FESTWERTE.get(modell.__name__, {})
        for f in _datenfelder(modell):
            if f.name in vorgaben:
                werte[f.name], such = vorgaben[f.name], None
            else:
                werte[f.name], such = _feldwert(f, next(_ZAEHLER))
            if getattr(f, "auto_now_add", False) or getattr(f, "auto_now", False):
                nachtragen[f.name] = werte[f.name]
            gemerkt.append((f.name, such))
        zeile = modell(**werte)
        with transaction.atomic():
            zeile.save_base(raw=True, force_insert=True)
            if nachtragen:
                modell._base_manager.filter(pk=zeile.pk).update(**nachtragen)
        return zeile, gemerkt

    def anlegen(self, pfad: str, modell, fest: dict):
        try:
            zeile, gemerkt = self._zeile(modell, fest, frisch=False)
        except IntegrityError:
            # Eindeutigkeit über einen Bezug (etwa eine Sitzung je Aufgabe): mit frischen Hilfszeilen
            zeile, gemerkt = self._zeile(modell, fest, frisch=True)
        self.eigene.setdefault(modell, zeile)
        self.zeilen.append((pfad, modell, gemerkt))
        return zeile


def _mitglied(name: str) -> Mitglied:
    m = Mitglied.objects.create(
        username=f"{name}@example.org", email=f"{name}@example.org", first_name="Vorname", last_name="Nachname",
        is_active=True, beitritt=timezone.localdate() - timedelta(days=400),
        identitaetsstufe=Identitaetsstufe.GEPRUEFT,
    )
    m.set_unusable_password()
    m.save()
    return m


def _markenzeilen():
    """Probe-Mitglied samt je einer Markenzeile für jeden Pfad mit Ordner: (probe, zeilen, ordner je Pfad)."""
    probe, anderer = _mitglied("probe"), _mitglied("anderer")
    fabrik = Fabrik(probe, anderer)
    ordner: dict[str, str] = {}
    je_modell: dict = {}
    modelle = sorted((m for m in apps.get_models() if not m._meta.auto_created), key=lambda m: m._meta.label)
    for modell in modelle:
        for f in _bezuege(modell):
            pfad = f"{modell.__name__}.{f.name}"
            if f.related_model is Mitglied and pfad not in DIREKT_OHNE_ORDNER:
                assert pfad in DIREKT_ORDNER, f"Rückbeziehung ohne Ordner: {pfad} (siehe test_profil.py)"
                ordner[pfad] = DIREKT_ORDNER[pfad]
                je_modell.setdefault(modell.__name__, []).append(fabrik.anlegen(pfad, modell, {f.name: probe}))
    offen = dict(MITTELBAR_ORDNER)
    while offen:
        fortschritt = False
        for schluessel, zweig in list(offen.items()):
            eltern, kind = schluessel.split(" > ")
            kindname, feld = kind.split(".")
            modell = next((m for m in modelle if m.__name__ == kindname), None)
            if modell is None:  # Zwischentabelle einer Mehrfachbeziehung: keine eigenen Datenfelder
                del offen[schluessel]
                fortschritt = True
                continue
            if eltern not in je_modell:
                continue
            f = modell._meta.get_field(feld)
            del offen[schluessel]
            fortschritt = True
            if f.many_to_many:
                continue  # die Beziehung selbst prüft der Wächter in test_profil.py
            ordner[schluessel] = zweig.split(".")[0]
            fest = {feld: je_modell[eltern][0]}
            # Hängt das Kind auch unmittelbar am Mitglied, gehört die Zeile der Probe — sonst stünde sie
            # im Export eines anderen (etwa der eigene Entwurfsbeitrag, der auf einen KI-Lauf verweist).
            eigen = next(
                (b for b in _bezuege(modell) if b.related_model is Mitglied
                 and DIREKT_ORDNER.get(f"{kindname}.{b.name}") == ordner[schluessel]), None,
            )
            if eigen is not None:
                fest[eigen.name] = probe
            je_modell.setdefault(kindname, []).append(fabrik.anlegen(schluessel, modell, fest))
        assert fortschritt, f"Pfade ohne erreichbare Elternzeile: {sorted(offen)}"
    return probe, fabrik.zeilen, ordner


def _pruefen(daten: dict, zeilen, ordner, ausnahmen: dict):
    """(fehlend, überflüssig): Felder ohne Marke im Ordner und ohne Ausnahme — und Ausnahmen, deren Feld
    der Export doch führt."""
    teile = {
        name: json.dumps(wert, ensure_ascii=False, cls=DjangoJSONEncoder) for name, wert in daten.items()
    }
    fehlend, gefuehrt = set(), set()
    for pfad, modell, gemerkt in zeilen:
        teil = teile[ordner[pfad]]
        for feld, such in gemerkt:
            name = f"{modell.__name__}.{feld}"
            if such is None:
                drin = f'"{SCHLUESSEL_ANDERS.get(name, feld)}":' in teil
            else:
                drin = such in teil
            if drin:
                gefuehrt.add(name)
            elif name not in ausnahmen:
                fehlend.add(f"{name} (Pfad {pfad}, Ordner {ordner[pfad]})")
    return sorted(fehlend), sorted(gefuehrt & set(ausnahmen))


def test_jedes_feld_steht_im_export_oder_begruendet_in_der_ausnahmeliste():
    probe, zeilen, ordner = _markenzeilen()
    daten = daten_export(Mitglied.objects.get(pk=probe.pk))
    fehlend, ueberfluessig = _pruefen(daten, zeilen, ordner, AUSNAHMEN_FELDER)
    assert not fehlend, "Feld weder im Export noch in AUSNAHMEN_FELDER:\n" + "\n".join(fehlend)
    assert not ueberfluessig, f"Ausnahme für ein Feld, das der Export führt: {ueberfluessig}"
    bekannt = {f"{modell.__name__}.{feld}" for _pfad, modell, gemerkt in zeilen for feld, _such in gemerkt}
    veraltet = set(AUSNAHMEN_FELDER) - bekannt
    assert not veraltet, f"Ausnahme für ein Feld, das es nicht gibt: {sorted(veraltet)}"
    assert all(grund.strip() for grund in AUSNAHMEN_FELDER.values())


def test_belastende_angaben_stehen_im_export_und_nicht_in_der_ausnahmeliste():
    """GP-089: Vertrauensfrage samt Stellungnahme, Gründe für Ruhen und Ausblendung, Vermerke der
    Verwaltung und der Vertrauensentzug gehören zum vollständigen Export."""
    pflicht = {
        "Vertrauensfrage.sperrhinweis", "Vertrauensfrage.entscheidung", "Vertrauensfrage.anlass_ausstaende",
        "Stellungnahme.text", "Stellungnahme.erstellt_am", "Rolle.ruht_seit", "Rolle.ruht_grund",
        "Kommentar.ausgeblendet_grund", "Kommentar.archiviert_am", "Anstoss.vermerk",
        "Mandat.vertrauen_entzogen_am", "Mandat.rueckgabe_ersucht_bis",
        "Antrag.zurueckweisung_begruendung", "AntragsFassung.wortlaut", "Mitglied.status_grund",
    }
    assert not pflicht & set(AUSNAHMEN_FELDER)
    for wort in ("vertrauen", "stellungnahme", "grund", "gruendung", "vermerk"):
        betroffen = [name for name in AUSNAHMEN_FELDER if wort in name.lower()]
        assert not betroffen, betroffen
    probe, zeilen, ordner = _markenzeilen()
    gefunden = {f"{modell.__name__}.{feld}" for _pfad, modell, gemerkt in zeilen for feld, _such in gemerkt}
    assert pflicht - {"Mitglied.status_grund"} <= gefunden, sorted(pflicht - gefunden)


def test_waechter_schlaegt_an_wenn_ein_feld_weder_exportiert_noch_ausgenommen_ist():
    """Die Probe auf den Wächter selbst: Ohne ihre Ausnahme gelten ausgelassene Felder als Lücke —
    so verhält sich ein neu ergänztes Feld, das der Export nicht nachzieht."""
    probe, zeilen, ordner = _markenzeilen()
    daten = daten_export(Mitglied.objects.get(pk=probe.pk))
    fehlend, _ueberfluessig = _pruefen(daten, zeilen, ordner, {})
    assert {eintrag.split(" ")[0] for eintrag in fehlend} == set(AUSNAHMEN_FELDER)
    # … und ein Feld, dessen Ordner im Export fehlt, fällt ebenso auf.
    ohne = {**daten, "rollen": []}
    fehlend, _ueberfluessig = _pruefen(ohne, zeilen, ordner, AUSNAHMEN_FELDER)
    assert any(eintrag.startswith("Rolle.ruht_grund ") for eintrag in fehlend)


def test_jedes_feld_des_kontos_steht_im_export_oder_begruendet_in_der_ausnahmeliste():
    felder = {f.name for f in Mitglied._meta.get_fields() if f.concrete and not f.many_to_many}
    unbekannt = felder - set(KONTO_PFADE) - set(KONTO_AUSNAHMEN)
    assert not unbekannt, f"Kontofeld weder im Export noch in KONTO_AUSNAHMEN: {sorted(unbekannt)}"
    veraltet = (set(KONTO_PFADE) | set(KONTO_AUSNAHMEN)) - felder
    assert not veraltet, f"Eintrag ohne Feld am Konto: {sorted(veraltet)}"
    assert not set(KONTO_PFADE) & set(KONTO_AUSNAHMEN) and all(KONTO_AUSNAHMEN.values())
    daten = daten_export(_mitglied("konto"))
    for feld, pfad in KONTO_PFADE.items():
        knoten = daten
        for teil in pfad:
            assert isinstance(knoten, dict) and teil in knoten, (feld, pfad)
            knoten = knoten[teil]
