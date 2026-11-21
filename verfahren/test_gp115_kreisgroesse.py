'''Kreisgröße und Prüfgrundlage des örtlichen Kreises (Gesamtprüfung GP-057).

Vor der Abstimmung war nicht zu sehen, wie viele Stimmberechtigte der festgehaltene örtliche Kreis hat
und dass er auf Selbstauskunft beruht (Entscheidung A0-29: „Selbstauskunft zur tatsächlichen Meldung
genügt vorerst“). Das Ereignis zum festgehaltenen Kreis trägt jetzt die Zahl der am Einbringungstag
Stimmberechtigten, die Antragsseite zeigt sie mit dem Wort „Selbstauskunft“.

Nicht festgehalten und nicht gezeigt wird die Zahl aller Konten im Kreis (auch ungeprüfter): Sie steht
heute nirgends öffentlich — das ist eine offene Frage an den Gründer.'''

import re

import pytest
from django.urls import reverse
from django.utils import timezone

from mitglieder.models import Identitaetsstufe, Mitglied, Wohnsitzart
from verfahren.audit_oeffentlich import ereignis_oeffentlich
from verfahren.models import Antrag, AuditEintrag, OertlicheTeilnahme
from verfahren.teilnahme import kreis_festhalten, oertlich_zulaessig
from verfahren.test_oertliche_teilnahme import _einbringen, menschen  # noqa: F401
from verfahren.test_teilnahme_fundament import mit_ort, orte, vorbereiten  # noqa: F401
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def _ereignis(antrag):
    return AuditEintrag.objects.get(ereignis__typ='teilnehmerkreis_festgehalten', ereignis__antrag=antrag.pk).ereignis


def _ungeprueft(name, ort):
    '''Ein Konto im Ort, das zum Kreis gehört, aber (noch) nicht stimmberechtigt ist.'''
    konto = mitglied_anlegen(name, tage=800)
    konto.wohnsitz, konto.wohnsitz_art = ort, Wohnsitzart.OESTERREICH
    felder = konto.identitaetsstufe_setzen(Identitaetsstufe.UNGEPRUEFT)
    konto.save(update_fields=['wohnsitz', 'wohnsitz_art', *felder])
    return konto


def _kreisabsatz(client, antrag):
    seite = client.get(reverse('verfahren:antrag', args=[antrag.pk])).content.decode()
    return re.search(r'<p class="meldung" id="teilnehmerkreis">(.*?)</p>', seite, re.S).group(1)


def test_das_ereignis_traegt_die_stimmberechtigten_des_einbringungstags_als_zahl(client, menschen, ordnung):  # noqa: F811
    leute, ort, _fremdort = menschen
    _ungeprueft('neuling', ort)
    antrag = _einbringen(client, leute['autor'])
    ereignis = _ereignis(antrag)
    # im Kreis: Autor, „ort“ und der ungeprüfte Neuling — stimmberechtigt sind zwei
    assert OertlicheTeilnahme.objects.filter(antrag=antrag).count() == 3
    assert ereignis['stimmberechtigte'] == 2 and type(ereignis['stimmberechtigte']) is int
    assert ereignis['stichtag'] == timezone.localdate(antrag.eingebracht_am).isoformat()
    # ohne Kontobezug und ohne die Zahl aller Konten: nichts zu schwärzen, nichts Neues veröffentlicht
    assert 'konten' not in ereignis and 'mitglied' not in ereignis and 'durch' not in ereignis
    assert ereignis_oeffentlich(ereignis) == (ereignis, False)
    assert antrag.kreis_stimmberechtigte() == 2


