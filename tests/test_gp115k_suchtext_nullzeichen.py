'''Nullzeichen in Suchtexten (Abschlusskorrektur 0.115.0).

Text aus der Adresse ging ungeprüft in Datenbankvergleiche (`titel__icontains`, `name__icontains`,
`phase__in`). PostgreSQL nimmt in Textwerten kein Nullzeichen an: psycopg wirft „DataError: PostgreSQL text
fields cannot contain NUL (0x00) bytes“, und die Seite antwortete mit 500 — /parlament/ und /gemeinde/ ohne
Anmeldung. Jetzt entfernt eine gemeinsame Stelle (`plattform_core.parlamentlisten.suchtext`) das
Nullzeichen beim Einlesen.

Die Seitentests laufen auf beiden Datenbanken; SQLite nimmt das Nullzeichen hin, der Beweis für die
Antwort 200 liegt auf PostgreSQL (CI-Job `pruefen_postgres`). Dass der Text bereinigt in die Abfrage geht,
prüfen die Tests auf jeder Datenbank am Kontext der Seite.'''

import pytest
from django.urls import reverse

from gremien.models import Gremium
from gremien.test_werkstatt import rolle_geben
from plattform_core.parlamentlisten import suchtext
from verfahren.models import antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

NUL = '\x00'


def test_suchtext_entfernt_nullzeichen_raender_und_ueberlaenge():
    assert suchtext('a\x00b') == 'ab'
    assert suchtext('  Sitzungs\x00protokolle \x00 ') == 'Sitzungsprotokolle'
    assert suchtext('\x00') == '' and suchtext('') == '' and suchtext(None) == ''
    assert suchtext('  unverändert  ') == 'unverändert'
    assert suchtext('ä' * 300, 140) == 'ä' * 140
    assert suchtext('\x00' * 5 + 'abc', 2) == 'ab'  # erst bereinigen, dann kürzen
    assert suchtext('abc', 0) == 'abc' and suchtext('abc', None) == 'abc'  # ohne Grenze


@pytest.mark.django_db
def test_parlament_sucht_mit_nullzeichen_im_suchtext_ohne_anmeldung(client, ordnung):  # noqa: F811
    antrag_einbringen(mitglied_anlegen('steller'), **ANTRAG, ordnung=ordnung)
    antwort = client.get('/parlament/?suche=Sitzungs%00protokolle')
    assert antwort.status_code == 200
    assert antwort.context['suchtext'] == 'Sitzungsprotokolle'
    assert NUL not in antwort.content.decode()
    assert ANTRAG['titel'] in antwort.content.decode()  # der Titel wird ohne das Nullzeichen gefunden

    assert client.get('/parlament/?suche=a%00b').status_code == 200
    nur_null = client.get('/parlament/?suche=%00')
    assert nur_null.status_code == 200 and nur_null.context['suchtext'] == ''  # wie ohne Suche


@pytest.mark.django_db
def test_gemeindesuche_mit_nullzeichen_im_ort_ohne_anmeldung(client):
    antwort = client.get('/gemeinde/?ort=a%00b')
    assert antwort.status_code == 200
    assert antwort.context['suche'] == 'ab'
    assert NUL not in antwort.content.decode()
    assert client.get('/gemeinde/?ort=%00&seite=%00').status_code == 200


@pytest.mark.django_db
def test_antragsseite_mit_nullzeichen_in_der_archivwahl_ohne_anmeldung(client, ordnung):  # noqa: F811
    '''`?archiv=<phase>` wählt die Phase, deren Beiträge mitkommen — der Wert geht in `phase__in`.'''
    antrag = antrag_einbringen(mitglied_anlegen('steller'), **ANTRAG, ordnung=ordnung)
    seite = reverse('verfahren:antrag', args=[antrag.pk])
    assert client.get(seite + '?archiv=a%00b').status_code == 200
    assert client.get(seite + '?archiv=%00').status_code == 200
    assert client.get(seite + '?archiv=unterstuetzung').status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize('gremium, seite', [(Gremium.INTEGRITAETSRAT, 'gremien:integritaet'), (Gremium.KOORDINATIONSRAT, 'gremien:koordination')])
def test_antragsauswahl_der_raete_mit_nullzeichen_in_der_suche(client, ordnung, gremium, seite):  # noqa: F811
    antrag_einbringen(mitglied_anlegen('steller'), **ANTRAG, ordnung=ordnung)
    rat = mitglied_anlegen('rat')
    rolle_geben(rat, gremium)
    client.force_login(rat)
    antwort = client.get(reverse(seite) + '?antrag_suche=Sitzungs%00protokolle&antrag=1%00')
    assert antwort.status_code == 200
    assert antwort.context['antrag_suche'] == 'Sitzungsprotokolle'
    assert NUL not in antwort.content.decode()
