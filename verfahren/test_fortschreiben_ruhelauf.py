'''Der Fristen-Wächter im Ruhelauf (Gesamtprüfung GP-163).

Der Wächter schrieb bei jedem Takt jeden laufenden Antrag einzeln fort — rund 8,5 Abfragen je Antrag,
auch wenn nichts fällig war. Jetzt wählt er mit wenigen Sammelabfragen aus, an welchen Anträgen etwas
fällig sein kann, und schreibt nur diese einzeln fort. Was ein Lauf bewirkt, bleibt dasselbe: Der
zweite Test fährt denselben Bestand einmal nach altem Muster (jeden einzeln) und einmal nach neuem und
vergleicht Endzustand und Audit-Ereignisse.'''

from datetime import timedelta

import pytest
from django.db import connection, transaction
from django.utils import timezone

from gremien.models import Anlass, Aussetzung, BeschlussStatus, Entwurf, GremienBeschluss
from gremien.test_integritaet import antrag_in_abstimmung, beschluss_fassen, rat
from gremien.test_werkstatt import einreichen, frist_verstreichen, werkstatt_lage
from verfahren.management.commands.verfahren_fortschreiben import alles_fortschreiben
from verfahren.models import Antrag, AuditEintrag, Kommentar, antrag_einbringen, stimme_abgeben
from verfahren.test_views_aktionen import (  # noqa: F401
    ANTRAG,
    in_abstimmung_bringen,
    mitglied_anlegen,
    ordnung,
)

pytestmark = pytest.mark.django_db
T = timedelta


class Zaehler:
    '''Zählt jede Anweisung an die Datenbank — auch Sicherungspunkte; das Abfrageprotokoll von Django
    schneidet bei 9.000 Einträgen ab.'''

    def __init__(self):
        self.n = 0
        self.aussetzungen = 0

    def __call__(self, execute, sql, params, many, context):
        self.n += 1
        if 'gremien_aussetzung' in sql:
            self.aussetzungen += 1
        return execute(sql, params, many, context)


def _grossbestand(ordnung, anzahl, jetzt):  # noqa: F811
    '''`anzahl` laufende Anträge, an denen nichts fällig ist: je ein Drittel in Unterstützung, Beratung
    und Abstimmung, alle erst gestern in ihre Phase gekommen.'''
    vorlage = antrag_einbringen(mitglied_anlegen('lastprobe'), **ANTRAG, ordnung=ordnung)
    phasen = ('unterstuetzung', 'beratung', 'abstimmung')
    Antrag.objects.bulk_create(
        [
            Antrag(
                titel=f'Lastprobe {i}',
                eingebracht_von=vorlage.eingebracht_von,
                policy_snapshot=vorlage.policy_snapshot,
                phase=phasen[i % 3],
                phase_beginn=jetzt - T(days=1),
                stimmberechtigte_anzahl=10 if phasen[i % 3] == 'abstimmung' else None,
                stimmberechtigung_stichtag=timezone.localdate(jetzt - T(days=1)) if phasen[i % 3] == 'abstimmung' else None,
            )
            for i in range(anzahl - 1)
        ]
    )
    assert Antrag.objects.filter(phase__in=phasen).count() == anzahl


def test_ein_ruhelauf_ueber_2000_antraege_braucht_hoechstens_2100_abfragen(ordnung):  # noqa: F811
    jetzt = timezone.now()
    _grossbestand(ordnung, 2000, jetzt)
    audit_vorher = AuditEintrag.objects.count()
    zaehler = Zaehler()
    with connection.execute_wrapper(zaehler):
        stand = alles_fortschreiben(jetzt)
    assert stand == {
        'phasenwechsel': 0, 'beschluesse': 0, 'aussetzungen': 0, 'parametertests': 0, 'vertrauensfragen': 0, 'fehler': 0,
    }
    assert AuditEintrag.objects.count() == audit_vorher
    assert zaehler.n <= 2100, f'{zaehler.n} Abfragen im Ruhelauf'
    # Nicht mehr je Antrag: Der Lauf braucht eine feste, kleine Zahl von Abfragen.
    assert zaehler.n <= 40, f'{zaehler.n} Abfragen im Ruhelauf'
    # Die Aussetzungen: eine Sammelabfrage der betroffenen Anträge und ein Schließlauf, nicht je Antrag.
    assert zaehler.aussetzungen <= 2, f'{zaehler.aussetzungen} Abfragen auf Aussetzungen'


