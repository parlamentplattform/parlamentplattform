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

Verfahren ohne Beratungsphase (Policy `beratung_entfaellt`, § 7 Abs 10 lit c und e —
die Vertrauensfrage): UNTERSTUETZUNG ──Schwelle erreicht──▶ ABSTIMMUNG. Die Abstimmung
beginnt frühestens `abstimmung_fruehestens_tage` nach Phasenbeginn und spätestens
`abstimmung_spaetestens_tage_nach_schwelle` nach dem Erreichen der Schwelle; wann die
Schwelle erreicht wurde, sagt der Aufrufer (`schwelle_erreicht_am`) — die Plattform zählt
und veröffentlicht, der Kern rechnet nur.

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

#: Fassung der Übergangsregeln (§ 2 Abs 6): wann ein Antrag die Phase wechselt und mit
#: welchem Zeitpunkt der Wechsel gilt. Welche Fristen dabei gelten, steht in der am
#: Antrag eingefrorenen Verfahrensordnung — die trägt ihre eigene Versionsnummer.
#: Fassung 2 (15.9.2026): der Weg ohne Beratungsphase mit frühestem und spätestem
#: Abstimmungsbeginn (§ 7 Abs 10). Fassung 1 bleibt für alle anderen Ordnungen unverändert.
VERSION = 2


class Phase(enum.StrEnum):
    UNTERSTUETZUNG = "unterstuetzung"
    BERATUNG = "beratung"
    ABSTIMMUNG = "abstimmung"
    ANGENOMMEN = "angenommen"
    ABGELEHNT = "abgelehnt"
    VERFALLEN = "verfallen"  # Unterstützungsschwelle verfehlt
    ZURUECKGEWIESEN = "zurueckgewiesen"  # formal, nur durch Integritätsrat (§ 5 Abs 2)
    ZURUECKGEZOGEN = "zurueckgezogen"  # durch die Antragstellerin


END_PHASEN = frozenset(
    {Phase.ANGENOMMEN, Phase.ABGELEHNT, Phase.VERFALLEN, Phase.ZURUECKGEWIESEN, Phase.ZURUECKGEZOGEN}
)


@dataclass(frozen=True)
class Transition:
    """Ergebnis einer Übergangsprüfung."""

    neue_phase: Phase
    wirksam_ab: datetime  # der Zeitpunkt, ab dem die neue Phase gilt (deterministisch)
    grund: str  # menschenlesbare Begründung für das Audit-Log


def unterstuetzung_frist_ende(phase_beginn: datetime, policy: Policy) -> datetime:
    return phase_beginn + timedelta(days=policy.unterstuetzung_frist_tage)


def beratung_frist_ende(phase_beginn: datetime, policy: Policy) -> datetime:
    return phase_beginn + timedelta(days=policy.beratung_tage)


def abstimmung_frist_ende(phase_beginn: datetime, policy: Policy) -> datetime:
    return phase_beginn + timedelta(days=policy.abstimmung_tage)


def abstimmungsbeginn_ohne_beratung(
    phase_beginn: datetime, schwelle_erreicht_am: datetime, policy: Policy
) -> datetime:
    """Wann die Abstimmung eines Verfahrens ohne Beratungsphase beginnt (§ 7 Abs 10 lit e).

    Frühestens `abstimmung_fruehestens_tage` nach dem Beginn der Unterstützung, sonst mit dem
    Erreichen der Schwelle. Der Beginn ist damit immer der früheste zulässige Zeitpunkt — also
    nie später als `schwelle_erreicht_am + abstimmung_spaetestens_tage_nach_schwelle`, es sei
    denn, die Satzung verlangt die Wartezeit („frühestens jedoch am siebten Tag nach
    Einbringung“; dann geht sie vor)."""
    return max(schwelle_erreicht_am, phase_beginn + timedelta(days=policy.abstimmung_fruehestens_tage))


