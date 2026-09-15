"""Die Mandatar-Steuerung, Stufe M1 (§ 7 Abs 9 E-2.5, F-71).

Ein öffentlicher Bereich je Mandatsträger: Lichtbild, aktuelle Aufgaben und
laufende Entscheidungsprozesse samt Fristen — und die daraus entstehenden,
vom Mandatar betreuten Abstimmungen (verknüpfte Anträge, F-70). Die Pflicht,
diese Informationen einzustellen, kommt aus der Mandatsvereinbarung
(§ 7 Abs 3 lit b); die Plattform macht sie sichtbar. Seit 0.46 pflegt der
Mandatar den Bereich selbst: Die Rolle „Mandatar“ ist abgeleitet (offenes
Mandat, `Mitglied.ist_mandatar`), der Instant-Report ist die `Aufgabe` mit
Zeitpunkt und Sitzungstag, aus ihm entsteht die Mandatsfrage
(`verfahren.models.mandatsfrage_eroeffnen`), und nach jedem Sitzungstag sind
Sammelbericht (`Bericht`) und Rechenschaft (`Rechenschaft`) fällig — die
Fristen rechnet `plattform_core.rechenschaft`.

Das Lichtbild liegt bewusst in der Datenbank (kleines Binärfeld, streng
begrenzt): Der Plattenspeicher des Dienstes ist flüchtig, die Datenbank
wird gesichert — so überlebt das Foto jeden Neustart ohne Zusatzdienst.

Seit 0.48 (S10c) trägt dieses Modul die Vertrauensfrage (§ 7 Abs 10): die
Fachdaten zum Antrag (`Vertrauensfrage`), das Gehör des Mandatars
(`Stellungnahme`), die Sperrprüfung nach lit g (`sperren_pruefen` — ein Hinweis,
nie eine Abweisung; die Feststellung trifft der Integritätsrat), die Wirkungen
einer verlorenen Vertrauensfrage in zwei Stufen (`vertrauensfrage_wirkungen`,
`vertrauensfragen_fortschreiben`) und die Vermerke des Rechtsschutzes.
Nichts davon setzt `Mandat.beendet`: Ob ein Mandat zurückgelegt wird,
entscheidet allein der Mandatsträger (§ 7 Abs 2)."""

from __future__ import annotations

from datetime import date, timedelta

from django.conf import settings
from django.db import models, transaction
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from plattform_core import Phase
from plattform_core.eligibility import monate_addieren
from plattform_core.rechenschaft import (
    RECHENSCHAFT_TAGE,
    SAMMELBERICHT_TAGE,
    STATUS_AUSSTAENDIG,
    Lage,
    berichtsmonate,
    faellig_am,
    lage,
    monatsbericht_faellig_am,
)
from verfahren.models import Antrag, AuditEintrag, Bewerbung, Ebene, Rueckgabezusage

FOTO_HOECHSTGROESSE = 800_000  # Bytes — genug für ein Porträt, zu wenig für Missbrauch

_MAGISCHE_ANFAENGE = [
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"\x89PNG\r\n\x1a\n", "image/png"),
]


def foto_typ_erkennen(daten: bytes) -> str | None:
    """Erlaubte Bildformate an den magischen Bytes erkennen (kein Pillow nötig).
    JPEG, PNG — und WebP (RIFF….WEBP). Alles andere wird abgelehnt."""
    for anfang, typ in _MAGISCHE_ANFAENGE:
        if daten.startswith(anfang):
            return typ
    if daten[:4] == b"RIFF" and daten[8:12] == b"WEBP":
        return "image/webp"
    return None


#: Nach dem Mandatsende bleiben Rechenschaft, Sammelbericht und Monatsbericht noch so viele Tage
#: möglich: Die Sieben-Tage-Frist des § 7 Abs 5 überlebt das Ende des Mandats — die Rolle endet,
#: die Pflicht aus der letzten Sitzung nicht. Keine Stellgröße, sie folgt der Satzungsfrist.
NACHFRIST_TAGE = RECHENSCHAFT_TAGE

# ── Die Vertrauensfrage (§ 7 Abs 10): satzungsfeste Fristen, keine Stellgrößen ─────────────
#: Inkrafttreten des Absatzes 10 — für davor angetretene Mandate beginnt die Schonfrist hier (lit j).
INKRAFTTRETEN_ABS_10 = date(2026, 9, 15)
SCHONFRIST_TAGE = 90  # lit g erster Fall: die ersten 90 Tage nach Antritt
WIEDERHOLUNGSSPERRE_MONATE = 6  # lit g dritter und fünfter Fall; lit f Z 3 für die Bestätigung
SPERRFESTSTELLUNG_TAGE = 3  # lit b: Frist des Integritätsrats für die Feststellung
ANFECHTUNGSFRIST_TAGE = 7  # lit h: Anrufung des Parteischiedsgerichts
RUECKGABEFRIST_TAGE = 30  # lit f Z 4: das Ersuchen um Rückgabe
ANLASS_AUSSTAND_TAGE = 30  # lit b: ein Ausstand zählt als Anlass, wenn er länger als 30 Tage besteht
#: Grund, mit dem Gremienrollen nach § 7 Abs 10 lit f ruhen und enden — der Text ist der Schlüssel,
#: über den eine Aufhebung (lit h) genau diese Rollen wiederfindet.
RUHENSGRUND = "Vertrauensfrage (§ 7 Abs 10 lit f), Anfechtungsfrist läuft"
BEENDIGUNGSGRUND = "Vertrauensfrage (§ 7 Abs 10 lit f)"


