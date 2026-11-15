"""Reihenfolge der öffentlichen Ortsübersicht, als ORM-Feldnamen ausführbar."""

VERSION = 5

ORTSREIHUNG = ("name", "bezirk", "kennziffer")
MANDATSREIHUNG = ("angetreten", "pk")
SITZUNGSREIHUNG = ("-beginn", "-pk")
SPRECHSTUNDENREIHUNG = ("beginn", "pk")
RATSINITIATIVENREIHUNG = ("-veroeffentlicht_am", "-pk")
RATSVERLAUFSREIHUNG = ("eingetragen_am", "pk")
SITZUNGSQUELLENREIHUNG = ("-sitzung_am", "-aufgabe_id", "art")
HAUSHALTSQUELLENREIHUNG = ("-jahr", "art", "mandat_id")
