"""GP-089 (DEN-02, MG-14): Der Ordner eines Mandats im persönlichen Export führt jedes Feld der Modelle dieser App —
oder nennt es mit Grund in `EXPORT_AUSNAHMEN`. Vertrauensfragen, Stellungnahmen, die Gründe und Vermerke stehen
im Export, nicht in der Ausnahmeliste."""

import json
from datetime import UTC, date, datetime, timedelta

import pytest
from django.apps import apps
from django.core.serializers.json import DjangoJSONEncoder

from mandatare.gemeindeexport import (
    EXPORT_AUSNAHMEN,
    EXPORT_SCHLUESSEL,
    mandat_exportieren,
    mandate_fuer_export,
)
from mandatare.models import (
    Aufgabe,
    Bericht,
    Berichtsart,
    FreiwilligeBegruendung,
    Livemeldung,
    Mandat,
    Sitzung,
    Stellungnahme,
    Tagesordnungspunkt,
)
from mitglieder.models import Gemeinde
from verfahren.test_vertrauensfrage import abweichung, altmandat, einbringen  # noqa: F401
from verfahren.test_views_aktionen import mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db

#: Was die Befunde ausdrücklich vermissten — keines davon darf in der Ausnahmeliste stehen.
GEFORDERT = {
    ('Mandat', f) for f in (
        'foto_typ', 'vertrauen_entzogen_am', 'rueckgabe_ersucht_bis', 'rueckgabezusage', 'rueckgabezusage_am',
        'mandatsvereinbarung_lit_h_am', 'mandatsvereinbarung_endet_am', 'vertretung_beendet_am', 'bestaetigt_am',
    )
} | {('Stellungnahme', 'text'), ('Stellungnahme', 'erstellt_am'), ('Bericht', 'aufgabe_id')} | {
    ('Vertrauensfrage', f.attname) for f in apps.get_model('mandatare', 'Vertrauensfrage')._meta.concrete_fields
    if f.attname not in ('mandat_id',)
}


def _schluessel(modell: str, feld: str) -> str:
    if (modell, feld) in EXPORT_SCHLUESSEL:
        return EXPORT_SCHLUESSEL[(modell, feld)]
    return feld[:-3] if feld.endswith('_id') else feld


def _ordner(ordnung, altmandat):  # noqa: F811
    """Ein Mandat mit allen Stempeln, einer Vertrauensfrage samt Stellungnahme, Sammelbericht, Rechenschaft mit
    freiwilliger Begründung und einer Sitzung — jeder Wert unverwechselbar."""
    md = altmandat
    stempel = {
        'vertrauen_entzogen_am': datetime(2001, 2, 3, 7, tzinfo=UTC), 'rueckgabe_ersucht_bis': date(2001, 3, 4),
        'rueckgabezusage': 'abgegeben', 'rueckgabezusage_am': date(2001, 4, 5),
        'mandatsvereinbarung_lit_h_am': date(2001, 5, 6), 'mandatsvereinbarung_endet_am': date(2001, 6, 7),
        'vertretung_beendet_am': date(2031, 7, 8), 'bestaetigt_am': date(2001, 8, 9), 'foto_typ': 'image/png',
    }
    for feld, wert in stempel.items():
        setattr(md, feld, wert)
    md.save()
    sitzungstag = Aufgabe.objects.create(mandat=md, titel='ZQ-Sitzungstag', sitzungstag=True,
                                         frist=datetime(2026, 1, 5, 18, tzinfo=UTC))
    Bericht.objects.create(mandat=md, art=Berichtsart.SAMMELBERICHT, aufgabe=sitzungstag, text='ZQ-Sammelbericht')
    eintrag = abweichung(md, gegenstand='ZQ-Gegenstand', aufgabe=sitzungstag)
    FreiwilligeBegruendung.objects.create(rechenschaft=eintrag, text='ZQ-Freiwillig')
    sitzung = Sitzung.objects.create(mandat=md, aufgabe=sitzungstag, beginn=datetime(2026, 1, 5, 17, tzinfo=UTC))
    punkt = Tagesordnungspunkt.objects.create(sitzung=sitzung, nummer=1, titel='ZQ-Punkt')
    Livemeldung.objects.create(sitzung=sitzung, punkt=punkt, text='ZQ-Meldung')
    antrag = einbringen(mitglied_anlegen('gp089carl'), md, ordnung, anlaesse=[eintrag])
    vf = antrag.vertrauensfrage
    vf.sperrhinweis, vf.aktenkennung = 'ZQ-Sperrhinweis', 'ZQ-Akte'
    vf.angefochten_am = datetime(2001, 9, 10, 8, tzinfo=UTC)
    vf.save()
    Stellungnahme.objects.create(vertrauensfrage=vf, text='ZQ-Stellungnahme', erstellt_am=datetime(2001, 10, 11, 9, tzinfo=UTC))
    # Gemeindearbeit (0.112.0) — damit jede Zeilenart mindestens einmal im Ordner steht
    ort = Gemeinde.objects.create(kennziffer='49999', name='ZQ-Ort', bezirk='ZQ-Bezirk', bundesland='oberoesterreich')
    md.gemeinde = ort
    md.save(update_fields=['gemeinde'])
    beginn = datetime(2026, 1, 7, 16, tzinfo=UTC)
    md.sprechstunden.create(gemeinde=ort, beginn=beginn, ende=beginn + timedelta(hours=1), treffpunkt='ZQ-Treffpunkt')
    initiative = md.ratsinitiativen.create(gemeinde=ort, art='anfrage', titel='ZQ-Initiative', text='Frage')
    initiative.meldungen.create(art='eingebracht', datum=date(2026, 1, 8), text='ZQ-Vermerk')
    sitzungstag.gemeindesitzungsquellen.create(gemeinde=ort, sitzung_am=date(2026, 1, 5), art='ratsbeschluesse')
    md.haushaltsquellen.create(gemeinde=ort, jahr=2026, art='voranschlag')
    md.gemeindeprojekte.create(gemeinde=ort).staende.create(
        lage='vorgestellt', titel='ZQ-Projekt', quelle='https://example.org/zq', stand_am=date(2026, 1, 9)
    )
    (md,) = mandate_fuer_export(md.mitglied)
    return md, stempel


