"""Der Phasenautomat: § 5 Abs 3 der Satzung als Zustandsmaschine.

    EINGEBRACHT ──sofort──▶ UNTERSTUETZUNG ──Schwelle erreicht──▶ BERATUNG
                                 │                                   │
                          Frist abgelaufen                    Beratungsfrist um
                                 ▼                                   ▼
                             VERFALLEN                          ABSTIMMUNG
                                                                     │
                                                              Abstimmungsfrist um
                                                                     ▼
                                                       ANGENOMMEN oder ABGELEHNT

Grundsätze:
- Übergänge geschehen ausschließlich durch Zeitablauf oder das Erreichen einer
  in der eingefrorenen Policy definierten Schwelle — nie durch Administratorwillkür.
  Die einzige Ausnahme ist die formale Zurückweisung durch den Integritätsrat
  (§ 5 Abs 2), die als eigener, begründungspflichtiger Verwaltungsakt außerhalb
  dieses Automaten modelliert ist.
- Alle Funktionen sind rein: gleiche Eingaben ergeben immer denselben Übergang.
  Die "Uhr" wird stets als Parameter übergeben, nie aus der Systemzeit gelesen —
  dadurch ist jeder historische Zustand exakt reproduzierbar.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime, timedelta

from plattform_core.policy import Policy
from plattform_core.tally import Auszaehlung


class Phase(enum.StrEnum):
    UNTERSTUETZUNG = "unterstuetzung"
    BERATUNG = "beratung"
    ABSTIMMUNG = "abstimmung"
    ANGENOMMEN = "angenommen"
    ABGELEHNT = "abgelehnt"
    VERFALLEN = "verfallen"                 # Unterstützungsschwelle verfehlt
    ZURUECKGEWIESEN = "zurueckgewiesen"     # formal, nur durch Integritätsrat (§ 5 Abs 2)
    ZURUECKGEZOGEN = "zurueckgezogen"       # durch die Antragstellerin

END_PHASEN = frozenset(
    {Phase.ANGENOMMEN, Phase.ABGELEHNT, Phase.VERFALLEN, Phase.ZURUECKGEWIESEN, Phase.ZURUECKGEZOGEN}
)


@dataclass(frozen=True)
class Transition:
    """Ergebnis einer Übergangsprüfung."""

    neue_phase: Phase
    wirksam_ab: datetime  # der Zeitpunkt, ab dem die neue Phase gilt (deterministisch)
    grund: str            # menschenlesbare Begründung für das Audit-Log


def unterstuetzung_frist_ende(phase_beginn: datetime, policy: Policy) -> datetime:
    return phase_beginn + timedelta(days=policy.unterstuetzung_frist_tage)


def beratung_frist_ende(phase_beginn: datetime, policy: Policy) -> datetime:
    return phase_beginn + timedelta(days=policy.beratung_tage)


def abstimmung_frist_ende(phase_beginn: datetime, policy: Policy) -> datetime:
    return phase_beginn + timedelta(days=policy.abstimmung_tage)


def naechster_uebergang(
    phase: Phase,
    phase_beginn: datetime,
    jetzt: datetime,
    policy: Policy,
    unterstuetzungen: int,
    auszaehlung: Auszaehlung | None = None,
) -> Transition | None:
    """Prüft, ob aus dem gegebenen Zustand ein Übergang fällig ist.

    Gibt None zurück, wenn nichts zu tun ist. Die Funktion ist idempotent:
    Wer sie mit demselben Zustand mehrfach aufruft, bekommt dasselbe Ergebnis.

    Wichtig für die Nachvollziehbarkeit: `wirksam_ab` ist der *Fristzeitpunkt*
    (bzw. bei Schwellenerreichung `jetzt`), nicht der zufällige Moment, in dem
    ein Hintergrundjob lief. Verspätete Verarbeitung verfälscht dadurch keine
    nachgelagerten Fristen.
    """
    if phase in END_PHASEN:
        return None

    if phase is Phase.UNTERSTUETZUNG:
        frist = unterstuetzung_frist_ende(phase_beginn, policy)
        if unterstuetzungen >= policy.unterstuetzung_schwelle and jetzt <= frist:
            return Transition(
                Phase.BERATUNG,
                wirksam_ab=jetzt,
                grund=(
                    f"Unterstützungsschwelle erreicht: {unterstuetzungen}/"
                    f"{policy.unterstuetzung_schwelle} innerhalb der Frist (§ 5 Abs 3 lit b)."
                ),
            )
        if jetzt > frist:
            if unterstuetzungen >= policy.unterstuetzung_schwelle:
                # Schwelle war bei Fristablauf bereits erreicht, Verarbeitung kam spät:
                # Übergang gilt rückwirkend zum Fristende, nicht zum Jobzeitpunkt.
                return Transition(
                    Phase.BERATUNG,
                    wirksam_ab=frist,
                    grund="Schwelle bei Fristablauf erreicht; Übergang wirksam zum Fristende.",
                )
            return Transition(
                Phase.VERFALLEN,
                wirksam_ab=frist,
                grund=(
                    f"Unterstützungsfrist abgelaufen: {unterstuetzungen}/"
                    f"{policy.unterstuetzung_schwelle}. Wiedereinbringung nach "
                    f"{policy.wiedereinbringung_sperre_monate} Monaten möglich (§ 5 Abs 3 lit b)."
                ),
            )
        return None

    if phase is Phase.BERATUNG:
        frist = beratung_frist_ende(phase_beginn, policy)
        if jetzt >= frist:
            return Transition(
                Phase.ABSTIMMUNG,
                wirksam_ab=frist,
                grund=f"Beratungsphase von {policy.beratung_tage} Tagen beendet (§ 5 Abs 3 lit c).",
            )
        return None

    if phase is Phase.ABSTIMMUNG:
        frist = abstimmung_frist_ende(phase_beginn, policy)
        if jetzt >= frist:
            if auszaehlung is None:
                raise ValueError(
                    "Abstimmungsfrist erreicht, aber keine Auszählung übergeben — "
                    "der Aufrufer muss vor dem Übergang auszählen."
                )
            if auszaehlung.angenommen:
                return Transition(
                    Phase.ANGENOMMEN, wirksam_ab=frist, grund=auszaehlung.begruendung
                )
            return Transition(
                Phase.ABGELEHNT, wirksam_ab=frist, grund=auszaehlung.begruendung
            )
        return None

    raise ValueError(f"Unbehandelte Phase: {phase!r}")  # pragma: no cover


def stimme_zulaessig(phase: Phase, phase_beginn: datetime, jetzt: datetime, policy: Policy) -> bool:
    """Eine Stimme ist genau dann zulässig, wenn die Abstimmung läuft und die
    Frist nicht abgelaufen ist. Diese Funktion ist die einzige Wahrheit darüber —
    Views, Importe von Papierstimmen und Tests benutzen alle dieselbe Prüfung."""
    if phase is not Phase.ABSTIMMUNG:
        return False
    return jetzt < abstimmung_frist_ende(phase_beginn, policy)
