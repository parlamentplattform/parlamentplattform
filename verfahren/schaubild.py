"""Gemeinsame Anzeige der aktuell beschlossenen Regeln, keine neue Verfahrensregel."""

from verfahren.models import Verfahrensordnung


def fristen_fuer_das_diagramm() -> dict:
    """Eine Registeränderung ist noch keine neue Verfahrensordnung.

    Bestehende Anträge lesen weiter nur ihre eigenen Schnappschüsse. Hier werden
    die Regeln für neue Sachanträge angezeigt, wie auch in der Einführung.
    """
    ordnung = Verfahrensordnung.objects.filter(aktiv=True).order_by("-version").first()
    if ordnung is None:
        return {}
    policy = ordnung.als_policy()
    return {
        "id": policy.id,
        "version": policy.version,
        "unterstuetzung": policy.unterstuetzung_frist_tage,
        "beratung": policy.beratung_tage,
        "abstimmung": policy.abstimmung_tage,
        "runden": policy.hoechstrunden,
        "beratung_entfaellt": policy.beratung_entfaellt,
    }
