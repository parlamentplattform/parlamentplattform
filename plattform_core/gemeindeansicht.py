"""Reihenfolge der öffentlichen Ortsübersicht, als ORM-Feldnamen ausführbar."""

VERSION = 2

ORTSREIHUNG = ("name", "bezirk", "kennziffer")
MANDATSREIHUNG = ("angetreten", "pk")
SITZUNGSREIHUNG = ("-beginn", "-pk")
SPRECHSTUNDENREIHUNG = ("beginn", "pk")
