"""plattform_core — der framework-freie Verfahrenskern der ParlamentPlattform.

Dieses Paket enthält die vollständige Verfahrenslogik als reine Funktionen:
Phasenautomat, Fristen, Stimmberechtigung, Auszählung und Audit-Hash-Kette.
Es hat bewusst keine Abhängigkeit zu Django oder einer Datenbank, damit es

1. isoliert und erschöpfend testbar ist,
2. von jedem Menschen mit Python-Grundkenntnissen gelesen werden kann
   (Satzung § 5 Abs 8: Überprüfbarkeit ohne Spezialkenntnisse), und
3. im Zweifel unabhängig von der Plattform nachgerechnet werden kann
   (siehe verify/nachrechnen.py im Repository).

Änderungen an diesem Paket brauchen: einen Test, der das neue Verhalten
festschreibt, und — bei Verhaltensänderung — einen Eintrag im CHANGELOG.
"""

from plattform_core.eligibility import Gegenstand, stimmberechtigt
from plattform_core.hashchain import GENESIS, ereignis_hash, kette_pruefen
from plattform_core.phases import Phase, Transition, naechster_uebergang
from plattform_core.policy import Policy
from plattform_core.tally import Auszaehlung, Stimme, auszaehlen

__all__ = [
    "Policy",
    "Phase",
    "Transition",
    "naechster_uebergang",
    "Stimme",
    "Auszaehlung",
    "auszaehlen",
    "stimmberechtigt",
    "Gegenstand",
    "GENESIS",
    "ereignis_hash",
    "kette_pruefen",
]

__version__ = "0.42.0"