def test_im_grossbestand_wird_das_faellige_gefunden(ordnung):  # noqa: F811
    '''Zwischen 300 ruhenden Anträgen liegen drei fällige — sie werden fortgeschrieben, die übrigen
    bleiben, und der Lauf kostet weiter nicht je Antrag.'''
    jetzt = timezone.now()
    _grossbestand(ordnung, 300, jetzt)
    faellig = list(Antrag.objects.filter(titel__in=['Lastprobe 30', 'Lastprobe 31', 'Lastprobe 32']).order_by('pk'))
    assert [a.phase for a in faellig] == ['unterstuetzung', 'beratung', 'abstimmung']
    Antrag.objects.filter(pk__in=[a.pk for a in faellig]).update(phase_beginn=jetzt - T(days=40))
    zaehler = Zaehler()
    with connection.execute_wrapper(zaehler):
        stand = alles_fortschreiben(jetzt)
    for a in faellig:
        a.refresh_from_db()
    # Unterstützung um: verfallen. Beratung und danach auch die Abstimmung um: Ergebnis. Abstimmung um: Ergebnis.
    assert [a.phase for a in faellig] == ['verfallen', 'abgelehnt', 'abgelehnt']
    assert stand['phasenwechsel'] == 4 and stand['fehler'] == 0
    assert Antrag.objects.filter(phase__in=('unterstuetzung', 'beratung', 'abstimmung')).count() == 297
    assert zaehler.n <= 300, f'{zaehler.n} Abfragen bei drei fälligen Anträgen'


# --- Derselbe Endzustand wie beim Fortschreiben jedes einzelnen Antrags ------------------------------


