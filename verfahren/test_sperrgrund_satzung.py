"""Eine Quelle je Sperrgrund für den Satzungsbezug (GP-176, OCR-16).

Feldhinweis und Sperrseiten nannten für denselben Sperrgrund verschiedene Absätze von § 4, die
Sperrseite für den Ausschluss sogar § 4 Abs 6, den der Satzungsentwurf 2.5 nicht kennt."""

import re
from pathlib import Path

import pytest
from django.urls import reverse

from mitglieder.models import Identitaetsstufe, Mitgliedsstatus
from verfahren.hinweise import HINWEISE
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

WURZEL = Path(__file__).resolve().parent.parent
SPERRCODES = ('gesperrt_ungeprueft', 'gesperrt_pausiert', 'gesperrt_ausgeschlossen', 'nicht_stimmberechtigt')
ZITAT = re.compile(r'§ 4 Abs (\d+)')


def _absaetze_von_paragraf_4() -> set[str]:
    """Die Absätze von § 4 aus dem öffentlichen Satzungs-Baukasten (Abbild des Entwurfs 2.5)."""
    text = (WURZEL / 'docs' / 'partner' / 'SATZUNG_BAUKASTEN.md').read_text(encoding='utf-8')
    abschnitt = text.split('## § 4 ', 1)[1].split('\n## ', 1)[0]
    return set(re.findall(r'^(\d+)\. ', abschnitt, flags=re.MULTILINE))


def test_jeder_sperrcode_hat_genau_ein_zitat_und_der_absatz_existiert():
    absaetze = _absaetze_von_paragraf_4()
    assert absaetze == {'1', '2', '3', '4', '5'}
    for code in SPERRCODES:
        satzung = HINWEISE[code]['satzung']
        assert ZITAT.fullmatch(satzung), code
        assert ZITAT.fullmatch(satzung).group(1) in absaetze, code
        zitate = ZITAT.findall(str(HINWEISE[code]['text']))
        assert zitate == [ZITAT.fullmatch(satzung).group(1)], code  # der Feldhinweis zitiert dieselbe Stelle


@pytest.mark.parametrize('vorlage', ['mitwirkung_ruht.html', 'nur_bestaetigte.html'])
def test_sperrseiten_zitieren_nicht_selbst(vorlage):
    quelle = (WURZEL / 'verfahren' / 'templates' / 'verfahren' / vorlage).read_text(encoding='utf-8')
    assert not ZITAT.search(quelle)


@pytest.mark.django_db
@pytest.mark.parametrize(('stufe', 'status', 'code'), [
    (Identitaetsstufe.UNGEPRUEFT, Mitgliedsstatus.AKTIV, 'gesperrt_ungeprueft'),
    (Identitaetsstufe.GEPRUEFT, Mitgliedsstatus.PAUSIERT, 'gesperrt_pausiert'),
    (Identitaetsstufe.GEPRUEFT, Mitgliedsstatus.AUSGESCHLOSSEN, 'gesperrt_ausgeschlossen'),
])
def test_sperrseite_nennt_den_absatz_aus_dem_woerterbuch(client, ordnung, stufe, status, code):  # noqa: F811
    m = mitglied_anlegen('gesperrt', stufe=stufe)
    m.status = status
    m.save(update_fields=['status'])
    client.force_login(m)
    antwort = client.post(reverse('verfahren:einbringen'), {'titel': 'T', 'wortlaut': 'W'})
    assert antwort.status_code == 403
    seite = antwort.content.decode()
    assert ZITAT.findall(seite.split('<main', 1)[1].split('</main>', 1)[0]) == [
        ZITAT.fullmatch(HINWEISE[code]['satzung']).group(1)
    ]
