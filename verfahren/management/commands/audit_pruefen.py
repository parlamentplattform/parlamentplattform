"""Die Audit-Kette nachrechnen: `python manage.py audit_pruefen [--voll]` (Bestandsaufnahme A7).

Ohne `--voll` rechnet der Befehl ab dem Stand weiter, den der tägliche Hintergrundlauf zuletzt geprüft
hat; mit `--voll` die ganze Kette von vorn (etwa nach einer Wiederherstellung aus der Sicherung). Er
schreibt nichts. Stimmt die Kette nicht, endet er mit Fehlercode und nennt die laufende Nummer des
ersten Eintrags, der nicht stimmt — für die CI und die Wiederherstellungsprobe."""

from django.core.management.base import BaseCommand, CommandError

from verfahren.audit_pruefung import gemerkter_stand, pruefen

GRUENDE = {
    "hash": "Inhalt passt nicht zum Hash — der Eintrag wurde verändert",
    "vorgaenger": "hängt nicht am Hash des Vorgängers — ein Eintrag wurde entfernt, eingeschoben oder umgehängt",
    "anker": "der zuletzt geprüfte Eintrag ist verändert oder fehlt",
}


class Command(BaseCommand):
    help = "Rechnet die Audit-Kette nach (stückweise oder mit --voll von vorn) und meldet eine Bruchstelle."

    def add_arguments(self, parser):
        parser.add_argument("--voll", action="store_true", help="die ganze Kette von vorn nachrechnen")

    def handle(self, *args, voll=False, **optionen):
        stand = pruefen(voll=voll, stand=None if voll else gemerkter_stand())
        art = "vollständig" if stand["voll"] else "ab dem gemerkten Stand"
        if not stand["intakt"]:
            raise CommandError(
                f"Audit-Kette gebrochen bei Eintrag {stand['bruch']}: {GRUENDE.get(stand['grund'], stand['grund'])} "
                f"({stand['geprueft']} Einträge {art} geprüft, bis dahin stimmig bis Eintrag {stand['geprueft_bis']})."
            )
        self.stdout.write(
            f"Audit-Kette intakt: {stand['geprueft']} Einträge {art} geprüft, "
            f"{stand['eintraege']} insgesamt, Kopf {stand['kopf']}."
        )