def _gemischter_bestand(client, ordnung):  # noqa: F811
    '''Ein Bestand mit allem, was der Wächter antreffen kann — Ruhendes und Fälliges in jeder Phase,
    eine Entwurfsschleife mit verstrichener Frist, eine laufende und eine abgelaufene Aussetzung, ein
    fälliger Beschluss ohne laufenden Antrag, ein liegengebliebener Antrag mit zwei fälligen Schritten.'''
    leute = [mitglied_anlegen(f'g{i}') for i in range(6)]
    jetzt = timezone.now()

    def neu(titel):
        return antrag_einbringen(leute[0], **{**ANTRAG, 'titel': titel}, ordnung=ordnung)

    def zurueck(antrag, tage):
        Antrag.objects.filter(pk=antrag.pk).update(phase_beginn=jetzt - T(days=tage))

    neu('U ruhend')
    zurueck(neu('U Frist um'), 15)  # unterstuetzung_frist_tage = 14
    schwelle = neu('U Schwelle erreicht, nie gezählt')
    for m in leute[1:3]:
        schwelle.unterstuetzungen.create(mitglied=m)
    knapp = neu('U eine Unterstützung fehlt')
    knapp.unterstuetzungen.create(mitglied=leute[1])
    zurueckgezogen = neu('U zwei Unterstützungen, eine zurückgezogen')
    zurueckgezogen.unterstuetzungen.create(mitglied=leute[1])
    zurueckgezogen.unterstuetzungen.create(mitglied=leute[2], zurueckgezogen_am=jetzt)

    def beratung(titel):
        antrag = neu(titel)
        for m in leute[1:3]:
            antrag.unterstuetzungen.create(mitglied=m)
        antrag.fortschreiben()
        assert antrag.phase == 'beratung'
        return antrag

    beratung('B ruhend')
    zurueck(beratung('B Frist um'), 22)  # beratung_tage = 21
    zurueck(beratung('B liegengeblieben, auch die Abstimmung ist um'), 40)

    def abstimmung(titel, stimmen=()):
        antrag = in_abstimmung_bringen(neu(titel), leute[1:3])
        for m, wert in zip(leute, stimmen, strict=False):
            stimme_abgeben(antrag, m, wert)
        return antrag

    abstimmung('A ruhend', ('ja', 'nein'))
    zurueck(abstimmung('A Frist um, angenommen', ('ja', 'ja', 'nein')), 8)  # abstimmung_tage = 7
    zurueck(abstimmung('A Frist um, ohne Stimme'), 8)

    # Entwurfsschleife in der Beratung, Frist der Unterstützer verstrichen (§ 5 Abs 12)
    antrag, _unterstuetzer, er = werkstatt_lage(ordnung)
    frist_verstreichen(einreichen(client, antrag, er))

    # Aussetzungen (§ 6 Abs 3 lit d). Die eine läuft seit drei Tagen, nach sechs Tagen Abstimmung: Ohne sie
    # wäre die Frist (sieben Tage) um, mit ihr nicht. Die andere begann vor 40 Tagen nach fünf Tagen
    # Abstimmung und endete nach sieben Tagen von selbst: Der Rest der Frist ist längst verstrichen.
    ir = rat()
    laeuft = antrag_in_abstimmung(ordnung)
    beschluss_fassen(client, ir, laeuft, Anlass.AUSSETZUNG, 'Verdacht auf Beeinflussung.')
    Aussetzung.objects.filter(antrag=laeuft).update(beginn=jetzt - T(days=3))
    Antrag.objects.filter(pk=laeuft.pk).update(phase_beginn=jetzt - T(days=9), titel='A ausgesetzt')
    abgelaufen = antrag_in_abstimmung(ordnung)
    beschluss_fassen(client, ir, abgelaufen, Anlass.AUSSETZUNG, 'Verdacht auf Beeinflussung.')
    Aussetzung.objects.filter(antrag=abgelaufen).update(beginn=jetzt - T(days=40))
    Antrag.objects.filter(pk=abgelaufen.pk).update(phase_beginn=jetzt - T(days=45), titel='A Aussetzung abgelaufen')

    # Ein fälliger Beschluss ohne laufenden Antrag — ihn schließt der Nachlauf
    GremienBeschluss.objects.create(
        gremium='koordinationsrat', gegenstand='fällig ohne Antrag', angelegt_von=leute[0],
        optionen=[{'wert': 'dafuer', 'name': 'dafür'}, {'wert': 'dagegen', 'name': 'dagegen'}],
        frist=jetzt - T(days=1),
    )
    # Ein fälliger Beschluss ZU einem sonst ruhenden Antrag — er macht den Antrag zum Einzelfall
    mit_beschluss = neu('U ruhend, aber mit fälligem Beschluss')
    GremienBeschluss.objects.create(
        gremium='koordinationsrat', gegenstand='fällig zum Antrag', angelegt_von=leute[0], antrag=mit_beschluss,
        optionen=[{'wert': 'dafuer', 'name': 'dafür'}, {'wert': 'dagegen', 'name': 'dagegen'}],
        frist=jetzt - T(hours=2),
    )


