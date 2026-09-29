"""Policy: die Verfahrensregeln eines Antrags — versioniert, eingefroren, nachlesbar.

Eine Policy ist die maschinenlesbare Fassung der Verfahrensordnung für einen
Beschlussgegenstand. Beim Einbringen eines Antrags wird die dann gültige Policy
als unveränderliche Kopie am Antrag gespeichert (Satzung § 5 Abs 5 — das
Rückwirkungsverbot). Der Phasenautomat und die Auszählung arbeiten ausschließlich
mit dieser Kopie, niemals mit der "aktuellen" Fassung.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from plattform_core.losziehung import SATZUNG_MIN_RATSGROESSE

#: Fassung der Ordnungsregeln (§ 2 Abs 6): welche Felder eine Verfahrensordnung hat, wie
#: sie aus dem Register entsteht und welche satzungsfesten Grenzen sie nicht
#: überschreiten darf. Die einzelne Ordnung trägt daneben ihre eigene `version`.
#: Seit 0.45 gehören auch die Fristen, Runden und die Annahme-Schwelle der Entwurfsschleife
#: (§ 5 Abs 12) zur Ordnung — bis dahin las die Schleife sie live aus dem Register. Die
#: Fassungsnummer wird zusammen mit dem Eintrag im Regelverzeichnis angehoben
#: (`plattform_core.regelwerk`), nicht für sich allein: Das Verzeichnis prüft, dass beide
#: dasselbe sagen.
#: Seit 0.48 (Fassung 3) kennt die Ordnung Verfahren ohne Beratungsphase mit frühestem und
#: spätestem Abstimmungsbeginn — die Vertrauensfrage nach § 7 Abs 10. Die drei Felder tragen
#: Vorgaben, die jeden älteren Snapshot unverändert lassen.
#: Fassung 4 (29.9.2026): Die Unterstützungsschwelle kann als Anteil der Stimmberechtigten
#: gelten (`unterstuetzung_anteil`, Mindestzahl `unterstuetzung_schwelle`); beim Einbringen wird
#: daraus die konkrete Zahl gerechnet und samt Grundgesamtheit eingefroren (§ 5 Abs 5).
#: Fassung 5 (0.51.0): Die Übergangsregel des § 4 Abs 4 lit d wird beim Einbringen aus der
#: Einstellung der Instanz übernommen und gilt bis zum Ende des Verfahrens (`uebergangsregel`,
#: Bestandsaufnahme A5); dazu der schlafende Schalter für die Tendenz während der Abstimmung
#: (`tendenz_ab_mindestbeteiligung`, D-D2 b).
VERSION = 5

# Mindestwerte aus der Satzung — eine Policy darf diese niemals unterschreiten.
SATZUNG_MIN_BERATUNG_TAGE = 21  # § 5 Abs 3 lit c
SATZUNG_MIN_ABSTIMMUNG_TAGE = 7  # § 5 Abs 3 lit d
SATZUNG_MIN_BETEILIGUNG = 0.05  # § 5 Abs 4 — satzungsfeste Untergrenze
# Höchstwert aus der Satzung: § 5 Abs 12 gibt den Unterstützern und dem Expertenrat je Runde
# „binnen 14 Tagen" — eine Obergrenze, kein Minimum. Eine Ordnung darf kürzer sein, nie länger.
SATZUNG_MAX_SCHLEIFENFRIST_TAGE = 14  # § 5 Abs 12
# Die Vertrauensfrage (§ 7 Abs 10) — Spiegel der Satzung, keine Stellgrößen des Registers (lit k):
# Die Prozentschwelle, Höchst- und Mindestfristen darf die Verfahrensordnung weder unter- noch
# überschreiten; sie sind dem Parameterverfahren entzogen.
SATZUNG_VERTRAUENSFRAGE_ANTEIL = 0.05  # lit c: fünf Prozent der für Personenwahlen Stimmberechtigten
SATZUNG_MAX_VERTRAUENSFRAGE_SAMMELFRIST_TAGE = 30  # lit c: Sammelfrist von höchstens 30 Tagen
VERTRAUENSFRAGE_FRUEHESTENS_TAGE = 7  # lit e: Abstimmung frühestens am siebten Tag nach Einbringung
VERTRAUENSFRAGE_SPAETESTENS_TAGE = 3  # lit e: spätestens am dritten Tag nach Erreichen der Schwelle


class PolicyFehler(ValueError):
    """Eine Policy verletzt die satzungsfesten Untergrenzen oder ist unvollständig."""


@dataclass(frozen=True)
class Policy:
    """Eingefrorene Verfahrensregeln. `frozen=True` ist Absicht: Instanzen sind
    unveränderlich, so wie es § 5 Abs 5 für laufende Verfahren verlangt."""

    id: str  # z. B. "sachantrag-standard"
    version: int  # Version der Verfahrensordnung
    unterstuetzung_schwelle: int  # absolute Zahl an Unterstützungen
    unterstuetzung_frist_tage: int  # Frist für die Unterstützungsphase
    beratung_tage: int  # Dauer der Beratungsphase (>= 21)
    abstimmung_tage: int  # Dauer der Abstimmungsphase (>= 7)
    mindestbeteiligung: float  # Anteil der Stimmberechtigten (>= 0.05)
    mehrheitsbasis: str = "ja_nein"  # "ja_nein": Ja > Nein.
    #                                      "abgegeben": Ja > Hälfte aller
    #                                      abgegebenen Stimmen inkl. Enthaltung.
    #                                      Welche Basis gilt, beschließt die
    #                                      Verfahrensordnung — nicht der Code.
    wiedereinbringung_sperre_monate: int = 6  # § 5 Abs 3 lit b
    # Auslosung des Expertenrats (§ 6 Abs 7). Sie geschieht erst zu Beratungsbeginn, also
    # rund zwei Monate nach dem Einbringen — deshalb gehören Größen und Regelfassung hierher
    # und nicht ins laufende Register: Sonst wirkte eine Änderung zurück (§ 5 Abs 5).
    expertenrat_gruppe1: int = 3  # >= 3 (§ 6 Abs 8)
    expertenrat_gruppe2: int = 3  # >= 3, nur bei Vollzugs- oder Beschaffungsbezug gezogen
    losregel_fassung: int = 1  # plattform_core.losziehung.VERSION zum Zeitpunkt der Fassung
    # Die Entwurfsschleife (§ 5 Abs 12). Sie entscheidet Monate nach dem Einbringen, ob ein
    # Vorschlag zur Endabstimmung geht oder zurück in die Werkstatt — und § 5 Abs 5 schreibt
    # Schwellen, Fristen und Auswertungsregeln beim Einbringen fest: „Ein Verstoß macht die
    # betroffene Abstimmung ungültig." Deshalb stehen sie hier und nicht im laufenden Register.
    # Die Vorgaben sind die Registerwerte des Erstbestands; ältere Snapshots ohne diese Felder
    # laden damit unverändert (`aus_dict` ergänzt nur Fehlendes, nie Fremdes).
    vorschlag_annahme_anteil: float = 0.5  # „Passt alles" muss diesen Anteil überschreiten
    hoechstrunden: int = 3  # Runden der Schleife, danach in jedem Fall Endabstimmung
    review_tage: int = 14  # Frist der Unterstützer je Runde (<= 14, § 5 Abs 12)
    ueberarbeitung_tage: int = 14  # Frist des Expertenrats je Rückgabe (<= 14, § 5 Abs 12)
    pruefung_tage: int = 7  # Frist der Gruppe 2 für ihre Prüfung (§ 6 Abs 7)
    # Verfahren ohne Beratungsphase (§ 7 Abs 10 lit c und e: die Vertrauensfrage). Ist
    # `beratung_entfaellt` gesetzt, geht es aus der Unterstützung unmittelbar in die Abstimmung;
    # sie beginnt frühestens `abstimmung_fruehestens_tage` nach Phasenbeginn und spätestens
    # `abstimmung_spaetestens_tage_nach_schwelle` nach dem Erreichen der Schwelle (0 = sofort).
    # Mit `beratung_entfaellt` darf die Unterstützungsschwelle 0 sein — sie gilt dann mit dem
    # Einbringen als erreicht (Bestätigungsantrag nach § 7 Abs 10 lit f Z 3). Die Vorgaben sind
    # das bisherige Verhalten: ältere Snapshots laden unverändert.
    beratung_entfaellt: bool = False
    abstimmung_fruehestens_tage: int = 0
    abstimmung_spaetestens_tage_nach_schwelle: int = 0
    # Fassung 4: Die Schwelle als Anteil der am Einbringungstag Stimmberechtigten (0 = aus; Anweisung
    # des Gründers 29.9.2026: „wir fangen mit 50 % an“). `unterstuetzung_schwelle` ist dann die
    # Mindestzahl; die beim Einbringen gerechnete Zahl ersetzt sie im Schnappschuss des Antrags,
    # und `unterstuetzung_grundgesamtheit` hält fest, aus wie vielen Stimmberechtigten sie entstand.
    unterstuetzung_anteil: float = 0.0
    unterstuetzung_grundgesamtheit: int = 0
    unterstuetzung_mindestzahl: int = 0  # die Mindestzahl der Ordnung, wenn die Schwelle gerechnet wurde
    # Fassung 5: Die Übergangsregel des § 4 Abs 4 lit d („entfällt die Anwartschaft“) — eine Einstellung
    # der Instanz (`DDOE_UEBERGANGSREGEL`), kein Registerwert. Beim Einbringen gesetzt; Zählung der
    # Stimmberechtigten, Prüfung jeder Stimme, Bewerbung und Unterstützung lesen sie von da an nur hier.
    # Die Vorgabe ist der Wert jeder bekannten Instanz und der Standard der Einstellung: Ältere
    # Schnappschüsse ohne das Feld laden damit so, wie sie gerechnet wurden.
    uebergangsregel: bool = True
    # Fassung 5: D-D2 (b) als schlafender Schalter — ob Kachel, Antragsseite und Übersicht während einer
    # laufenden Abstimmung die Tendenz (Ja, Nein, Enthaltung) zeigen, sobald die Mindestbeteiligung
    # erreicht ist. 0 = verdeckt bis zum Fristende (Voreinstellung, D-D2 a); 1 = sichtbar ab erreichter
    # Mindestbeteiligung. Ein „immer“ gibt es nicht. Eingefroren wie jede Regel, die während einer
    # Abstimmung gilt (§ 5 Abs 5); gilt nur für Sachanträge (`tally.tendenz_sichtbar`).
    tendenz_ab_mindestbeteiligung: int = 0

    def __post_init__(self) -> None:
        if self.beratung_tage < SATZUNG_MIN_BERATUNG_TAGE:
            raise PolicyFehler(
                f"Beratung {self.beratung_tage} Tage unterschreitet Satzungsminimum "
                f"{SATZUNG_MIN_BERATUNG_TAGE} (§ 5 Abs 3 lit c)."
            )
        if self.abstimmung_tage < SATZUNG_MIN_ABSTIMMUNG_TAGE:
            raise PolicyFehler(
                f"Abstimmung {self.abstimmung_tage} Tage unterschreitet Satzungsminimum "
                f"{SATZUNG_MIN_ABSTIMMUNG_TAGE} (§ 5 Abs 3 lit d)."
            )
        for name, wert in (
            ("expertenrat_gruppe1", self.expertenrat_gruppe1),
            ("expertenrat_gruppe2", self.expertenrat_gruppe2),
        ):
            if wert < SATZUNG_MIN_RATSGROESSE:
                raise PolicyFehler(
                    f"{name} = {wert} unterschreitet das Satzungsminimum "
                    f"{SATZUNG_MIN_RATSGROESSE} (§ 6 Abs 8)."
                )
        if self.mindestbeteiligung < SATZUNG_MIN_BETEILIGUNG:
            raise PolicyFehler(
                f"Mindestbeteiligung {self.mindestbeteiligung} unterschreitet "
                f"Satzungsminimum {SATZUNG_MIN_BETEILIGUNG} (§ 5 Abs 4)."
            )
        if self.unterstuetzung_schwelle < 0 or (
            self.unterstuetzung_schwelle == 0 and not self.beratung_entfaellt
        ):
            raise PolicyFehler(
                "Unterstützungsschwelle muss mindestens 1 sein — 0 nur ohne Beratungsphase "
                "(Bestätigungsantrag, § 7 Abs 10 lit f Z 3)."
            )
        if self.unterstuetzung_frist_tage < 1:
            raise PolicyFehler("Unterstützungsfrist muss mindestens 1 Tag sein.")
        if not 0 <= self.unterstuetzung_anteil <= 1:
            raise PolicyFehler(
                f"unterstuetzung_anteil = {self.unterstuetzung_anteil} liegt nicht zwischen 0 und 1."
            )
        if self.unterstuetzung_grundgesamtheit < 0 or self.unterstuetzung_mindestzahl < 0:
            raise PolicyFehler("Grundgesamtheit und Mindestzahl der Unterstützung dürfen nicht negativ sein.")
        for name, wert in (
            ("abstimmung_fruehestens_tage", self.abstimmung_fruehestens_tage),
            ("abstimmung_spaetestens_tage_nach_schwelle", self.abstimmung_spaetestens_tage_nach_schwelle),
        ):
            if wert < 0:
                raise PolicyFehler(f"{name} darf nicht negativ sein.")
        if not self.beratung_entfaellt and (
            self.abstimmung_fruehestens_tage or self.abstimmung_spaetestens_tage_nach_schwelle
        ):
            raise PolicyFehler(
                "Frühester und spätester Abstimmungsbeginn gelten nur für Verfahren ohne Beratungsphase "
                "(beratung_entfaellt)."
            )
        if self.mehrheitsbasis not in ("ja_nein", "abgegeben"):
            raise PolicyFehler(f"Unbekannte Mehrheitsbasis: {self.mehrheitsbasis!r}")
        for name, wert in (("review_tage", self.review_tage), ("ueberarbeitung_tage", self.ueberarbeitung_tage)):
            if wert < 1:
                raise PolicyFehler(f"{name} muss mindestens 1 Tag sein.")
            if wert > SATZUNG_MAX_SCHLEIFENFRIST_TAGE:
                raise PolicyFehler(
                    f"{name} = {wert} überschreitet die Satzungsfrist von "
                    f"{SATZUNG_MAX_SCHLEIFENFRIST_TAGE} Tagen (§ 5 Abs 12: „binnen 14 Tagen“)."
                )
        if self.pruefung_tage < 1:
            raise PolicyFehler("pruefung_tage muss mindestens 1 Tag sein.")
        if self.hoechstrunden < 1:
            raise PolicyFehler("hoechstrunden muss mindestens 1 sein.")
        if self.tendenz_ab_mindestbeteiligung not in (0, 1):
            raise PolicyFehler(
                f"tendenz_ab_mindestbeteiligung = {self.tendenz_ab_mindestbeteiligung!r} ist weder 0 noch 1."
            )
        if not isinstance(self.uebergangsregel, bool):
            raise PolicyFehler(f"uebergangsregel = {self.uebergangsregel!r} ist kein Wahrheitswert.")
        if not 0 <= self.vorschlag_annahme_anteil < 1:
            raise PolicyFehler(
                f"vorschlag_annahme_anteil = {self.vorschlag_annahme_anteil} liegt nicht zwischen 0 und 1."
            )

    def als_dict(self) -> dict[str, Any]:
        """Serialisierung für den Policy-Snapshot am Antrag (JSON-Feld)."""
        return asdict(self)

    @classmethod
    def aus_dict(cls, daten: dict[str, Any]) -> Policy:
        """Deserialisierung eines Snapshots. Wirft PolicyFehler bei ungültigen Daten —
        auch historische Snapshots müssen den Satzungsminima genügt haben."""
        erlaubt = {f for f in cls.__dataclass_fields__}
        unbekannt = set(daten) - erlaubt
        if unbekannt:
            raise PolicyFehler(f"Unbekannte Policy-Felder: {sorted(unbekannt)}")
        return cls(**daten)


#: Welcher Registerschlüssel welches Feld der Verfahrensordnung speist (FB-J1).
#: Werte, die keine ganze Zahl sind, tragen ihren Umrechner mit — das Register führt nur ganze
#: Zahlen, weil sich Dezimalwerte in einem Formular schlecht bearbeiten und schlecht vergleichen lassen.
REGISTER_ZUORDNUNG = {
    "unterstuetzung_schwelle": ("verfahren-unterstuetzung-schwelle", int),
    "unterstuetzung_anteil": ("verfahren-unterstuetzung-anteil-prozent", lambda n: n / 100),
    "unterstuetzung_frist_tage": ("verfahren-unterstuetzung-tage", int),
    "beratung_tage": ("expertenrat-erstvorschlag-tage", int),
    "abstimmung_tage": ("verfahren-abstimmung-tage", int),
    "mindestbeteiligung": ("verfahren-mindestbeteiligung-prozent", lambda n: n / 100),
    "wiedereinbringung_sperre_monate": ("verfahren-wiedereinbringung-monate", int),
    "expertenrat_gruppe1": ("expertenrat-gruppe1-groesse", int),
    "expertenrat_gruppe2": ("expertenrat-gruppe2-groesse", int),
    # Die Entwurfsschleife (§ 5 Abs 12) — seit Fassung 2 Teil der eingefrorenen Ordnung.
    "vorschlag_annahme_anteil": ("vorschlag-annahme-prozent", lambda n: n / 100),
    "hoechstrunden": ("gremien-hoechstrunden", int),
    "review_tage": ("gremien-review-tage", int),
    "ueberarbeitung_tage": ("gremien-ueberarbeitung-tage", int),
    "pruefung_tage": ("gremien-pruefung-tage", int),
    # Fassung 5: nur der Wert 1 schaltet ein, alles andere wirkt wie 0 (wie jeder Schalter im Register).
    "tendenz_ab_mindestbeteiligung": ("verfahren-tendenz-ab-mindestbeteiligung", lambda n: 1 if n == 1 else 0),
}


def unterstuetzungsschwelle(mindestzahl: int, anteil: float, stimmberechtigte: int) -> int:
    """Die konkrete Unterstützungsschwelle eines Antrags am Einbringungstag (Fassung 4).

    Gilt ein Anteil, ist die Schwelle der aufgerundete Anteil der Stimmberechtigten — nie unter
    der Mindestzahl. Ohne Anteil (0) bleibt es bei der Mindestzahl. Nachrechnen: 50 % von 5
    Stimmberechtigten sind 2,5 → 3; mit Mindestzahl 3 bleibt es 3; 50 % von 50 sind 25."""
    if anteil <= 0:
        return mindestzahl
    return max(mindestzahl, -(-int(round(anteil * stimmberechtigte * 1_000_000)) // 1_000_000))


def aus_register(
    werte: dict[str, int], policy_id: str, version: int, mehrheitsbasis: str = "ja_nein"
) -> Policy:
    """Baut eine Verfahrensordnung aus Registerwerten (FB-J1).

    `werte` bildet Registerschlüssel auf ganze Zahlen ab — genau das, was `parameter.zahl`
    liefert. Fehlt ein Schlüssel, wirft diese Funktion: Eine Ordnung mit stillschweigend
    ergänzten Werten wäre schlimmer als gar keine, weil niemand sähe, was fehlt.

    Die Satzungsminima prüft die Policy selbst (`__post_init__`) — auch eine aus dem Register
    erzeugte Fassung darf sie nicht unterschreiten. Wer im Register eine Beratungsdauer unter
    21 Tagen einträgt, bekommt hier einen Fehler statt einer satzungswidrigen Ordnung.

    Diese Funktion erzeugt immer eine **neue** Fassung; bestehende bleiben unberührt, damit
    laufende Verfahren ihre eingefrorene Kopie behalten (§ 5 Abs 5)."""
    fehlend = sorted(
        schluessel
        for _feld, (schluessel, _wandler) in REGISTER_ZUORDNUNG.items()
        if schluessel not in werte
    )
    if fehlend:
        raise PolicyFehler(
            "Im Register fehlen Werte für die Verfahrensordnung: " + ", ".join(fehlend)
        )
    felder = {
        feld: wandler(werte[schluessel])
        for feld, (schluessel, wandler) in REGISTER_ZUORDNUNG.items()
    }
    from plattform_core.losziehung import VERSION as LOSREGEL

    return Policy(
        id=policy_id,
        version=version,
        mehrheitsbasis=mehrheitsbasis,
        losregel_fassung=LOSREGEL,
        **felder,
    )