def test_die_zahl_ist_dieselbe_wie_die_grundgesamtheit_der_einbringung(client, menschen, ordnung):  # noqa: F811
    '''Kennt die Ordnung einen Anteil (Erstbestand: fünf Prozent), nennt schon `antrag_eingebracht` die
    Stimmberechtigten des Kreises und die eingefrorene Ordnung führt sie als Grundgesamtheit — beide
    Ereignisse derselben Einbringung nennen dieselbe Zahl. Die Ordnung der Tests kennt keinen Anteil;
    ohne ihn hier zu setzen, verglich der Test nichts.'''
    leute, ort, _fremdort = menschen
    _ungeprueft('neuling', ort)
    ordnung.regeln = {**ordnung.regeln, 'unterstuetzung_anteil': 0.05}
    ordnung.save(update_fields=['regeln'])
    antrag = _einbringen(client, leute['autor'])
    eingebracht = AuditEintrag.objects.get(ereignis__typ='antrag_eingebracht', ereignis__antrag=antrag.pk).ereignis
    assert eingebracht['stimmberechtigte'] == _ereignis(antrag)['stimmberechtigte'] == 2
    assert antrag.policy_snapshot['unterstuetzung_grundgesamtheit'] == 2 == antrag.kreis_stimmberechtigte()


def test_ohne_anteil_nennt_nur_das_kreisereignis_die_zahl(client, menschen, ordnung):  # noqa: F811
    '''Ohne Anteil in der Ordnung rechnet die Einbringung keine Grundgesamtheit: `antrag_eingebracht`
    trägt keine Zahl, das Ereignis zum festgehaltenen Kreis schon.'''
    leute, _ort, _fremdort = menschen
    antrag = _einbringen(client, leute['autor'])
    eingebracht = AuditEintrag.objects.get(ereignis__typ='antrag_eingebracht', ereignis__antrag=antrag.pk).ereignis
    assert 'stimmberechtigte' not in eingebracht
    assert antrag.policy_snapshot.get('unterstuetzung_grundgesamtheit', 0) == 0
    assert _ereignis(antrag)['stimmberechtigte'] == 2 == antrag.kreis_stimmberechtigte()


def test_die_antragsseite_zeigt_die_zahl_und_das_wort_selbstauskunft(client, menschen, ordnung):  # noqa: F811
    leute, ort, _fremdort = menschen
    _ungeprueft('neuling', ort)
    antrag = _einbringen(client, leute['autor'])
    client.logout()  # öffentlich, auch für Gäste
    absatz = _kreisabsatz(client, antrag)
    assert 'Stimmberechtigte am Einbringungstag: 2.' in absatz
    assert 'Selbstauskunft' in absatz and 'nicht amtlich geprüft' in absatz
    assert 'nicht festgehalten' not in absatz


def test_ein_kreis_ohne_stimmberechtigte_zeigt_null_nicht_nichts(client, ordnung, orte):  # noqa: F811
    autor = _ungeprueft('autor', orte[0])
    antrag = vorbereiten(ordnung, autor)
    kreis_festhalten(antrag)
    assert _ereignis(antrag)['stimmberechtigte'] == 0 and antrag.kreis_stimmberechtigte() == 0
    absatz = _kreisabsatz(client, antrag)
    assert 'Stimmberechtigte am Einbringungstag: 0.' in absatz and 'Selbstauskunft' in absatz


def test_altbestand_ohne_die_zahl_gilt_als_nicht_festgehalten(client, ordnung, orte, monkeypatch):  # noqa: F811
    '''Ein Kreis von vor dieser Fassung: Sein Ereignis trägt keine Zahl. Nichts wird nachgerechnet.'''
    autor = mit_ort('autor', orte[0])
    mit_ort('zweite', orte[0])
    antrag = vorbereiten(ordnung, autor)
    echt = AuditEintrag.anhaengen
    with monkeypatch.context() as frueher:
        frueher.setattr(
            AuditEintrag, 'anhaengen',
            lambda ereignis: echt({k: v for k, v in ereignis.items() if k not in ('stimmberechtigte', 'stichtag')}),
        )
        kreis_festhalten(antrag)
    assert set(_ereignis(antrag)) == {'typ', 'antrag', 'fassung', 'gebiet', 'festgehalten_am', 'zeit'}
    antrag.refresh_from_db()
    assert antrag.kreis_stimmberechtigte() is None
    absatz = _kreisabsatz(client, antrag)
    assert 'Stimmberechtigte am Einbringungstag: nicht festgehalten.' in absatz
    assert 'Selbstauskunft' in absatz