def _uebergang_ohne_beratung(
    phase_beginn: datetime,
    jetzt: datetime,
    policy: Policy,
    unterstuetzungen: int,
    schwelle_erreicht_am: datetime | None,
) -> Transition | None:
    """Unterstützungsphase eines Verfahrens ohne Beratung (Policy `beratung_entfaellt`).

    Die Schwelle gilt als erreicht, sobald `unterstuetzungen >= schwelle` — bei Schwelle 0 mit
    dem Phasenbeginn. Der Zeitpunkt kommt vom Aufrufer (`schwelle_erreicht_am`, die Plattform
    hat ihn beim Zählen festgehalten und veröffentlicht); fehlt er, gilt `jetzt`, begrenzt auf
    das Fristende, damit späte Verarbeitung keine Frist verschiebt. Ein übergebener Zeitpunkt
    gilt für sich: Das Erreichen ist veröffentlicht (§ 7 Abs 10 lit c) und eröffnet die
    Anfechtungsfrist (lit h) — eine danach zurückgezogene Unterstützung macht es nicht
    ungeschehen, so wie im Regelverfahren der sofortige Übergang in die Beratung. Eine
    Schwelle, die erst nach dem Fristende steht, zählt nicht: Der Antrag verfällt zum Fristende."""
    frist = unterstuetzung_frist_ende(phase_beginn, policy)
    erreicht = unterstuetzungen >= policy.unterstuetzung_schwelle or schwelle_erreicht_am is not None
    if erreicht:
        if policy.unterstuetzung_schwelle == 0:
            erreicht_am = phase_beginn
        elif schwelle_erreicht_am is not None:
            erreicht_am = schwelle_erreicht_am
        else:
            erreicht_am = min(jetzt, frist)
        if erreicht_am > frist:
            erreicht = False
    if erreicht:
        beginn = abstimmungsbeginn_ohne_beratung(phase_beginn, erreicht_am, policy)
        if jetzt < beginn:
            return None
        spaetestens = erreicht_am + timedelta(days=policy.abstimmung_spaetestens_tage_nach_schwelle)
        wartezeit = (
            " Die Wartezeit ab Einbringung geht dem spätesten Beginn vor." if beginn > spaetestens else ""
        )
        festgehalten = f" (festgehalten am {erreicht_am.isoformat()})" if schwelle_erreicht_am is not None else ""
        return Transition(
            Phase.ABSTIMMUNG,
            wirksam_ab=beginn,
            grund=(
                f"Unterstützungsschwelle erreicht: {unterstuetzungen}/"
                f"{policy.unterstuetzung_schwelle}{festgehalten}; ohne Beratungsphase beginnt die Abstimmung "
                f"frühestens {policy.abstimmung_fruehestens_tage} Tage nach Einbringung und spätestens "
                f"{policy.abstimmung_spaetestens_tage_nach_schwelle} Tage nach Erreichen der Schwelle "
                f"(§ 7 Abs 10 lit c und e).{wartezeit}"
            ),
        )
    if jetzt > frist:
        return Transition(
            Phase.VERFALLEN,
            wirksam_ab=frist,
            grund=(
                f"Unterstützungsfrist abgelaufen: {unterstuetzungen}/"
                f"{policy.unterstuetzung_schwelle} (§ 7 Abs 10 lit c)."
            ),
        )
    return None


def naechster_uebergang(
    phase: Phase,
    phase_beginn: datetime,
    jetzt: datetime,
    policy: Policy,
    unterstuetzungen: int,
    auszaehlung: Auszaehlung | None = None,
    schwelle_erreicht_am: datetime | None = None,
) -> Transition | None:
    """Prüft, ob aus dem gegebenen Zustand ein Übergang fällig ist.

    Gibt None zurück, wenn nichts zu tun ist. Die Funktion ist idempotent:
    Wer sie mit demselben Zustand mehrfach aufruft, bekommt dasselbe Ergebnis.

    Wichtig für die Nachvollziehbarkeit: `wirksam_ab` ist der *Fristzeitpunkt*
    (bzw. bei Schwellenerreichung `jetzt`), nicht der zufällige Moment, in dem
    ein Hintergrundjob lief. Verspätete Verarbeitung verfälscht dadurch keine
    nachgelagerten Fristen.

    `schwelle_erreicht_am` gilt nur für Ordnungen ohne Beratungsphase
    (`policy.beratung_entfaellt`): der vom Aufrufer festgehaltene Zeitpunkt, zu dem die
    Unterstützungsschwelle erreicht wurde — für die Vertrauensfrage zählt und veröffentlicht
    ihn die Plattform (§ 7 Abs 10 lit c), der Kern rechnet damit den Abstimmungsbeginn.
    """
    if phase in END_PHASEN:
        return None

    if phase is Phase.UNTERSTUETZUNG and policy.beratung_entfaellt:
        return _uebergang_ohne_beratung(phase_beginn, jetzt, policy, unterstuetzungen, schwelle_erreicht_am)

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
                return Transition(Phase.ANGENOMMEN, wirksam_ab=frist, grund=auszaehlung.begruendung)
            return Transition(Phase.ABGELEHNT, wirksam_ab=frist, grund=auszaehlung.begruendung)
        return None

    raise ValueError(f"Unbehandelte Phase: {phase!r}")  # pragma: no cover


def stimme_zulaessig(phase: Phase, phase_beginn: datetime, jetzt: datetime, policy: Policy) -> bool:
    """Eine Stimme ist genau dann zulässig, wenn die Abstimmung läuft und die
    Frist nicht abgelaufen ist. Diese Funktion ist die einzige Wahrheit darüber —
    Views, Importe von Papierstimmen und Tests benutzen alle dieselbe Prüfung."""
    if phase is not Phase.ABSTIMMUNG:
        return False
    return jetzt < abstimmung_frist_ende(phase_beginn, policy)