class Mandat(models.Model):
    """Ein öffentliches Mandat eines DDÖ-Mitglieds — Nationalrat, Land, Bezirk
    oder Gemeinde. Beendete Mandate bleiben dokumentiert (Rechenschaft)."""

    mitglied = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="mandate"
    )
    bezeichnung = models.CharField(
        max_length=120, help_text='Z. B. „Gemeinderat“, „Abgeordnete zum Nationalrat“.'
    )
    ebene = models.CharField(max_length=12, choices=Ebene.choices, default=Ebene.GEMEINDE)
    gebiet = models.CharField(max_length=120, blank=True)
    angetreten = models.DateField(default=timezone.localdate)
    beendet = models.DateField(null=True, blank=True)
    kandidatur = models.ForeignKey(
        Antrag,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mandate",
        help_text="Der Kandidatur-Antrag, aus dem dieses Mandat hervorging.",
    )
    vorstellung = models.TextField(max_length=2000, blank=True)
    foto = models.BinaryField(null=True, blank=True, editable=False)
    foto_typ = models.CharField(max_length=30, blank=True)
    # Vertrauensfrage (§ 7 Abs 10) — alles Stempel, nichts davon setzt `beendet`.
    vertrauen_entzogen_am = models.DateTimeField(
        null=True, blank=True,
        help_text="Veröffentlichung des Ergebnisses einer verlorenen Vertrauensfrage (§ 7 Abs 10 lit e).",
    )
    rueckgabe_ersucht_bis = models.DateField(
        null=True, blank=True,
        help_text="Ende der 30-Tage-Frist, binnen derer die Person als ersucht gilt, das Mandat "
        "zurückzulegen (§ 7 Abs 10 lit f Z 4). Ob sie dem folgt, entscheidet sie allein.",
    )
    rueckgabezusage = models.CharField(
        max_length=20, choices=Rueckgabezusage.choices, blank=True, default=Rueckgabezusage.UNBEKANNT,
        help_text="Freiwillige, nicht einklagbare Ehrenerklärung neben der Mandatsvereinbarung (§ 7 Abs 3).",
    )
    rueckgabezusage_am = models.DateField(null=True, blank=True)
    mandatsvereinbarung_lit_h_am = models.DateField(
        null=True, blank=True,
        help_text="Die Mandatsvereinbarung enthält § 7 Abs 3 lit h — bei Altverträgen erst nach der "
        "Ergänzung (§ 7 Abs 10 lit j). Nur dann endet sie nach einer verlorenen Vertrauensfrage.",
    )
    mandatsvereinbarung_endet_am = models.DateField(
        null=True, blank=True, help_text="Ende der Mandatsvereinbarung nach § 7 Abs 10 lit f Z 5.",
    )
    vertretung_beendet_am = models.DateField(
        null=True, blank=True,
        help_text="Ab hier ist die Person nicht mehr Mandatsträger der DDÖ (§ 7 Abs 10 lit f Z 8): die "
        "Rolle „Mandatar“ endet, Bereich und Register bleiben lesbar und werden fortgeführt.",
    )
    bestaetigt_am = models.DateField(
        null=True, blank=True,
        help_text="Bestätigung durch die Mitgliederversammlung nach einer verlorenen Vertrauensfrage "
        "(§ 7 Abs 10 lit f Z 3) — durch angenommenen Bestätigungsantrag oder Wahl in ein Organ.",
    )

    class Meta:
        ordering = ["ebene", "gebiet", "angetreten"]
        verbose_name = "Mandat"
        verbose_name_plural = "Mandate"

    def __str__(self) -> str:
        return f"{self.bezeichnung} ({self.gebiet or self.get_ebene_display()})"

    @property
    def aktiv(self) -> bool:
        """Die Person vertritt die DDÖ in diesem Mandat: nicht beendet und nicht nach § 7 Abs 10
        lit f Z 8 aus der Vertretung ausgeschieden. Das staatliche Mandat bleibt davon unberührt."""
        return self.beendet is None and self.vertretung_beendet_am is None

    @property
    def pflichtende(self) -> date | None:
        """Der Tag, bis zu dem Rechenschaft und Berichte geschuldet sind: Mandatsende oder Ende der
        Vertretung (§ 7 Abs 10 lit f Z 8 — „eine Begründung ist nicht mehr geschuldet“)."""
        tage = [t for t in (self.beendet, self.vertretung_beendet_am) if t is not None]
        return min(tage) if tage else None

    @property
    def kandidatursperre(self) -> bool:
        """§ 7 Abs 10 lit f Z 3: nach einer verlorenen Vertrauensfrage keine Kandidatur nach Abs 1,
        bis die Mitgliederversammlung bestätigt hat. Eine Aufhebung (lit h) leert den Stempel."""
        return self.vertrauen_entzogen_am is not None and self.bestaetigt_am is None

    def rueckgabezusage_wirksam(self) -> tuple[str, str]:
        """Die Rückgabezusage (§ 7 Abs 3) und ihre Quelle: der Vermerk am Mandat (Verwaltung, „mandat“),
        sonst die öffentliche Erklärung aus der Bewerbung zur verknüpften Kandidatur („bewerbung“);
        `("", "")` heißt „keine Angabe“. Register, Seite und JSON lesen dieselbe Quelle — der Vermerk
        nach Fristablauf darf nicht „keine Rückgabezusage“ sagen, wo die Bewerbung eine trägt."""
        if self.rueckgabezusage:
            return self.rueckgabezusage, "mandat"
        if self.kandidatur_id:
            zusage = (
                Bewerbung.objects.filter(antrag_id=self.kandidatur_id, mitglied_id=self.mitglied_id)
                .values_list("rueckgabezusage", flat=True)
                .first()
            )
            if zusage:
                return zusage, "bewerbung"
        return Rueckgabezusage.UNBEKANNT.value, ""

    @property
    def rueckgabe_vermerk(self) -> str:
        """Der Vermerk des Rechenschaftsregisters nach Ablauf der Rückgabefrist (§ 7 Abs 10 lit f Z 4)
        — ein Sachverhalt ohne Wertung, leer solange die Frist läuft oder kein Ersuchen besteht."""
        if self.rueckgabe_ersucht_bis is None or self.vertrauen_entzogen_am is None:
            return ""
        if self.beendet is not None:
            return str(_("Mandat zurückgelegt am %(datum)s") % {"datum": self.beendet.strftime("%d.%m.%Y")})
        if timezone.localdate() <= self.rueckgabe_ersucht_bis:
            return ""
        if self.rueckgabezusage_wirksam()[0] == Rueckgabezusage.ABGEGEBEN:
            return str(_("Rückgabezusage nicht eingehalten"))
        return str(_("keine Rückgabezusage abgegeben"))

    def bestaetigen(self, grund: str, jetzt=None) -> bool:
        """Die Bestätigung nach § 7 Abs 10 lit f Z 3 vermerken — durch angenommenen Bestätigungsantrag
        (`grund="antrag"`) oder Wahl in ein Organ bzw. eine Gliederungsleitung (`grund="wahl"`).
        Hebt die Kandidatursperre auf; die übrigen Wirkungen bleiben. Idempotent."""
        if self.bestaetigt_am is not None:
            return False
        jetzt = jetzt or timezone.now()
        self.bestaetigt_am = timezone.localdate(jetzt)
        self.save(update_fields=["bestaetigt_am"])
        AuditEintrag.anhaengen({"typ": "vertrauen_bestaetigt", "mandat": self.pk, "grund": grund})
        return True

    @property
    def nachfrist_bis(self) -> date | None:
        """Letzter Tag, an dem nach dem Ende der Pflichten (Mandatsende oder Ende der Vertretung,
        `pflichtende`) noch Rechenschaft und Berichte eingetragen werden können — None, solange
        die Pflichten laufen. Dieselbe Grenze, mit der `offene_pflichten` rechnet."""
        ende = self.pflichtende
        if ende is None:
            return None
        return ende + timedelta(days=NACHFRIST_TAGE)

    def in_nachfrist(self, heute: date | None = None) -> bool:
        """Pflichten beendet, aber die Nachfrist läuft noch (Endtag eingeschlossen)."""
        bis = self.nachfrist_bis
        if bis is None:
            return False
        return (heute or timezone.localdate()) <= bis

    @classmethod
    def aktive_von(cls, mitglied):
        """Die offenen Mandate eines Mitglieds — dieselbe Bedingung wie die Unvereinbarkeits-
        prüfung der Gremien (`beendet` leer). Reihenfolge: Ebene, Gebiet, Antritt (Meta)."""
        if mitglied is None or not getattr(mitglied, "pk", None):
            return cls.objects.none()
        return cls.objects.filter(mitglied=mitglied, beendet__isnull=True, vertretung_beendet_am__isnull=True)

    @classmethod
    def zugaenglich_von(cls, mitglied, heute: date | None = None):
        """Die Mandate, deren Bereich ein Mitglied öffnen darf: die offenen und die beendeten,
        deren Nachfrist für Rechenschaft und Berichte noch läuft."""
        if mitglied is None or not getattr(mitglied, "pk", None):
            return cls.objects.none()
        grenze = (heute or timezone.localdate()) - timedelta(days=NACHFRIST_TAGE)
        return cls.objects.filter(mitglied=mitglied).filter(
            models.Q(beendet__isnull=True) | models.Q(beendet__gte=grenze)
        )

    @property
    def initialen(self) -> str:
        """Kürzel für die Kachel — aus dem Klarnamen nur, wenn er öffentlich erscheinen darf
        (§ 5 Abs 3 lit a), sonst aus dem Anzeigenamen."""
        m = self.mitglied
        teile = ((m.get_full_name() if m.klarname_oeffentlich else "") or m.anzeigename).split()
        return "".join(t[0].upper() for t in teile[:2]) or "?"

    def sitzungstage(self):
        """Aufgaben, die einen Sitzungstag des Vertretungskörpers ankündigen (mit Frist)."""
        return self.aufgaben.filter(sitzungstag=True, frist__isnull=False)

    def offene_pflichten(self, heute: date | None = None) -> dict:
        """Was nach § 7 Abs 3 lit b und Abs 5 gerade fällig oder ausständig ist — Zahlen, kein Urteil.

        Rückgabe: `{"sammelberichte": [...], "rechenschaften": [...], "monatsberichte": [...],
        "karenz": n}`. Sammelberichte und Rechenschaften: je vergangener Sitzungstag ohne Eintrag
        ein Dict `{"aufgabe", "sitzungstag", "faellig", "lage"}`; Monatsberichte: je geschuldetem
        Monat ohne Bericht ein Dict `{"monat", "faellig", "lage"}`. Erledigtes erscheint nicht
        (ein Monat mit mindestens einem Bericht gilt als berichtet). `lage` ist
        `plattform_core.rechenschaft.Lage` (offen mit Resttagen oder ausständig seit n Tagen);
        `karenz` ist der einmal gelesene Registerwert der Monatsfrist.

        Ohne `heute` gilt der Sitzungstag als vorbei, sobald sein Zeitpunkt erreicht ist; mit
        übergebenem `heute` (Tests, Stichtagsrechnung) zählt der Kalendertag.

        Beendete Mandate: Sitzungstage nach dem Endtag erzeugen keine Pflicht (der Tag selbst
        zählt noch), und die Zähler frieren mit dem Ablauf der Nachfrist ein — danach kann der
        Mandatar nichts mehr nachtragen, ein weiterlaufender Zähler wäre eine Zahl ohne Handlung.

        Für viele Mandate auf einmal: `offene_pflichten_fuer` (wenige Abfragen statt je Mandat)."""
        return self.offene_pflichten_fuer([self], heute)[self.pk]

    @classmethod
    def offene_pflichten_fuer(cls, mandate, heute: date | None = None) -> dict[int, dict]:
        """`offene_pflichten` für mehrere Mandate mit einer festen Zahl von Abfragen: einmal das
        Register, einmal die Berichte, einmal die Rechenschaft. Die Sitzungstage kommen aus
        `aufgaben.all()` — vorgeladen (Prefetch) kostet das nichts, sonst eine Abfrage je Mandat."""
        from parameter.models import zahl

        mandate = list(mandate)
        ergebnis: dict[int, dict] = {}
        if not mandate:
            return ergebnis
        jetzt = timezone.now() if heute is None else None
        if heute is None:
            heute = timezone.localdate(jetzt)
        karenz = zahl("mandatar-monatsbericht-frist-tage", 7)
        pks = [m.pk for m in mandate]

        mit_bericht: dict[int, set] = {pk: set() for pk in pks}
        berichtete_monate: dict[int, set] = {pk: set() for pk in pks}
        for mandat_id, art, aufgabe_id, monat in Bericht.objects.filter(mandat_id__in=pks).values_list(
            "mandat_id", "art", "aufgabe_id", "monat"
        ):
            if art == Berichtsart.SAMMELBERICHT and aufgabe_id is not None:
                mit_bericht[mandat_id].add(aufgabe_id)
            elif art == Berichtsart.MONATSBERICHT and monat is not None:
                berichtete_monate[mandat_id].add(monat)
        mit_rechenschaft: dict[int, set] = {pk: set() for pk in pks}
        for mandat_id, aufgabe_id in Rechenschaft.objects.filter(
            mandat_id__in=pks, aufgabe__isnull=False
        ).values_list("mandat_id", "aufgabe_id"):
            mit_rechenschaft[mandat_id].add(aufgabe_id)

        for mandat in mandate:
            stichtag, zeitpunkt = heute, jetzt
            ende = mandat.pflichtende
            if ende is not None:
                grenze = ende + timedelta(days=NACHFRIST_TAGE + 1)  # der erste Tag ohne Handlungsmöglichkeit
                if stichtag > grenze:
                    stichtag, zeitpunkt = grenze, None
            sitzungstage = sorted(
                (a for a in mandat.aufgaben.all() if a.sitzungstag and a.frist is not None),
                key=lambda a: a.frist,
            )
            sammelberichte, rechenschaften = [], []
            for aufgabe in sitzungstage:
                tag = timezone.localdate(aufgabe.frist)
                if ende is not None and tag > ende:
                    continue  # nach dem Mandatsende bestand nie eine Pflicht
                vorbei = aufgabe.frist <= zeitpunkt if zeitpunkt is not None else tag <= stichtag
                if not vorbei:
                    continue
                if aufgabe.pk not in mit_bericht[mandat.pk]:
                    faellig = faellig_am(tag, SAMMELBERICHT_TAGE)
                    sammelberichte.append(
                        {"aufgabe": aufgabe, "sitzungstag": tag, "faellig": faellig, "lage": lage(faellig, None, stichtag)}
                    )
                if aufgabe.pk not in mit_rechenschaft[mandat.pk]:
                    faellig = faellig_am(tag, RECHENSCHAFT_TAGE)
                    rechenschaften.append(
                        {"aufgabe": aufgabe, "sitzungstag": tag, "faellig": faellig, "lage": lage(faellig, None, stichtag)}
                    )
            monatsberichte = []
            for monat in berichtsmonate(mandat.angetreten, ende, stichtag):
                if monat in berichtete_monate[mandat.pk]:
                    continue
                faellig = monatsbericht_faellig_am(monat, karenz)
                monatsberichte.append({"monat": monat, "faellig": faellig, "lage": lage(faellig, None, stichtag)})
            ergebnis[mandat.pk] = {
                "sammelberichte": sammelberichte,
                "rechenschaften": rechenschaften,
                "monatsberichte": monatsberichte,
                "karenz": karenz,
            }
        return ergebnis

    def anlass_ausstaende(self, heute: date | None = None) -> list[dict]:
        """Die Ausstände, die nach § 7 Abs 10 lit b Anlass einer Vertrauensfrage sein können: seit
        mehr als 30 Tagen ausständige Rechenschaft, Sammel- oder Monatsberichte — genau die, die
        der öffentliche Bereich ausweist (`offene_pflichten`). Jeder Eintrag trägt eine `kennung`
        (`rechenschaft:<aufgabe>`, `sammelbericht:<aufgabe>`, `monatsbericht:<jjjj-mm-01>`), mit
        der ein Formular ihn auswählt, den Tag der Frist (`seit`) und die Tage seither (`tage`)."""
        heute = heute or timezone.localdate()
        pflichten = self.offene_pflichten(heute)
        treffer: list[dict] = []
        for art, schluessel in (("rechenschaft", "rechenschaften"), ("sammelbericht", "sammelberichte")):
            for eintrag in pflichten[schluessel]:
                if eintrag["lage"].status == STATUS_AUSSTAENDIG and eintrag["lage"].seit_tagen > ANLASS_AUSSTAND_TAGE:
                    treffer.append(
                        {
                            "kennung": f"{art}:{eintrag['aufgabe'].pk}",
                            "art": art,
                            "seit": eintrag["faellig"],
                            "tage": eintrag["lage"].seit_tagen,
                            "bezug": eintrag["sitzungstag"].strftime("%d.%m.%Y"),
                        }
                    )
        for eintrag in pflichten["monatsberichte"]:
            if eintrag["lage"].status == STATUS_AUSSTAENDIG and eintrag["lage"].seit_tagen > ANLASS_AUSSTAND_TAGE:
                treffer.append(
                    {
                        "kennung": f"monatsbericht:{eintrag['monat'].isoformat()}",
                        "art": "monatsbericht",
                        "seit": eintrag["faellig"],
                        "tage": eintrag["lage"].seit_tagen,
                        "bezug": eintrag["monat"].strftime("%m/%Y"),
                    }
                )
        return treffer


