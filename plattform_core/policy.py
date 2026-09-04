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

# Mindestwerte aus der Satzung — eine Policy darf diese niemals unterschreiten.
SATZUNG_MIN_BERATUNG_TAGE = 21  # § 5 Abs 3 lit c
SATZUNG_MIN_ABSTIMMUNG_TAGE = 7  # § 5 Abs 3 lit d
SATZUNG_MIN_BETEILIGUNG = 0.05  # § 5 Abs 4 — satzungsfeste Untergrenze


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
        if self.mindestbeteiligung < SATZUNG_MIN_BETEILIGUNG:
            raise PolicyFehler(
                f"Mindestbeteiligung {self.mindestbeteiligung} unterschreitet "
                f"Satzungsminimum {SATZUNG_MIN_BETEILIGUNG} (§ 5 Abs 4)."
            )
        if self.unterstuetzung_schwelle < 1:
            raise PolicyFehler("Unterstützungsschwelle muss mindestens 1 sein.")
        if self.unterstuetzung_frist_tage < 1:
            raise PolicyFehler("Unterstützungsfrist muss mindestens 1 Tag sein.")
        if self.mehrheitsbasis not in ("ja_nein", "abgegeben"):
            raise PolicyFehler(f"Unbekannte Mehrheitsbasis: {self.mehrheitsbasis!r}")

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
    "unterstuetzung_frist_tage": ("verfahren-unterstuetzung-tage", int),
    "beratung_tage": ("expertenrat-erstvorschlag-tage", int),
    "abstimmung_tage": ("verfahren-abstimmung-tage", int),
    "mindestbeteiligung": ("verfahren-mindestbeteiligung-prozent", lambda n: n / 100),
    "wiedereinbringung_sperre_monate": ("verfahren-wiedereinbringung-monate", int),
}


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
    return Policy(id=policy_id, version=version, mehrheitsbasis=mehrheitsbasis, **felder)