def _zustand(audit_ab):
    '''Alles, was ein Lauf verändern kann — ohne die Kennungen neu angelegter Zeilen und ohne den
    Zeitstempel der Kette (beides fällt in zwei Läufen verschieden aus).'''
    return {
        'antraege': list(
            Antrag.objects.order_by('pk').values_list(
                'pk', 'phase', 'phase_beginn', 'stimmberechtigte_anzahl', 'stimmberechtigung_stichtag'
            )
        ),
        'aussetzungen': list(Aussetzung.objects.order_by('pk').values_list('pk', 'beendet_am', 'beendet_grund')),
        'entwuerfe': list(Entwurf.objects.order_by('pk').values_list('pk', 'status', 'runde', 'review_frist')),
        'beschluesse': list(
            GremienBeschluss.objects.order_by('frist', 'gegenstand').values_list('gegenstand', 'status', 'ergebnis')
        ),
        'archivierte_beitraege': Kommentar.objects.filter(archiviert_am__isnull=False).count(),
        'audit': [
            tuple(e.ereignis.get(k) for k in ('typ', 'antrag', 'neue_phase', 'wirksam_ab', 'grund', 'stimmberechtigte'))
            for e in AuditEintrag.objects.filter(lfd__gt=audit_ab).order_by('lfd')
        ],
    }


def test_der_lauf_liefert_denselben_endzustand_wie_das_fortschreiben_jedes_einzelnen_antrags(client, ordnung):  # noqa: F811
    _gemischter_bestand(client, ordnung)
    jetzt = timezone.now()  # EIN Zeitpunkt für beide Läufe
    audit_ab = AuditEintrag.objects.order_by('-lfd').values_list('lfd', flat=True).first()
    vorher = _zustand(audit_ab)

    punkt = transaction.savepoint()
    stand_alt = alles_fortschreiben(jetzt, jeden_einzeln=True)  # das alte Muster
    alt = _zustand(audit_ab)
    transaction.savepoint_rollback(punkt)
    assert _zustand(audit_ab) == vorher, 'der Bestand steht wieder wie vor dem ersten Lauf'

    stand_neu = alles_fortschreiben(jetzt)
    neu = _zustand(audit_ab)

    assert stand_neu == stand_alt
    assert neu == alt
    # Der Vergleich ist nicht leer: Der Lauf hat wirklich etwas bewegt — und Ruhendes ruhen lassen.
    phasen = {titel: phase for titel, phase in Antrag.objects.values_list('titel', 'phase')}
    assert phasen['U ruhend'] == 'unterstuetzung' and phasen['U eine Unterstützung fehlt'] == 'unterstuetzung'
    assert phasen['U zwei Unterstützungen, eine zurückgezogen'] == 'unterstuetzung'
    assert phasen['U Frist um'] == 'verfallen' and phasen['U Schwelle erreicht, nie gezählt'] == 'beratung'
    assert phasen['B ruhend'] == 'beratung' and phasen['B Frist um'] == 'abstimmung'
    assert phasen['B liegengeblieben, auch die Abstimmung ist um'] == 'abgelehnt'
    assert phasen['A ruhend'] == 'abstimmung' and phasen['A Frist um, angenommen'] == 'angenommen'
    assert phasen['A Frist um, ohne Stimme'] == 'abgelehnt'
    assert phasen['A ausgesetzt'] == 'abstimmung' and phasen['A Aussetzung abgelaufen'] == 'abgelehnt'
    assert stand_neu['phasenwechsel'] >= 7 and stand_neu['fehler'] == 0
    assert not GremienBeschluss.objects.filter(status=BeschlussStatus.OFFEN, frist__lte=jetzt).exists()
    assert Aussetzung.objects.filter(beendet_am__isnull=False).count() == 1
    assert Aussetzung.objects.filter(beendet_am__isnull=True).count() == 1


def test_ein_zweiter_lauf_zum_selben_zeitpunkt_bewegt_nichts_mehr(client, ordnung):  # noqa: F811
    _gemischter_bestand(client, ordnung)
    jetzt = timezone.now()
    alles_fortschreiben(jetzt)
    audit_ab = AuditEintrag.objects.order_by('-lfd').values_list('lfd', flat=True).first()
    danach = _zustand(audit_ab)
    stand = alles_fortschreiben(jetzt)
    assert stand['phasenwechsel'] == 0 and stand['fehler'] == 0
    assert _zustand(audit_ab) == danach