class Aufgabenstatus(models.TextChoices):
    OFFEN = "offen", _("offen")
    LAUFEND = "laufend", _("laufend")
    ERLEDIGT = "erledigt", _("erledigt")


class Aufgabe(models.Model):
    """Eine aktuelle Aufgabe bzw. ein laufender Entscheidungsprozess des
    Mandatars — mit Frist und, wo vorhanden, der daraus entstandenen,
    von ihm betreuten Abstimmung (§ 7 Abs 9)."""

    mandat = models.ForeignKey(Mandat, on_delete=models.CASCADE, related_name="aufgaben")
    titel = models.CharField(max_length=200)
    beschreibung = models.TextField(max_length=4000, blank=True)
    frist = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Zeitpunkt der Frist (Datum und Uhrzeit, Wiener Zeit). Ein reines Datum gilt bis 23:59.",
    )
    sitzungstag = models.BooleanField(
        default=False,
        help_text="Die Frist ist ein Sitzungstag des Vertretungskörpers — danach sind Sammelbericht "
        "(§ 7 Abs 3 lit b) und Rechenschaft (§ 7 Abs 5) fällig.",
    )
    status = models.CharField(
        max_length=12, choices=Aufgabenstatus.choices, default=Aufgabenstatus.OFFEN
    )
    antrag = models.ForeignKey(
        Antrag,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="mandats_aufgaben",
        help_text="Die aus der Aufgabe entstandene, vom Mandatar betreute Abstimmung.",
    )
    erstellt_am = models.DateTimeField(default=timezone.now)
    aktualisiert_am = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-aktualisiert_am"]
        verbose_name = "Mandats-Aufgabe"
        verbose_name_plural = "Mandats-Aufgaben"

    def __str__(self) -> str:
        return f"{self.titel} [{self.get_status_display()}]"

    @property
    def ueberfaellig(self) -> bool:
        return (
            self.status != Aufgabenstatus.ERLEDIGT
            and self.frist is not None
            and self.frist < timezone.now()
        )

    @property
    def sitzungstag_datum(self) -> date | None:
        """Der Wiener Kalendertag des Sitzungstags — Basis der Sieben-Tage-Fristen."""
        if not self.sitzungstag or self.frist is None:
            return None
        return timezone.localdate(self.frist)


