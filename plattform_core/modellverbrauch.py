"""Gespeicherte Laufangaben zusammenfassen, ohne Rechnung oder Preisannahme."""

VERSION = 1
ZAHLEN = ("laeufe", "fehlversuche", "tokens_ein", "tokens_aus", "dauer_ms")


def zusammenfassen(zeilen):
    """Vier bekannte Zwecke plus Sonstige; keine Relevanzsortierung/Teilmengengrenze."""
    if not isinstance(zeilen, list) or len(zeilen) > 5:
        raise ValueError("Verbrauchsgruppen")
    werte = []
    for zeile in zeilen:
        if (
            not isinstance(zeile, dict) or set(zeile) != {"zweck", *ZAHLEN}
            or not isinstance(zeile["zweck"], str) or not 0 < len(zeile["zweck"]) <= 20
            or any(type(zeile[k]) is not int or zeile[k] < 0 for k in ZAHLEN)
            or zeile["fehlversuche"] > zeile["laeufe"]
        ):
            raise ValueError("Verbrauchsangaben")
        werte.append(dict(zeile))
    if len({z["zweck"] for z in werte}) != len(werte):
        raise ValueError("Doppelter Zweck")
    return {
        "version": VERSION, "zeilen": sorted(werte, key=lambda z: z["zweck"]),
        "summe": {k: sum(z[k] for z in werte) for k in ZAHLEN},
        # Das Archiv enthält weder einen damaligen Tarif noch eine Abrechnung.
        "kosten": {"betrag": None, "waehrung": None, "nachweis": "nicht_erfasst"},
    }