def test_altbestand_mit_anteil_nennt_die_zahl_der_einbringung(client, menschen, ordnung, monkeypatch):  # noqa: F811
    '''Auflage zu GP-057: Ein Kreis von vor dieser Fassung trägt keine Zahl — rechnete die Ordnung die
    Schwelle aber als Anteil (Live-Erstbestand: fünf Prozent), nennt `antrag_eingebracht` desselben Antrags
    die Stimmberechtigten des Kreises schon öffentlich. Die Seite zeigt diese Zahl statt „nicht festgehalten“;
    nachgerechnet wird nichts.'''
    leute, ort, _fremdort = menschen
    _ungeprueft('neuling', ort)
    ordnung.regeln = {**ordnung.regeln, 'unterstuetzung_anteil': 0.05}
    ordnung.save(update_fields=['regeln'])
    echt = AuditEintrag.anhaengen

    def frueher(ereignis, *args, **kwargs):
        if ereignis.get('typ') == 'teilnehmerkreis_festgehalten':
            ereignis = {k: v for k, v in ereignis.items() if k not in ('stimmberechtigte', 'stichtag')}
        return echt(ereignis, *args, **kwargs)

    with monkeypatch.context() as alt:
        alt.setattr(AuditEintrag, 'anhaengen', frueher)
        antrag = _einbringen(client, leute['autor'])
    assert 'stimmberechtigte' not in _ereignis(antrag)
    eingebracht = AuditEintrag.objects.get(ereignis__typ='antrag_eingebracht', ereignis__antrag=antrag.pk).ereignis
    assert eingebracht['stimmberechtigte'] == 2
    mit_ort('spaeter', ort)  # wer danach dazukommt, ändert die festgehaltene Zahl nicht
    assert Antrag.objects.get(pk=antrag.pk).kreis_stimmberechtigte() == 2
    client.logout()
    absatz = _kreisabsatz(client, antrag)
    assert 'Stimmberechtigte am Einbringungstag: 2.' in absatz and 'nicht festgehalten' not in absatz


def test_bundesweite_und_alte_verfahren_bekommen_keine_kreiszahl(client, ordnung, orte):  # noqa: F811
    autor = mit_ort('autor', orte[0])
    bund = vorbereiten(ordnung, autor, ebene='bund')
    kreis_festhalten(bund)
    assert 'stimmberechtigte' not in _ereignis(bund) and bund.kreis_stimmberechtigte() is None
    alt = Antrag.objects.create(
        titel='Altverfahren', eingebracht_von=autor, policy_snapshot=ordnung.als_policy().als_dict(),
        ebene='gemeinde', gebiet=orte[0].name,
    )
    assert alt.kreis_stimmberechtigte() is None
    seite = client.get(reverse('verfahren:antrag', args=[alt.pk])).content.decode()
    assert 'Stimmberechtigte am Einbringungstag' not in seite and 'Selbstauskunft' not in seite


def test_wer_zum_kreis_gehoert_aendert_sich_nicht(client, menschen, ordnung):  # noqa: F811
    leute, ort, _fremdort = menschen
    neuling = _ungeprueft('neuling', ort)
    antrag = _einbringen(client, leute['autor'])
    antrag.refresh_from_db()
    assert oertlich_zulaessig(antrag, leute['autor']) and oertlich_zulaessig(antrag, leute['ort'])
    assert oertlich_zulaessig(antrag, Mitglied.objects.get(pk=neuling.pk))  # ungeprüft bleibt im Kreis
    assert not oertlich_zulaessig(antrag, leute['fremd'])