class Beschluss(models.TextChoices):
    """Was die Plattform zu dem Gegenstand beschlossen hatte — abgeleitet aus dem Antrag."""

    ANGENOMMEN = "angenommen", _("angenommen")
    ABGELEHNT = "abgelehnt", _("abgelehnt")
    KEINER = "keiner", _("kein Beschluss der Plattform")


class Stimmverhalten(models.TextChoices):
    DAFUER = "dafuer", _("dafür")
    DAGEGEN = "dagegen", _("dagegen")
    ENTHALTEN = "enthalten", _("enthalten")
    NICHT_TEILGENOMMEN = "nicht_teilgenommen", _("nicht teilgenommen")


class Rechenschaft(models.Model):
    """Das Rechenschaftsregister (§ 7 Abs 5): Wie der Vertretungskörper entschied, wie der
    Mandatar stimmte und warum — neben dem Beschluss der Plattform, falls es einen gab.

    Erwartet wird ein Eintrag je angekündigtem Sitzungstag binnen sieben Tagen
    (`plattform_core.rechenschaft.RECHENSCHAFT_TAGE`). Fehlt er, zeigt die Plattform den
    Ausstand — ohne Sanktion (§ 7 Abs 2 und 4). Eine Abweichung vom Plattformbeschluss wird
    nebeneinandergestellt, nicht bewertet. Einträge werden nicht gelöscht."""

    mandat = models.ForeignKey(Mandat, on_delete=models.CASCADE, related_name="rechenschaft")
    aufgabe = models.ForeignKey(
        Aufgabe,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rechenschaft",
        help_text="Der angekündigte Sitzungstag, zu dem dieser Eintrag gehört.",
    )
    antrag = models.ForeignKey(
        Antrag,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="rechenschaft",
        help_text="Der Beschluss der Plattform zu diesem Gegenstand, falls es einen gab.",
    )
    gegenstand = models.CharField(max_length=200, help_text="Worüber der Vertretungskörper abstimmte.")
    sitzung_am = models.DateField()
    beschluss_plattform = models.CharField(
        max_length=16,
        choices=Beschluss.choices,
        default=Beschluss.KEINER,
        help_text="Bei gesetztem Antrag aus dessen Phase abgeleitet und beim Speichern gesetzt.",
    )
    stimme = models.CharField(max_length=20, choices=Stimmverhalten.choices)
    begruendung = models.TextField(max_length=4000)
    eingetragen_am = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-sitzung_am", "-eingetragen_am"]
        verbose_name = "Rechenschaft"
        verbose_name_plural = "Rechenschaftsregister"

    def __str__(self) -> str:
        return f"{self.gegenstand} ({self.sitzung_am:%d.%m.%Y}, {self.get_stimme_display()})"

    def save(self, *args, **kwargs):
        if self.antrag_id is not None:
            self.beschluss_plattform = self.beschluss_aus_antrag(self.antrag)
        super().save(*args, **kwargs)

    @staticmethod
    def beschluss_aus_antrag(antrag) -> str:
        """angenommen / abgelehnt / keiner — nur ein beendetes Verfahren ist ein Beschluss."""
        if antrag is None:
            return Beschluss.KEINER
        if antrag.phase == Phase.ANGENOMMEN.value:
            return Beschluss.ANGENOMMEN
        if antrag.phase == Phase.ABGELEHNT.value:
            return Beschluss.ABGELEHNT
        return Beschluss.KEINER

    @property
    def beschluss_anzeige(self) -> str:
        """Der Beschluss der Plattform, wie er zu zeigen ist: bei verknüpftem Antrag live aus dessen
        Phase (ein Eintrag aus der Zeit vor Abstimmungsende behält sonst „kein Beschluss“),
        ohne Antrag der gespeicherte Wert."""
        if self.antrag_id is not None:
            return self.beschluss_aus_antrag(self.antrag)
        return self.beschluss_plattform

    def beschluss_nachziehen(self) -> None:
        """Den gespeicherten Beschluss auf den Stand des Antrags bringen, sobald der entschieden
        ist — idempotent, damit auch Export und Datenbank den Stand des Registers tragen."""
        beschluss = self.beschluss_anzeige
        if beschluss != self.beschluss_plattform and beschluss != Beschluss.KEINER:
            self.beschluss_plattform = beschluss
            self.save(update_fields=["beschluss_plattform"])

    @property
    def weicht_ab(self) -> bool:
        """Stimme des Mandatars und Beschluss der Plattform gehen auseinander — sichtbar, nicht bewertet."""
        beschluss = self.beschluss_anzeige
        return (beschluss == Beschluss.ANGENOMMEN and self.stimme != Stimmverhalten.DAFUER) or (
            beschluss == Beschluss.ABGELEHNT and self.stimme != Stimmverhalten.DAGEGEN
        )

    @property
    def frist(self) -> date:
        """Bis wann der Eintrag nach § 7 Abs 5 zu erwarten war."""
        return faellig_am(self.sitzung_am, RECHENSCHAFT_TAGE)

    def lage(self, heute: date | None = None) -> Lage:
        heute = heute or timezone.localdate()
        return lage(self.frist, timezone.localdate(self.eingetragen_am), heute)


class Berichtsart(models.TextChoices):
    MONATSBERICHT = "monatsbericht", _("Monatsbericht")
    SAMMELBERICHT = "sammelbericht", _("Sammelbericht")


class Bericht(models.Model):
    """Berichte nach § 7 Abs 3 lit b: der Monatsbericht für jeden vollen Kalendermonat des
    Mandats und der Sammelbericht binnen sieben Tagen nach jedem Sitzungstag.

    Kein Löschen, kein Bearbeiten — wer nachträgt, schreibt einen neuen Bericht mit Vermerk. Das
    gilt für beide Arten: Ein weiterer Bericht zum selben Sitzungstag oder zum selben Monat ist ein
    Nachtrag und wird so gekennzeichnet; die Pflicht gilt mit dem ersten Bericht als erfüllt."""

    mandat = models.ForeignKey(Mandat, on_delete=models.CASCADE, related_name="berichte")
    art = models.CharField(max_length=16, choices=Berichtsart.choices)
    monat = models.DateField(
        null=True,
        blank=True,
        help_text="Erster Tag des berichteten Monats — beim Monatsbericht Pflicht.",
    )
    aufgabe = models.ForeignKey(
        Aufgabe,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="berichte",
        help_text="Der Sitzungstag, den ein Sammelbericht abschließt — beim Sammelbericht Pflicht.",
    )
    text = models.TextField(max_length=8000)
    eingereicht_am = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-eingereicht_am"]
        verbose_name = "Bericht"
        verbose_name_plural = "Berichte"

    def __str__(self) -> str:
        return f"{self.get_art_display()} {self.monat or self.aufgabe_id or ''}".strip()

    @property
    def bezugstag(self) -> date | None:
        """Der Tag, auf den sich der Bericht bezieht: Monatserster oder Sitzungstag."""
        if self.art == Berichtsart.MONATSBERICHT:
            return self.monat
        if self.aufgabe is not None and self.aufgabe.frist:
            return timezone.localdate(self.aufgabe.frist)
        return None

    def _faellig(self, karenz: int | None) -> date | None:
        if self.art == Berichtsart.MONATSBERICHT and self.monat is not None:
            if karenz is None:
                from parameter.models import zahl

                karenz = zahl("mandatar-monatsbericht-frist-tage", 7)
            return monatsbericht_faellig_am(self.monat, karenz)
        if self.art == Berichtsart.SAMMELBERICHT and self.aufgabe is not None and self.aufgabe.frist:
            return faellig_am(timezone.localdate(self.aufgabe.frist), SAMMELBERICHT_TAGE)
        return None

    @property
    def faellig_am(self) -> date | None:
        """Der letzte Tag der Frist dieses Berichts — oder None, wenn kein Bezug gesetzt ist.
        Liest die Monatskarenz selbst aus dem Register; wer viele Berichte zeigt, reicht sie
        über `lage(karenz=…)` einmal herein."""
        return self._faellig(None)

    def lage(self, heute: date | None = None, karenz: int | None = None) -> Lage | None:
        faellig = self._faellig(karenz)
        if faellig is None:
            return None
        return lage(faellig, timezone.localdate(self.eingereicht_am), heute or timezone.localdate())