def test_ordner_des_mandats_fuehrt_jedes_feld_oder_begruendet_die_auslassung(ordnung, altmandat):  # noqa: F811
    md, stempel = _ordner(ordnung, altmandat)
    ordner = mandat_exportieren(md)
    roh = json.dumps(ordner, ensure_ascii=False, cls=DjangoJSONEncoder)

    fehlt = []
    for modell in apps.get_app_config('mandatare').get_models():
        name = modell.__name__
        felder = [f.attname for f in modell._meta.concrete_fields] + [f.name for f in modell._meta.many_to_many]
        for feld in felder:
            if (name, feld) in EXPORT_AUSNAHMEN:
                continue
            if f'"{_schluessel(name, feld)}":' not in roh:
                fehlt.append((name, feld))
    assert fehlt == [], fehlt
    assert all(grund.strip() for grund in EXPORT_AUSNAHMEN.values())
    assert GEFORDERT.isdisjoint(EXPORT_AUSNAHMEN), GEFORDERT & set(EXPORT_AUSNAHMEN)

    # Die Werte selbst, nicht nur die Schlüssel
    for feld, wert in stempel.items():
        assert ordner[feld] == wert, feld
    for marke in ('ZQ-Stellungnahme', 'ZQ-Sperrhinweis', 'ZQ-Akte', 'ZQ-Freiwillig', 'ZQ-Punkt', 'ZQ-Meldung',
                  '2001-09-10T08:00', '2001-10-11T09:00'):
        assert marke in roh, marke
    (vf,) = ordner['vertrauensfragen']
    assert vf['stellungnahmen'][0]['text'] == 'ZQ-Stellungnahme' and vf['anlaesse'] == [md.rechenschaft.get().pk]
    (bericht,) = ordner['berichte']
    assert bericht['aufgabe'] == ordner['aufgaben'][0]['aufgabe']  # der Sammelbericht nennt seinen Sitzungstag


def test_ordner_behaelt_die_schluessel_bis_0_114(altmandat):  # noqa: F811
    """Wer den Export bisher las, findet alles wieder: dieselben Schlüssel, dazu neue."""
    (md,) = mandate_fuer_export(altmandat.mitglied)
    ordner = mandat_exportieren(md)
    bisher = {'mandat', 'bezeichnung', 'ebene', 'gebiet', 'angetreten', 'beendet', 'vorstellung', 'gemeindearbeit',
              'aufgaben', 'berichte', 'rechenschaft', 'sitzungen'}
    assert bisher <= set(ordner)
    assert ordner['mandat'] == md.pk and ordner['vertrauensfragen'] == []


def test_ordner_eines_altbestands_ohne_stempel_und_ohne_lichtbild(altmandat):  # noqa: F811
    (md,) = mandate_fuer_export(Mandat.objects.get(pk=altmandat.pk).mitglied)
    ordner = mandat_exportieren(md)
    assert ordner['vertrauen_entzogen_am'] is None and ordner['foto_typ'] == '' and ordner['bestaetigt_am'] is None
    json.dumps(ordner, cls=DjangoJSONEncoder)
