"""Altersgrenze der freiwilligen Gemeindeanmeldung, keine Abstimmungszulassung."""

from datetime import date

VERSION = 1


def mindestens_sechzehn(geburt: date, heute: date) -> bool:
    """Vollendete Lebensjahre am Anmeldetag; keine bloße Geburtsjahrdifferenz."""
    return heute.year - geburt.year - ((heute.month, heute.day) < (geburt.month, geburt.day)) >= 16