# ── Die Vertrauensfrage (§ 7 Abs 10, S10c) ──────────────────────────────────────────────────


class VertrauensfrageArt(models.TextChoices):
    VERTRAUENSFRAGE = "vertrauensfrage", _("Vertrauensfrage")
    BESTAETIGUNG = "bestaetigung", _("Bestätigung nach § 7 Abs 10 lit f Z 3")


class Entscheidung(models.TextChoices):
    """Entscheidung des Parteischiedsgerichts über ein angefochtenes Ergebnis (§ 7 Abs 10 lit h)."""

    OFFEN = "", _("keine")
    AUFGEHOBEN = "aufgehoben", _("aufgehoben")
    BESTAETIGT = "bestaetigt", _("bestätigt")


class VertrauensfrageFehler(ValueError):
    """Eine Vertrauensfrage kann so nicht eingebracht werden — die Meldung sagt, warum."""


class Vertrauensfrage(models.Model):
    """Die Fachdaten einer Vertrauensfrage (§ 7 Abs 10) neben ihrem Antrag.

    Der Antrag läuft im Verfahren (`verfahren.Antrag`, Antragsart „Vertrauensfrage“): Unterstützung,
    dann ohne Beratungsphase die Abstimmung. Hier stehen, was das Verfahren nicht kennt: das Mandat,
    die Anlässe (Einträge des Rechenschaftsregisters, ausgewiesene Ausstände), die am Einbringungstag
    festgestellten Zahlen, der Sperrhinweis nach lit g samt der Feststellung des Integritätsrats,
    die Vermerke des Rechtsschutzes (lit h) und die Zeitpunkte der Wirkungen (lit f). Dieselbe
    Tabelle trägt den Bestätigungsantrag nach lit f Z 3 (`art`). Nichts wird gelöscht."""

    antrag = models.OneToOneField(Antrag, on_delete=models.CASCADE, related_name="vertrauensfrage")
    mandat = models.ForeignKey(Mandat, on_delete=models.CASCADE, related_name="vertrauensfragen")
    art = models.CharField(
        max_length=16, choices=VertrauensfrageArt.choices, default=VertrauensfrageArt.VERTRAUENSFRAGE
    )
    anlaesse = models.ManyToManyField(
        Rechenschaft, blank=True, related_name="vertrauensfragen",
        help_text="Einträge des Rechenschaftsregisters, in denen das Stimmverhalten vom Beschluss abweicht.",
    )
    anlass_ausstaende = models.JSONField(
        default=list, blank=True,
        help_text="Ausgewiesene Ausstände als Anlass: Liste aus {kennung, art, seit, tage, bezug}.",
    )
    stimmberechtigte_partei_am_einbringungstag = models.PositiveIntegerField(
        default=0, help_text="Für Personenwahlen Stimmberechtigte der Partei am Tag der Einbringung (lit c)."
    )
    schwelle_partei = models.PositiveIntegerField(
        default=0, help_text="Fünf Prozent davon, aufgerundet — die Unterstützungsschwelle (lit c)."
    )
    schwelle_erreicht_am = models.DateTimeField(
        null=True, blank=True, help_text="Veröffentlichter Zeitpunkt, zu dem die Schwelle erreicht war (lit c)."
    )
    sperrhinweis = models.TextField(
        blank=True,
        help_text="Klartext der beim Einbringen erkannten Sperre nach lit g — ein Hinweis für den "
        "Integritätsrat, keine Abweisung. Leer heißt: keine Sperre erkannt.",
    )
    sperre_beschluss = models.ForeignKey(
        "gremien.GremienBeschluss", null=True, blank=True, on_delete=models.SET_NULL,
        related_name="vertrauensfrage_sperren",
        help_text="Der Feststellungsbeschluss des Integritätsrats (lit b) — mit ihm gilt der Antrag als nicht eröffnet.",
    )
    angefochten_am = models.DateTimeField(null=True, blank=True, help_text="Anrufung des Parteischiedsgerichts (lit h).")
    aktenkennung = models.CharField(max_length=80, blank=True)
    entscheidung = models.CharField(max_length=12, choices=Entscheidung.choices, blank=True, default=Entscheidung.OFFEN)
    entschieden_am = models.DateTimeField(null=True, blank=True)
    wirkungen_ab = models.DateTimeField(
        null=True, blank=True, help_text="Veröffentlichung des Ergebnisses „verloren“ — Beginn der Wirkungen (lit f)."
    )
    wirkungen_endgueltig_am = models.DateTimeField(
        null=True, blank=True,
        help_text="Ablauf der Anfechtungsfrist oder Entscheidung des Parteischiedsgerichts — das Ruhen wird zum Ende.",
    )
    verstaendigt_am = models.DateTimeField(
        null=True, blank=True, help_text="Erster Versandversuch der Verständigung des Mandatars (lit b)."
    )

    class Meta:
        ordering = ["-antrag__eingebracht_am"]
        verbose_name = "Vertrauensfrage"
        verbose_name_plural = "Vertrauensfragen"

    def __str__(self) -> str:
        return f"{self.get_art_display()} zu Mandat {self.mandat_id} (Antrag {self.antrag_id})"

    @property
    def laeuft(self) -> bool:
        return self.antrag.phase in (Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value)

    @property
    def sperrfrist_ende(self):
        """Bis wann der Integritätsrat eine Sperre feststellen kann (lit b: drei Tage nach Einbringung)."""
        return self.antrag.eingebracht_am + timedelta(days=SPERRFESTSTELLUNG_TAGE)

    @property
    def nicht_eroeffnet(self) -> bool:
        return self.sperre_beschluss_id is not None

    @property
    def ergebnis_am(self):
        """Veröffentlichung des Ergebnisses — der Phasenbeginn der Endphase; None, solange offen."""
        if self.antrag.phase in (Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value):
            return self.antrag.phase_beginn
        return None

    @property
    def verloren(self) -> bool:
        return self.art == VertrauensfrageArt.VERTRAUENSFRAGE and self.antrag.phase == Phase.ANGENOMMEN.value

    @property
    def gewonnen(self) -> bool:
        return self.art == VertrauensfrageArt.VERTRAUENSFRAGE and self.antrag.phase == Phase.ABGELEHNT.value

    @property
    def ergebnis_wort(self) -> str:
        """„verloren“ / „gewonnen“ statt „angenommen“ / „abgelehnt“ (lit e) — für Bestätigungen
        „bestätigt“ / „nicht bestätigt“; leer, solange kein Ergebnis vorliegt."""
        phase = self.antrag.phase
        if self.art == VertrauensfrageArt.BESTAETIGUNG:
            if phase == Phase.ANGENOMMEN.value:
                return str(_("bestätigt"))
            if phase == Phase.ABGELEHNT.value:
                return str(_("nicht bestätigt"))
            return ""
        if phase == Phase.ANGENOMMEN.value:
            return str(_("Vertrauensfrage verloren"))
        if phase == Phase.ABGELEHNT.value:
            return str(_("Vertrauensfrage gewonnen"))
        return ""

    @property
    def anfechtungsfrist_ende(self):
        """Ende der sieben Tage ab Veröffentlichung des Ergebnisses (lit h) — None ohne Ergebnis."""
        ab = self.ergebnis_am
        return None if ab is None else ab + timedelta(days=ANFECHTUNGSFRIST_TAGE)

    @property
    def rueckgabefrist_ende(self):
        return None if self.wirkungen_ab is None else self.wirkungen_ab + timedelta(days=RUECKGABEFRIST_TAGE)

    @property
    def rechtsschutz_stand(self) -> str:
        if self.entscheidung == Entscheidung.AUFGEHOBEN:
            return str(_("vom Parteischiedsgericht aufgehoben"))
        if self.entscheidung == Entscheidung.BESTAETIGT:
            return str(_("vom Parteischiedsgericht bestätigt"))
        if self.angefochten_am is not None:
            return str(_("beim Parteischiedsgericht anhängig"))
        return ""

    def endgueltig_ab(self):
        """Ab wann das Ruhen zum Ende wird (lit f letzter Unterabsatz): sieben Tage nach der
        Veröffentlichung ohne Anfechtung, sonst mit der bestätigenden Entscheidung; None, solange
        eine Anfechtung offen ist oder das Ergebnis aufgehoben wurde."""
        if self.wirkungen_ab is None or self.entscheidung == Entscheidung.AUFGEHOBEN:
            return None
        if self.angefochten_am is None:
            return self.wirkungen_ab + timedelta(days=ANFECHTUNGSFRIST_TAGE)
        if self.entscheidung == Entscheidung.BESTAETIGT and self.entschieden_am is not None:
            return self.entschieden_am
        return None

    @classmethod
    def offene_mit_sperrhinweis(cls):
        """Für den Bereich des Integritätsrats: laufende Vertrauensfragen mit erkannter Sperre und
        noch ohne Feststellungsbeschluss — er entscheidet binnen drei Tagen (lit b)."""
        return (
            cls.objects.exclude(sperrhinweis="")
            .filter(sperre_beschluss__isnull=True, antrag__phase__in=[Phase.UNTERSTUETZUNG.value, Phase.ABSTIMMUNG.value])
            .select_related("antrag", "mandat")
        )


class Stellungnahme(models.Model):
    """Das Gehör des Mandatsträgers (§ 7 Abs 10 lit d): im Wortlaut neben dem Antrag, ergänzbar bis zum
    Ende der Abstimmung, nie nachträglich änderbar — jeder Eintrag bleibt, wie er war."""

    vertrauensfrage = models.ForeignKey(Vertrauensfrage, on_delete=models.CASCADE, related_name="stellungnahmen")
    text = models.TextField(max_length=4000)
    erstellt_am = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["erstellt_am", "pk"]
        verbose_name = "Stellungnahme"
        verbose_name_plural = "Stellungnahmen"

    def __str__(self) -> str:
        return f"Stellungnahme zu Vertrauensfrage {self.vertrauensfrage_id} ({self.erstellt_am:%d.%m.%Y})"


def stellungnahme_abgeben(vf: Vertrauensfrage, mitglied, text: str, jetzt=None) -> Stellungnahme:
    """Nur der betroffene Mandatsträger, nur solange das Verfahren läuft (lit d); append-only."""
    jetzt = jetzt or timezone.now()
    if mitglied is None or mitglied.pk != vf.mandat.mitglied_id:
        raise VertrauensfrageFehler(_("Stellung nehmen kann nur der betroffene Mandatsträger (§ 7 Abs 10 lit d)."))
    vf.antrag.fortschreiben(jetzt)  # die Phase ist lazy — „bis zum Ende der Abstimmung“ heißt: bis zum Fristende
    if not vf.laeuft:
        raise VertrauensfrageFehler(_("Die Vertrauensfrage ist beendet — eine Stellungnahme ist nicht mehr möglich."))
    text = (text or "").strip()
    if not text:
        raise VertrauensfrageFehler(_("Die Stellungnahme braucht einen Text."))
    eintrag = Stellungnahme.objects.create(vertrauensfrage=vf, text=text[:4000], erstellt_am=jetzt)
    AuditEintrag.anhaengen(
        {"typ": "vertrauensfrage_stellungnahme", "antrag": vf.antrag_id, "mandat": vf.mandat_id, "stellungnahme": eintrag.pk}
    )
    return eintrag


def _letzte_gegen(mitglied_id: int, phasen: list[str], ausser: int | None = None):
    """Die jüngste Vertrauensfrage (nicht Bestätigung) gegen dieselbe Person in einer der Phasen."""
    qs = Vertrauensfrage.objects.filter(
        mandat__mitglied_id=mitglied_id, art=VertrauensfrageArt.VERTRAUENSFRAGE, antrag__phase__in=phasen
    ).select_related("antrag")
    if ausser is not None:
        qs = qs.exclude(pk=ausser)
    return qs.order_by("-antrag__phase_beginn").first()


def sperren_pruefen(mandat: Mandat, jetzt=None, anlaesse=(), ausstaende=()) -> str:
    """Die fünf Sperren des § 7 Abs 10 lit g am Tag der Einbringung — als Klartext, nie als Abweisung.

    Das Ergebnis wird am Antrag als `sperrhinweis` gezeigt und dem Integritätsrat vorgelegt; erst sein
    veröffentlichter Beschluss setzt den Antrag auf „nicht eröffnet“ (lit b, § 2 Abs 6). Leer heißt:
    keine Sperre erkannt. Der Text ist gespeicherter Sachverhalt in der Arbeitssprache — wie eine
    Beschlussbegründung, nicht wie eine Oberflächenmeldung; deshalb ohne Übersetzungskatalog.
    `anlaesse` (Rechenschaft) und `ausstaende` (Dicts mit `seit`) braucht der fünfte Fall: Nach
    einem verfallenen Antrag ist ein neuer nur mit einem Anlass zulässig, der nach dessen
    Einbringung entstanden ist."""
    from mitglieder.models import Mitgliedsstatus

    jetzt = jetzt or timezone.now()
    heute = timezone.localdate(jetzt)
    gruende: list[str] = []
    # Vierter Fall zuerst: Ohne Vertretungsbeziehung gibt es nichts, worüber die Versammlung entschiede.
    mitglied = mandat.mitglied
    if mandat.beendet is not None:
        gruende.append(f"Das Mandat hat am {mandat.beendet:%d.%m.%Y} geendet (lit g vierter Fall).")
    elif mandat.vertretung_beendet_am is not None:
        gruende.append(
            f"Die Person ist seit {mandat.vertretung_beendet_am:%d.%m.%Y} nicht mehr Mandatsträger der DDÖ "
            "(lit f Z 8, lit g vierter Fall)."
        )
    if not mitglied.is_active or mitglied.status in (Mitgliedsstatus.AUSGETRETEN, Mitgliedsstatus.AUSGESCHLOSSEN):
        gruende.append("Die Mitgliedschaft der Person hat geendet (lit g vierter Fall).")
    # Erster Fall: 90 Tage Schonfrist, für Altmandate ab dem Inkrafttreten (lit j).
    beginn = max(mandat.angetreten, INKRAFTTRETEN_ABS_10)
    schonfrist_ende = beginn + timedelta(days=SCHONFRIST_TAGE)
    if heute < schonfrist_ende:
        uebergang = ", gerechnet ab Inkrafttreten nach lit j" if beginn != mandat.angetreten else ""
        gruende.append(
            f"Schonfrist: In den ersten {SCHONFRIST_TAGE} Tagen nach Antritt des Mandats (bis "
            f"{schonfrist_ende:%d.%m.%Y}) kann keine Vertrauensfrage eingebracht werden (lit g erster Fall{uebergang})."
        )
    # Zweiter Fall: anhängige Vertrauensfrage gegen dieselbe Person.
    laufend = _letzte_gegen(mitglied.pk, [Phase.UNTERSTUETZUNG.value, Phase.BERATUNG.value, Phase.ABSTIMMUNG.value])
    if laufend is not None:
        gruende.append(
            f"Gegen dieselbe Person ist bereits eine Vertrauensfrage anhängig (Antrag #{laufend.antrag_id}; "
            "lit g zweiter Fall)."
        )
    # Dritter Fall: sechs Monate nach dem letzten Ergebnis — gewonnen oder verloren; nach einer
    # Aufhebung durch das Parteischiedsgericht läuft die Sperre nicht (lit h).
    letzte = _letzte_gegen(mitglied.pk, [Phase.ANGENOMMEN.value, Phase.ABGELEHNT.value])
    if letzte is not None and letzte.entscheidung != Entscheidung.AUFGEHOBEN:
        ergebnis_tag = timezone.localdate(letzte.antrag.phase_beginn)
        frei_ab = monate_addieren(ergebnis_tag, WIEDERHOLUNGSSPERRE_MONATE)
        if heute < frei_ab:
            gruende.append(
                f"Das Ergebnis der letzten Vertrauensfrage über dieselbe Person wurde am {ergebnis_tag:%d.%m.%Y} "
                f"veröffentlicht; eine neue ist erst ab {frei_ab:%d.%m.%Y} zulässig (lit g dritter Fall)."
            )
    # Fünfter Fall: binnen sechs Monaten nach einem an der Schwelle verfallenen Antrag nur mit einem
    # Anlass, der nach dessen Einbringung entstanden ist.
    verfallen = _letzte_gegen(mitglied.pk, [Phase.VERFALLEN.value])
    if verfallen is not None:
        verfall_tag = timezone.localdate(verfallen.antrag.phase_beginn)
        frei_ab = monate_addieren(verfall_tag, WIEDERHOLUNGSSPERRE_MONATE)
        eingebracht = verfallen.antrag.eingebracht_am
        neu = any(r.eingetragen_am > eingebracht for r in anlaesse) or any(
            _als_datum(a.get("seit")) is not None and _als_datum(a.get("seit")) > timezone.localdate(eingebracht)
            for a in ausstaende
        )
        if heute < frei_ab and not neu:
            gruende.append(
                f"Ein Antrag gegen dieselbe Person ist am {verfall_tag:%d.%m.%Y} an der Unterstützungsschwelle "
                f"verfallen; bis {frei_ab:%d.%m.%Y} braucht ein neuer Antrag einen Anlass, der nach dessen "
                "Einbringung entstanden ist (lit g fünfter Fall)."
            )
    return "\n".join(gruende)


def _als_datum(wert) -> date | None:
    if isinstance(wert, date):
        return wert
    if isinstance(wert, str):
        try:
            return date.fromisoformat(wert[:10])
        except ValueError:
            return None
    return None


def _koordinationsrat_hinweis(vf: Vertrauensfrage, jetzt) -> None:
    """Der Posteingang des Koordinationsrats: Mitteilung an den Klub (lit f Z 7), Ende der
    Gegenleistungen und der Abführung mit Ablauf der Rückgabefrist (Z 5), gegebenenfalls Abberufung
    nach § 6 Abs 2 lit c oder Abs 8 — Handlungen von Menschen, die die Plattform nur anstößt."""
    from gremien.models import Hinweis, HinweisQuelle

    mandat = vf.mandat
    frist = timezone.localdate(jetzt) + timedelta(days=RUECKGABEFRIST_TAGE)
    Hinweis.objects.create(
        quelle=HinweisQuelle.VERTRAUENSFRAGE,
        titel=f"Vertrauensfrage verloren: {mandat.bezeichnung}, {mandat.gebiet or mandat.get_ebene_display()}"[:200],
        text=(
            f"Die Mitgliederversammlung hat dem Mandat „{mandat.bezeichnung}“ ({mandat.gebiet or mandat.get_ebene_display()}) "
            f"am {timezone.localtime(jetzt):%d.%m.%Y} das Vertrauen versagt (Antrag #{vf.antrag_id}).\n"
            f"Zu veranlassen (§ 7 Abs 10 lit f): Mitteilung an den Parlamentsklub oder die Fraktion (Z 7); "
            f"Gegenleistungen der Partei und Abführungspflicht enden mit Ablauf der Rückgabefrist am {frist:%d.%m.%Y} "
            f"zugleich (Z 5), Kennzeichen, Konten und Kanäle sind zurückzugeben; hat die Person Funktionen in Organen "
            f"der Partei, ruhen sie bis zum Ablauf der Anfechtungsfrist — über eine Abberufung nach § 6 Abs 2 lit c "
            f"oder Abs 8 entscheidet der Rat. Anfechtung binnen sieben Tagen beim Parteischiedsgericht (lit h)."
        )[:4000],
        antrag=vf.antrag,
        angelegt_am=jetzt,
    )


@transaction.atomic
def vertrauensfrage_wirkungen(vf: Vertrauensfrage, jetzt=None) -> bool:
    """Stufe 1 der Wirkungen einer verlorenen Vertrauensfrage — mit der Veröffentlichung des Ergebnisses
    (§ 7 Abs 10 lit f): Vertrauen entzogen, Ersuchen um Rückgabe binnen 30 Tagen, Kandidatursperre
    (über `Mandat.kandidatursperre`), Gremienrollen ruhen, Hinweis an den Koordinationsrat. Nichts
    davon setzt `Mandat.beendet`. Idempotent; Rückgabe: ob etwas geschah."""
    from gremien.models import Rolle

    if vf.art != VertrauensfrageArt.VERTRAUENSFRAGE or vf.wirkungen_ab is not None:
        return False
    jetzt = jetzt or timezone.now()
    mandat = vf.mandat
    vf.wirkungen_ab = jetzt
    vf.save(update_fields=["wirkungen_ab"])
    mandat.vertrauen_entzogen_am = jetzt
    mandat.rueckgabe_ersucht_bis = timezone.localdate(jetzt) + timedelta(days=RUECKGABEFRIST_TAGE)
    mandat.bestaetigt_am = None  # eine frühere Bestätigung trägt nicht über eine neue Entscheidung
    mandat.save(update_fields=["vertrauen_entzogen_am", "rueckgabe_ersucht_bis", "bestaetigt_am"])
    ruhend = []
    for rolle in Rolle.aktive_von(mandat.mitglied):
        rolle.ruht_seit = jetzt
        rolle.ruht_grund = RUHENSGRUND
        rolle.save(update_fields=["ruht_seit", "ruht_grund"])
        ruhend.append(rolle.pk)
    _koordinationsrat_hinweis(vf, jetzt)
    AuditEintrag.anhaengen(
        {
            "typ": "vertrauensfrage_verloren",
            "antrag": vf.antrag_id,
            "mandat": mandat.pk,
            "rueckgabe_ersucht_bis": mandat.rueckgabe_ersucht_bis.isoformat(),
            "rollen_ruhen": ruhend,
        }
    )
    return True


def vertrauensfrage_ergebnis(vf: Vertrauensfrage, jetzt=None) -> None:
    """Was mit dem Ergebnis eines Vertrauensfrage- oder Bestätigungsantrags geschieht — aus
    `Antrag.fortschreiben` beim Übergang in eine Endphase gerufen (§ 7 Abs 10 lit e und f Z 3)."""
    jetzt = jetzt or timezone.now()
    phase = vf.antrag.phase
    if vf.art == VertrauensfrageArt.BESTAETIGUNG:
        if phase == Phase.ANGENOMMEN.value:
            vf.mandat.bestaetigen("antrag", jetzt)
            AuditEintrag.anhaengen({"typ": "bestaetigung_angenommen", "antrag": vf.antrag_id, "mandat": vf.mandat_id})
        elif phase == Phase.ABGELEHNT.value:
            AuditEintrag.anhaengen({"typ": "bestaetigung_abgelehnt", "antrag": vf.antrag_id, "mandat": vf.mandat_id})
        return
    if phase == Phase.ANGENOMMEN.value:
        vertrauensfrage_wirkungen(vf, jetzt)
    elif phase == Phase.ABGELEHNT.value:
        AuditEintrag.anhaengen({"typ": "vertrauensfrage_gewonnen", "antrag": vf.antrag_id, "mandat": vf.mandat_id})


def vertrauensfragen_fortschreiben(jetzt=None) -> int:
    """Stufe 2 der Wirkungen — lazy, aus Mandatar- und Antragsseiten und `verfahren_fortschreiben`
    (§ 7 Abs 10 lit f letzter Unterabsatz, Z 5 und Z 8):

    - Sieben Tage nach der Veröffentlichung ohne Anfechtung, sonst mit der bestätigenden Entscheidung
      des Parteischiedsgerichts, wird das Ruhen der Gremienrollen zum Ende (`wirkungen_endgueltig_am`).
    - Mit Ablauf der Rückgabefrist (30 Tage), frühestens aber dann, endet die Vertretung
      (`vertretung_beendet_am`: Rolle „Mandatar“ endet, Bereich und Register bleiben) und — nur bei
      Mandatsvereinbarungen mit lit h — die Mandatsvereinbarung (`mandatsvereinbarung_endet_am`).
    Solange eine Anfechtung offen ist, wartet alles; nach einer Aufhebung geschieht nichts mehr.
    Nichts davon setzt `Mandat.beendet`. Rückgabe: Zahl der geänderten Vertrauensfragen."""
    from gremien.models import Rolle

    jetzt = jetzt or timezone.now()
    geaendert = 0
    offene = Vertrauensfrage.objects.filter(
        art=VertrauensfrageArt.VERTRAUENSFRAGE, wirkungen_ab__isnull=False
    ).exclude(entscheidung=Entscheidung.AUFGEHOBEN).select_related("mandat", "mandat__mitglied")
    for vf in offene:
        mandat = vf.mandat
        if mandat.vertretung_beendet_am is not None:
            continue  # alles vollzogen
        endgueltig_ab = vf.endgueltig_ab()
        if endgueltig_ab is None or jetzt < endgueltig_ab:
            continue
        beruehrt = False
        if vf.wirkungen_endgueltig_am is None:
            vf.wirkungen_endgueltig_am = endgueltig_ab
            vf.save(update_fields=["wirkungen_endgueltig_am"])
            beendet = []
            for rolle in Rolle.objects.filter(mitglied=mandat.mitglied, ruht_grund=RUHENSGRUND, beendet_grund=""):
                rolle.beendet_grund = BEENDIGUNGSGRUND
                rolle.save(update_fields=["beendet_grund"])
                beendet.append(rolle.pk)
            AuditEintrag.anhaengen(
                {
                    "typ": "vertrauensfrage_endgueltig",
                    "antrag": vf.antrag_id,
                    "mandat": mandat.pk,
                    "endgueltig_ab": endgueltig_ab.isoformat(),
                    "rollen_beendet": beendet,
                }
            )
            beruehrt = True
        rueckgabe_ende = max(vf.rueckgabefrist_ende, endgueltig_ab)
        if jetzt >= rueckgabe_ende:
            tag = timezone.localdate(rueckgabe_ende)
            mandat.vertretung_beendet_am = tag
            felder = ["vertretung_beendet_am"]
            if mandat.mandatsvereinbarung_lit_h_am is not None and mandat.mandatsvereinbarung_endet_am is None:
                mandat.mandatsvereinbarung_endet_am = tag
                felder.append("mandatsvereinbarung_endet_am")
            mandat.save(update_fields=felder)
            AuditEintrag.anhaengen(
                {
                    "typ": "vertretung_beendet",
                    "antrag": vf.antrag_id,
                    "mandat": mandat.pk,
                    "ab": tag.isoformat(),
                    "mandatsvereinbarung_endet": "mandatsvereinbarung_endet_am" in felder,
                    "rueckgabezusage": mandat.rueckgabezusage,
                }
            )
            beruehrt = True
        geaendert += int(beruehrt)
    return geaendert


def vertrauensfrage_anfechtung_vermerken(vf: Vertrauensfrage, aktenkennung: str = "", jetzt=None) -> None:
    """Verwaltungsvermerk: Das Ergebnis ist beim Parteischiedsgericht angefochten (lit h). Solange der
    Vermerk steht, wird das Ruhen nicht zum Ende und die Mandatsvereinbarung endet nicht."""
    jetzt = jetzt or timezone.now()
    vf.angefochten_am = jetzt
    vf.aktenkennung = (aktenkennung or "").strip()[:80]
    vf.save(update_fields=["angefochten_am", "aktenkennung"])
    AuditEintrag.anhaengen({"typ": "vertrauensfrage_angefochten", "antrag": vf.antrag_id, "mandat": vf.mandat_id})


@transaction.atomic
def vertrauensfrage_entscheidung_vermerken(vf: Vertrauensfrage, entscheidung: str, jetzt=None) -> None:
    """Verwaltungsvermerk „Entscheidung vollziehen“ (lit h): `bestaetigt` lässt Stufe 2 ab der Entscheidung
    laufen; `aufgehoben` nimmt die Wirkungen zurück — Rollen wieder aktiv, Vertrauen nicht mehr entzogen,
    eine beendete Vertretung und Mandatsvereinbarung gelten als nicht beendet; die Sperre nach lit g
    dritter Fall läuft nicht. Nie automatisch, immer auditiert."""
    from gremien.models import Rolle

    jetzt = jetzt or timezone.now()
    entscheidung = Entscheidung(entscheidung)
    if entscheidung == Entscheidung.OFFEN:
        raise VertrauensfrageFehler(_("Eine Entscheidung lautet auf „aufgehoben“ oder „bestätigt“."))
    vf.entscheidung = entscheidung
    vf.entschieden_am = jetzt
    vf.save(update_fields=["entscheidung", "entschieden_am"])
    mandat = vf.mandat
    wiederhergestellt: list[int] = []
    if entscheidung == Entscheidung.AUFGEHOBEN and vf.art == VertrauensfrageArt.VERTRAUENSFRAGE:
        heute = timezone.localdate(jetzt)
        rollen = Rolle.objects.filter(mitglied=mandat.mitglied, ruht_grund=RUHENSGRUND, endet_am__gte=heute).filter(
            models.Q(beendet_grund="") | models.Q(beendet_grund=BEENDIGUNGSGRUND)
        )
        for rolle in rollen:
            rolle.ruht_seit = None
            rolle.ruht_grund = ""
            rolle.beendet_grund = ""
            rolle.save(update_fields=["ruht_seit", "ruht_grund", "beendet_grund"])
            wiederhergestellt.append(rolle.pk)
        mandat.vertrauen_entzogen_am = None
        mandat.rueckgabe_ersucht_bis = None
        mandat.vertretung_beendet_am = None
        mandat.mandatsvereinbarung_endet_am = None
        mandat.save(
            update_fields=["vertrauen_entzogen_am", "rueckgabe_ersucht_bis", "vertretung_beendet_am", "mandatsvereinbarung_endet_am"]
        )
    AuditEintrag.anhaengen(
        {
            "typ": "vertrauensfrage_aufgehoben" if entscheidung == Entscheidung.AUFGEHOBEN else "vertrauensfrage_bestaetigt",
            "antrag": vf.antrag_id,
            "mandat": mandat.pk,
            "rollen_wiederhergestellt": wiederhergestellt,
        }
    )


def rueckgabezusage_vermerken(mandat: Mandat, wert: str, jetzt=None) -> None:
    """Verwaltungsvermerk: Rückgabezusage nachgetragen oder widerrufen (§ 7 Abs 3) — mit Datum, auditiert."""
    jetzt = jetzt or timezone.now()
    mandat.rueckgabezusage = Rueckgabezusage(wert)
    mandat.rueckgabezusage_am = timezone.localdate(jetzt)
    mandat.save(update_fields=["rueckgabezusage", "rueckgabezusage_am"])
    AuditEintrag.anhaengen({"typ": "rueckgabezusage", "mandat": mandat.pk, "wert": mandat.rueckgabezusage})


def bestaetigung_zulaessig_ab(mandat: Mandat):
    """Frühester Tag für einen Bestätigungsantrag (§ 7 Abs 10 lit f Z 3): sechs Monate nach der
    Veröffentlichung des verlorenen Ergebnisses oder nach der letzten Ablehnung einer Bestätigung;
    None, wenn kein Vertrauen entzogen ist."""
    if mandat.vertrauen_entzogen_am is None:
        return None
    letzter = timezone.localdate(mandat.vertrauen_entzogen_am)
    abgelehnt = (
        Vertrauensfrage.objects.filter(
            mandat=mandat, art=VertrauensfrageArt.BESTAETIGUNG, antrag__phase=Phase.ABGELEHNT.value
        )
        .order_by("-antrag__phase_beginn")
        .first()
    )
    if abgelehnt is not None:
        letzter = max(letzter, timezone.localdate(abgelehnt.antrag.phase_beginn))
    return monate_addieren(letzter, WIEDERHOLUNGSSPERRE_MONATE)
