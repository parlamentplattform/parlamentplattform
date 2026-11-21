"""Die öffentliche Fachliste und der Lostopf (§ 6 Abs 7, FB-I1).

Die Satzung verlangt eine „öffentlich geführte Liste", aus der die Fachleute je Antrag
ausgelost werden — samt „Offenlegung von Interessenbindungen und Honoraren". Ohne diese Liste
wäre das Los eine Auswahl unter Unbekannten.
"""

from __future__ import annotations

import itertools
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from gremien.models import Fachliste, Gremium, lostopf_der_fachliste, unvereinbar
from gremien.test_werkstatt import mitglied_anlegen, ordnung, rolle_geben  # noqa: F401
from plattform_core.losziehung import ziehen
from verfahren.models import Kategorie

pytestmark = pytest.mark.django_db

_ZAEHLER = itertools.count()


def eintragen(name: str | None = None, fachgebiete=(), **felder) -> Fachliste:
    mitglied = mitglied_anlegen(name or f"fach{next(_ZAEHLER)}")
    eintrag = Fachliste.objects.create(mitglied=mitglied, **felder)
    for slug in fachgebiete:
        kategorie, _ = Kategorie.objects.get_or_create(
            slug=slug, defaults={"name": slug.capitalize()}
        )
        eintrag.fachgebiete.add(kategorie)
    return eintrag


def test_jeder_eintrag_bekommt_einen_stabilen_schluessel():
    """Mit ihm rechnet die Ziehung — er muss bleiben, auch wenn der Name geht."""
    eintrag = eintragen()
    schluessel = eintrag.schluessel
    assert schluessel.startswith("F-") and len(schluessel) == 10
    eintrag.interessenbindungen = "Vorstand eines Verkehrsvereins"
    eintrag.save()
    eintrag.refresh_from_db()
    assert eintrag.schluessel == schluessel


def test_nach_widerruf_steht_der_schluessel_statt_des_namens():
    """§ 8 Abs 4: „nach Widerruf werden die betroffenen Inhalte pseudonymisiert, wobei der
    sachliche Inhalt … erhalten bleibt." Loswert und Platz bleiben also nachrechenbar."""
    eintrag = eintragen("frau-mueller")
    assert eintrag.anzeigename == eintrag.mitglied.anzeigename
    eintrag.einwilligung_widerrufen_am = timezone.localdate()
    eintrag.save(update_fields=["einwilligung_widerrufen_am"])
    assert eintrag.anzeigename == eintrag.schluessel


def test_die_liste_steht_oeffentlich_mit_interessenbindungen_und_honoraren(client):
    """§ 6 Abs 7 nennt beides ausdrücklich — und die Liste ist ohne Anmeldung zu lesen."""
    eintragen(
        fachgebiete=["verkehr"],
        interessenbindungen="Beirat einer Verkehrsplanungsgesellschaft",
        honorare="Gutachten für die Stadt Linz, 2025, 3.400 Euro",
    )
    inhalt = client.get(reverse("gremien:fachliste")).content.decode()
    assert "Beirat einer Verkehrsplanungsgesellschaft" in inhalt
    assert "Gutachten für die Stadt Linz" in inhalt
    assert "Verkehr" in inhalt


def test_wer_im_integritaetsrat_sitzt_lost_nicht_mit():
    """§ 6 Abs 3 lit a: „Seine Mitglieder dürfen keinem anderen Rat angehören.\"

    Geprüft wird am Lostopf, nicht in der Ansicht: Wer es dort vergisst, hat es nie."""
    eintrag = eintragen()
    assert unvereinbar(eintrag.mitglied) == ""
    rolle_geben(eintrag.mitglied, Gremium.INTEGRITAETSRAT)
    assert "Integritätsrats" in unvereinbar(eintrag.mitglied)
    kandidat = next(k for k in lostopf_der_fachliste() if k.schluessel == eintrag.schluessel)
    assert kandidat.ausgeschlossen is True


def test_wer_ein_mandat_ausuebt_lost_nicht_mit():
    from mandatare.models import Mandat

    eintrag = eintragen()
    Mandat.objects.create(mitglied=eintrag.mitglied, bezeichnung="Gemeinderat")
    assert "Mandat" in unvereinbar(eintrag.mitglied)


def test_ein_beendetes_mandat_hindert_nicht():
    from mandatare.models import Mandat

    eintrag = eintragen()
    Mandat.objects.create(
        mitglied=eintrag.mitglied,
        bezeichnung="Gemeinderat",
        beendet=timezone.localdate() - timedelta(days=1),
    )
    assert unvereinbar(eintrag.mitglied) == ""


def test_ein_gestrichener_eintrag_bleibt_lesbar_lost_aber_nicht_mehr():
    """Grundregel 7: Aus dem Eintrag wurde vielleicht schon gelost — dann muss er bleiben."""
    eintrag = eintragen(gestrichen_am=timezone.localdate(), gestrichen_grund="Auf eigenen Wunsch.")
    kandidat = eintrag.als_kandidat()
    assert kandidat.ausgeschlossen is True and kandidat.ausschlussgrund == "gestrichen"
    assert Fachliste.objects.filter(pk=eintrag.pk).exists()


def test_aus_der_fachliste_laesst_sich_wirklich_ziehen():
    """Der Weg vom Modell in den Kern — ohne Django-Objekte in der Rechnung."""
    for _ in range(8):
        eintragen(fachgebiete=["verkehr"])
    kandidaten = lostopf_der_fachliste()
    ziehung = ziehen("a" * 64, kandidaten, [3], fachgebiete=["verkehr"])
    assert len(ziehung.gruppen[0]) == 3
    gezogen = {p.schluessel for p in ziehung.plaetze}
    assert gezogen <= set(Fachliste.objects.values_list("schluessel", flat=True))


def test_die_unvereinbarkeit_kostet_nicht_zwei_abfragen_je_kopf(client):
    """Befund #44: Liste und Lostopf prüften je Eintrag Integritätsrat und Mandat einzeln —
    bei 2.000 Fachleuten 4.000 Abfragen je Aufruf, und der Lostopf läuft in der Anfrage eines
    beliebigen Besuchers. Jetzt zwei Mengen für alle: Die Zahl der Abfragen wächst nicht mit."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    rolle_geben(eintragen().mitglied, Gremium.INTEGRITAETSRAT)
    for _ in range(4):
        eintragen(fachgebiete=("verkehr",))
    with CaptureQueriesContext(connection) as klein:
        assert client.get(reverse("gremien:fachliste")).status_code == 200
    with CaptureQueriesContext(connection) as topf_klein:
        lostopf_der_fachliste()
    for _ in range(20):
        eintragen(fachgebiete=("verkehr", "bildung"))
    with CaptureQueriesContext(connection) as gross:
        antwort = client.get(reverse("gremien:fachliste"))
    with CaptureQueriesContext(connection) as topf_gross:
        topf = lostopf_der_fachliste()
    assert len(gross) == len(klein), f"Liste: {len(klein)} → {len(gross)} Abfragen"
    assert len(topf_gross) == len(topf_klein), f"Lostopf: {len(topf_klein)} → {len(topf_gross)} Abfragen"
    assert antwort.context["gefuehrt"] == 24  # die Regel gilt weiter: der Integritätsrat lost nicht mit
    assert sum(1 for k in topf if k.ausgeschlossen) == 1
    assert {"verkehr", "bildung"} <= {slug for k in topf for slug in k.fachgebiete}


def test_die_seite_sagt_ehrlich_dass_der_bestellweg_fehlt(client):
    """§ 6 Abs 8 verlangt Ausschreibung und Bestätigung durch die Mitgliederversammlung.

    Beides gibt es nicht — und die Seite behauptet es auch nicht."""
    eintragen()
    inhalt = client.get(reverse("gremien:fachliste")).content.decode()
    assert "noch\nnicht" in inhalt or "noch nicht" in inhalt
    assert "trägt die Verwaltung die Liste ein" in inhalt


# --- GP-009: Der Pflegeweg der Fachliste für die Verwaltung -----------------------------------


def _verwaltung(client):
    admin = mitglied_anlegen('verwaltung')
    admin.ist_admin = True
    admin.save()
    client.force_login(admin)
    return admin


def _eintragen_post(client, mitglied, **felder):
    daten = {'aktion': 'eintragen', 'mitglied': mitglied.pk, 'einwilligung': 'on', **felder}
    return client.post(reverse('gremien:fachliste_aktion'), daten, follow=True)


def test_die_verwaltung_traegt_ein_und_daraus_wird_gelost(client, ordnung):  # noqa: F811
    """GP-009: Kein Weg der Anwendung legte einen Eintrag der Fachliste an — es wurde nie gelost,
    obwohl Seite und Fahrtenbuch (FB-I1) sagen, die Verwaltung trage die Liste ein."""
    from gremien.test_auslosung import antrag_in_beratung
    from verfahren.models import AuditEintrag

    admin = _verwaltung(client)
    verkehr = Kategorie.objects.get_or_create(slug='verkehr', defaults={'name': 'Verkehr'})[0]
    # Der Weg dorthin: Die Rollenverwaltung nennt die Seite — ohne Verweis fände sie nur, wer die Adresse kennt.
    assert reverse('gremien:fachliste_verwaltung') in client.get(reverse('gremien:rollen')).content.decode()
    assert client.get(reverse('gremien:fachliste_verwaltung')).status_code == 200
    leute = [mitglied_anlegen(f'fachfrau{i}') for i in range(3)]
    _eintragen_post(
        client, leute[0], fachgebiete=[verkehr.pk],
        interessenbindungen='Beirat einer Verkehrsplanungsgesellschaft', honorare='Gutachten 2025',
    )
    for mitglied in leute[1:]:
        _eintragen_post(client, mitglied)
    assert Fachliste.objects.count() == 3
    erster = Fachliste.objects.get(mitglied=leute[0])
    assert list(erster.fachgebiete.all()) == [verkehr] and erster.honorare == 'Gutachten 2025'
    eintraege = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis['typ'] == 'fachliste_eingetragen']
    assert len(eintraege) == 3 and all(e['einwilligung'] is True and e['durch'] == admin.pk for e in eintraege)
    assert all('mitglied' not in e and 'Beirat' not in str(e) for e in eintraege)
    client.logout()
    liste = client.get(reverse('gremien:fachliste')).content.decode()
    assert all(e.schluessel in liste for e in Fachliste.objects.all())
    assert 'Beirat einer Verkehrsplanungsgesellschaft' in liste
    antrag_in_beratung(ordnung)
    assert any(e.ereignis['typ'] == 'expertenrat_ausgelost' for e in AuditEintrag.objects.all())


def test_ohne_einwilligung_wird_niemand_eingetragen(client):
    _verwaltung(client)
    mitglied = mitglied_anlegen('ungefragt')
    antwort = client.post(
        reverse('gremien:fachliste_aktion'), {'aktion': 'eintragen', 'mitglied': mitglied.pk}, follow=True
    )
    assert not Fachliste.objects.exists()
    assert 'Einwilligung' in antwort.content.decode()


def test_niemand_steht_zweimal_auf_der_liste(client):
    _verwaltung(client)
    mitglied = mitglied_anlegen('doppelt')
    _eintragen_post(client, mitglied)
    antwort = _eintragen_post(client, mitglied)
    assert Fachliste.objects.count() == 1
    assert 'steht bereits auf der Fachliste' in antwort.content.decode()


def test_streichen_braucht_einen_grund_und_loescht_nichts(client):
    from verfahren.models import AuditEintrag

    admin = _verwaltung(client)
    eintrag = eintragen('streichkandidatin')
    aktion = reverse('gremien:fachliste_aktion')
    client.post(aktion, {'aktion': 'streichen', 'eintrag': eintrag.pk, 'grund': ''})
    eintrag.refresh_from_db()
    assert eintrag.gefuehrt
    client.post(aktion, {'aktion': 'streichen', 'eintrag': eintrag.pk, 'grund': 'Auf eigenen Wunsch.'})
    eintrag.refresh_from_db()
    assert not eintrag.gefuehrt and eintrag.gestrichen_grund == 'Auf eigenen Wunsch.'
    assert eintrag.gestrichen_am == timezone.localdate()
    gestrichen = [e.ereignis for e in AuditEintrag.objects.all() if e.ereignis['typ'] == 'fachliste_gestrichen']
    assert len(gestrichen) == 1 and gestrichen[0]['eintrag'] == eintrag.pk and gestrichen[0]['durch'] == admin.pk
    # Der frei geschriebene Grund steht nur am Eintrag, nicht in der unveränderlichen Kette (Live-Stand;
    # ob er dorthin gehört, entscheidet der Gründer, GP-009).
    assert 'grund' not in gestrichen[0]
    client.post(aktion, {'aktion': 'streichen', 'eintrag': eintrag.pk, 'grund': 'Noch einmal.'})
    eintrag.refresh_from_db()
    assert eintrag.gestrichen_grund == 'Auf eigenen Wunsch.'  # ein gestrichener Eintrag wird nicht überschrieben
    assert client.post(aktion, {'aktion': 'streichen', 'eintrag': 'abc', 'grund': 'x'}).status_code == 404


def test_die_pflege_der_fachliste_ist_der_verwaltung_vorbehalten(client):
    """Gast, Mitglied und Ratsmitglied werden abgewiesen — lesend wie schreibend."""
    ziel = mitglied_anlegen('ziel')
    seite, aktion = reverse('gremien:fachliste_verwaltung'), reverse('gremien:fachliste_aktion')
    daten = {'aktion': 'eintragen', 'mitglied': ziel.pk, 'einwilligung': 'on'}
    assert client.get(seite).status_code == 302 and client.post(aktion, daten).status_code == 302  # Gast: zur Anmeldung
    ratsmitglied = mitglied_anlegen('ratsmitglied')
    rolle_geben(ratsmitglied, Gremium.KOORDINATIONSRAT)
    for konto in (mitglied_anlegen('einfach'), ratsmitglied):
        client.force_login(konto)
        assert client.get(seite).status_code == 403
        assert client.post(aktion, daten).status_code == 403
    assert not Fachliste.objects.exists()


# --- GP-009 (Rest): Selbsterklärung, Wiederaufnahme, Grund nur am Eintrag --------------------


def _audit(typ):
    from verfahren.models import AuditEintrag

    return [
        {k: v for k, v in e.ereignis.items() if k not in ('zeit', 'salz')}
        for e in AuditEintrag.objects.order_by('lfd') if e.ereignis.get('typ') == typ
    ]


def test_das_mitglied_erklaert_die_einwilligung_selbst_und_die_verwaltung_traegt_ohne_haken_ein(client):
    """GP-009: Bisher hielt nur die Verwaltung die Einwilligung fest. Das Mitglied erklärt sie im
    Profil selbst; danach trägt die Verwaltung ohne eigenen Haken ein."""
    from django.template import Context, Template

    mitglied = mitglied_anlegen('selbsterklaerend')
    client.force_login(mitglied)
    vorlage = Template('{% load gremien_profil %}{% fachliste_einwilligung %}')
    from django.test import RequestFactory

    anfrage = RequestFactory().get('/profil/')
    anfrage.user = mitglied
    karte = vorlage.render(Context({'request': anfrage, 'user': mitglied}))
    assert reverse('gremien:fachliste_einwilligung') in karte and 'value="erklaeren"' in karte
    client.post(reverse('gremien:fachliste_einwilligung'), {'aktion': 'erklaeren'})
    from gremien.models import FachlistenEinwilligung

    assert FachlistenEinwilligung.liegt_vor(mitglied)
    assert _audit('fachliste_einwilligung')[-1]['aktion'] == 'erklaert'
    karte = vorlage.render(Context({'request': anfrage, 'user': mitglied}))
    assert 'value="widerrufen"' in karte

    admin = _verwaltung(client)
    seite = client.get(reverse('gremien:fachliste_verwaltung')).content.decode()
    assert 'selbsterklaerend' in seite  # die Verwaltung sieht, wer selbst eingewilligt hat
    client.post(reverse('gremien:fachliste_aktion'), {'aktion': 'eintragen', 'mitglied': mitglied.pk})
    eintrag = Fachliste.objects.get(mitglied=mitglied)
    ereignis = _audit('fachliste_eingetragen')[-1]
    assert ereignis['einwilligung'] is True and ereignis['selbst_erklaert'] is True and ereignis['durch'] == admin.pk

    # Wer geführt wird, widerruft im Profil nicht (Gegenlesen, E-10.8): Wie die Nennung des Namens auf der
    # Liste widerrufen wird, ist nicht entschieden — Eintrag, Name und Erklärung bleiben, wie sie sind.
    client.force_login(mitglied)
    karte = vorlage.render(Context({'request': anfrage, 'user': mitglied}))
    assert 'value="widerrufen"' not in karte and 'value="erklaeren"' not in karte
    vorher = len(_audit('fachliste_einwilligung'))
    client.post(reverse('gremien:fachliste_einwilligung'), {'aktion': 'widerrufen'})
    eintrag.refresh_from_db()
    assert FachlistenEinwilligung.liegt_vor(mitglied)
    assert eintrag.einwilligung_widerrufen_am is None and eintrag.anzeigename == mitglied.anzeigename
    assert len(_audit('fachliste_einwilligung')) == vorher
    client.force_login(admin)
    client.post(reverse('gremien:fachliste_aktion'), {'aktion': 'eintragen', 'mitglied': mitglied_anlegen('zweite').pk})
    assert Fachliste.objects.count() == 1  # ohne Selbsterklärung und ohne Haken: niemand


def test_eine_erklaerung_laesst_sich_zuruecknehmen_solange_niemand_gefuehrt_wird(client):
    """GP-009, Gegenlesen: Vor dem Eintrag und nach einer Streichung nimmt das Mitglied seine Erklärung
    im Profil zurück — die Verwaltung trägt dann nicht mehr ohne eigenen Haken ein und nimmt nicht
    ohne ihn wieder auf. Am Eintrag selbst und am Namen auf der Liste ändert das nichts (E-10.8)."""
    from gremien.models import FachlistenEinwilligung

    ziel = reverse('gremien:fachliste_einwilligung')
    aktion = reverse('gremien:fachliste_aktion')
    mitglied = mitglied_anlegen('ueberlegt-es-sich')
    client.force_login(mitglied)
    client.post(ziel, {'aktion': 'erklaeren'})
    client.post(ziel, {'aktion': 'widerrufen'})
    assert not FachlistenEinwilligung.liegt_vor(mitglied)
    assert _audit('fachliste_einwilligung')[-1] == {
        'typ': 'fachliste_einwilligung', 'aktion': 'widerrufen', 'eintrag': None, 'durch': mitglied.pk,
    }
    admin = _verwaltung(client)
    client.post(aktion, {'aktion': 'eintragen', 'mitglied': mitglied.pk})
    assert not Fachliste.objects.exists()  # zurückgenommen: ohne Haken trägt niemand ein

    # Nach einer Streichung: Die alte Erklärung gilt nicht still weiter, wenn das Mitglied sie zurücknimmt.
    client.force_login(mitglied)
    client.post(ziel, {'aktion': 'erklaeren'})
    client.force_login(admin)
    client.post(aktion, {'aktion': 'eintragen', 'mitglied': mitglied.pk})
    eintrag = Fachliste.objects.get(mitglied=mitglied)
    client.post(aktion, {'aktion': 'streichen', 'eintrag': eintrag.pk, 'grund': 'Auf eigenen Wunsch.'})
    client.force_login(mitglied)
    client.post(ziel, {'aktion': 'widerrufen'})
    eintrag.refresh_from_db()
    assert not FachlistenEinwilligung.liegt_vor(mitglied)
    assert eintrag.einwilligung_widerrufen_am is None  # der Eintrag bleibt, wie er ist
    assert _audit('fachliste_einwilligung')[-1]['eintrag'] == eintrag.pk
    client.force_login(admin)
    client.post(aktion, {'aktion': 'wieder_aufnehmen', 'eintrag': eintrag.pk})
    eintrag.refresh_from_db()
    assert not eintrag.gefuehrt  # ohne Erklärung und ohne Haken keine Wiederaufnahme


def _profilkarte(mitglied):
    from django.template import Context, Template
    from django.test import RequestFactory

    anfrage = RequestFactory().get('/profil/')
    anfrage.user = mitglied
    return Template('{% load gremien_profil %}{% fachliste_einwilligung %}').render(
        Context({'request': anfrage, 'user': mitglied})
    )


def _meldungen(antwort):
    from django.contrib.messages import get_messages

    return ' '.join(str(m) for m in get_messages(antwort.wsgi_request))


def test_am_gestrichenen_eintrag_sagt_die_ruecknahme_offen_was_sie_bewirkt(client):
    """Datenschutz-Fund: Am gestrichenen Eintrag bestätigte das Profil einen datierten Widerruf, während der
    Name dort öffentlich stehen bleibt (E-10.8 offen). Karte, Knopf und Meldung sagen jetzt, dass die
    Rücknahme nur eine erneute Eintragung verhindert und wo man die Nennung des Namens widerruft."""
    ziel = reverse('gremien:fachliste_einwilligung')
    mitglied = mitglied_anlegen('gestrichen-und-genannt')
    client.force_login(mitglied)
    client.post(ziel, {'aktion': 'erklaeren'})
    admin = _verwaltung(client)
    client.post(reverse('gremien:fachliste_aktion'), {'aktion': 'eintragen', 'mitglied': mitglied.pk})
    eintrag = Fachliste.objects.get(mitglied=mitglied)
    client.post(reverse('gremien:fachliste_aktion'), {'aktion': 'streichen', 'eintrag': eintrag.pk, 'grund': 'Auf eigenen Wunsch.'})
    assert admin.pk
    client.force_login(mitglied)
    karte = _profilkarte(mitglied)
    assert 'value="widerrufen"' in karte
    assert 'Einwilligung zur erneuten Eintragung zurücknehmen' in karte
    assert 'Einwilligung widerrufen<' not in karte
    assert 'nur, dass die Verwaltung Sie erneut einträgt' in karte
    assert 'bleibt mit Ihrem Namen' in karte and 'plattform@ddoe.at' in karte
    antwort = client.post(ziel, {'aktion': 'widerrufen'}, follow=True)
    meldung = _meldungen(antwort)
    assert 'Die Verwaltung trägt Sie nicht erneut ein.' in meldung
    assert 'bleibt mit Ihrem Namen' in meldung and 'plattform@ddoe.at' in meldung
    assert 'Einwilligung zur Fachliste widerrufen.' not in meldung
    eintrag.refresh_from_db()
    assert eintrag.einwilligung_widerrufen_am is None  # am Eintrag selbst ändert sich nichts (E-10.8)


def test_ohne_eintrag_bleibt_der_widerruf_wie_er_war(client):
    ziel = reverse('gremien:fachliste_einwilligung')
    mitglied = mitglied_anlegen('nie-gefuehrt')
    client.force_login(mitglied)
    client.post(ziel, {'aktion': 'erklaeren'})
    karte = _profilkarte(mitglied)
    assert 'value="widerrufen"' in karte and 'Einwilligung widerrufen<' in karte
    assert 'erneuten Eintragung' not in karte and 'bleibt mit Ihrem Namen' not in karte
    meldung = _meldungen(client.post(ziel, {'aktion': 'widerrufen'}, follow=True))
    assert 'Einwilligung zur Fachliste widerrufen.' in meldung and 'bleibt mit Ihrem Namen' not in meldung


def test_steht_am_gestrichenen_eintrag_schon_der_schluessel_behauptet_niemand_einen_bleibenden_namen(client):
    """Gegenlesen: Hat die Verwaltung die Nennung am gestrichenen Eintrag schon widerrufen (Schlüssel statt
    Name, § 8 Abs 4), wäre der Satz „bleibt mit Ihrem Namen auf der Fachliste stehen“ falsch. Karte und
    Meldung bleiben dann beim schlichten Widerruf; am Eintrag ändert sich weiter nichts."""
    ziel = reverse('gremien:fachliste_einwilligung')
    mitglied = mitglied_anlegen('gestrichen-ohne-namen')
    eintrag = Fachliste.objects.create(
        mitglied=mitglied, gestrichen_am=timezone.localdate(), einwilligung_widerrufen_am=timezone.localdate()
    )
    assert eintrag.anzeigename == eintrag.schluessel
    client.force_login(mitglied)
    client.post(ziel, {'aktion': 'erklaeren'})
    karte = _profilkarte(mitglied)
    assert 'value="widerrufen"' in karte and 'Einwilligung widerrufen<' in karte
    assert 'erneuten Eintragung' not in karte and 'bleibt mit Ihrem Namen' not in karte
    meldung = _meldungen(client.post(ziel, {'aktion': 'widerrufen'}, follow=True))
    assert 'Einwilligung zur Fachliste widerrufen.' in meldung and 'bleibt mit Ihrem Namen' not in meldung
    stand = Fachliste.objects.get(pk=eintrag.pk)
    assert stand.einwilligung_widerrufen_am == eintrag.einwilligung_widerrufen_am and not stand.gefuehrt


def test_die_verwaltung_sieht_als_selbst_erklaert_nur_wer_es_erklaert_hat(client):
    """GP-009, Gegenlesen: Die Karte „Einwilligung selbst erklärt“ nannte jedes aktive Mitglied ohne
    Eintrag — auch wer nie etwas erklärt hatte. Sie nennt nur offene Erklärungen."""
    from gremien.models import FachlistenEinwilligung

    erklaert = mitglied_anlegen('hat-erklaert')
    mitglied_anlegen('nie-erklaert')
    widerrufen = mitglied_anlegen('hat-widerrufen')
    schon_gefuehrt = eintragen('schon-gefuehrt').mitglied
    for m in (erklaert, widerrufen, schon_gefuehrt):
        FachlistenEinwilligung.erklaeren(m)
    FachlistenEinwilligung.widerrufen(widerrufen)
    _verwaltung(client)
    seite = client.get(reverse('gremien:fachliste_verwaltung'))
    assert [m.username for m in seite.context['selbst_erklaert']] == ['hat-erklaert']


def test_die_profilkarte_sieht_nur_wer_sich_erklaeren_kann(client):
    """GP-009, Gegenlesen: Wen der Endpunkt abweist (hier: pausiert), dem zeigt das Profil die Karte nicht."""
    from django.template import Context, Template
    from django.test import RequestFactory

    vorlage = Template('{% load gremien_profil %}{% fachliste_einwilligung %}')
    pausiert = mitglied_anlegen('pausiert')
    pausiert.status = 'pausiert'
    pausiert.save(update_fields=['status'])
    anfrage = RequestFactory().get('/profil/')
    anfrage.user = pausiert
    assert 'fachliste-einwilligung' not in vorlage.render(Context({'request': anfrage, 'user': pausiert}))
    client.force_login(pausiert)
    assert client.post(reverse('gremien:fachliste_einwilligung'), {'aktion': 'erklaeren'}).status_code == 403


def test_die_selbsterklaerung_braucht_ein_aktives_parteikonto(client):
    from gremien.models import FachlistenEinwilligung

    ziel = reverse('gremien:fachliste_einwilligung')
    assert client.post(ziel, {'aktion': 'erklaeren'}).status_code == 302  # Gast: zur Anmeldung
    assert client.get(ziel).status_code in (302, 405)
    ausgetreten = mitglied_anlegen('ausgetreten')
    ausgetreten.status = 'ausgetreten'
    ausgetreten.save(update_fields=['status'])
    client.force_login(ausgetreten)
    assert client.post(ziel, {'aktion': 'erklaeren'}).status_code == 403
    assert not FachlistenEinwilligung.objects.exists()


def test_ein_gestrichener_eintrag_laesst_sich_wieder_aufnehmen(client):
    """GP-009: Gestrichen hieß für immer — die Verwaltung konnte niemanden zurückholen. Der frei geschriebene
    Grund steht nur am Eintrag, nicht in der Kette: Ob ein personenbezogener Freitext dauerhaft in die
    unveränderliche Kette gehört, entscheidet der Gründer (Schlusspflege 0.115.0, Live-Stand)."""
    admin = _verwaltung(client)
    eintrag = eintragen('rueckkehrerin')
    aktion = reverse('gremien:fachliste_aktion')
    client.post(aktion, {'aktion': 'streichen', 'eintrag': eintrag.pk, 'grund': 'Auszeit bis Herbst.'})
    eintrag.refresh_from_db()
    assert eintrag.gestrichen_grund == 'Auszeit bis Herbst.'
    assert _audit('fachliste_gestrichen')[-1] == {'typ': 'fachliste_gestrichen', 'eintrag': eintrag.pk, 'durch': admin.pk}
    seite = client.get(reverse('gremien:fachliste_verwaltung')).content.decode()
    assert 'value="wieder_aufnehmen"' in seite
    # Sichtprüfung 0.115.0: Datum und Grund der Streichung sind beschriftet
    assert f'gestrichen am {eintrag.gestrichen_am:%d.%m.%Y} · Grund: Auszeit bis Herbst.' in seite
    # Ohne Einwilligung keine Wiederaufnahme.
    client.post(aktion, {'aktion': 'wieder_aufnehmen', 'eintrag': eintrag.pk})
    eintrag.refresh_from_db()
    assert not eintrag.gefuehrt
    client.post(aktion, {'aktion': 'wieder_aufnehmen', 'eintrag': eintrag.pk, 'einwilligung': 'on'})
    eintrag.refresh_from_db()
    assert eintrag.gefuehrt and eintrag.gestrichen_grund == '' and eintrag.einwilligung_widerrufen_am is None
    ereignis = _audit('fachliste_wieder_aufgenommen')[-1]
    assert ereignis == {
        'typ': 'fachliste_wieder_aufgenommen', 'eintrag': eintrag.pk, 'einwilligung': True,
        'selbst_erklaert': False, 'durch': admin.pk,
    }
    assert Fachliste.objects.count() == 1  # derselbe Eintrag, derselbe Schlüssel — kein zweiter daneben
    # Ein ausgetretenes Mitglied kommt nicht zurück.
    eintrag.mitglied.status = 'ausgetreten'
    eintrag.mitglied.save(update_fields=['status'])
    client.post(aktion, {'aktion': 'streichen', 'eintrag': eintrag.pk, 'grund': 'Austritt'})
    client.post(aktion, {'aktion': 'wieder_aufnehmen', 'eintrag': eintrag.pk, 'einwilligung': 'on'})
    eintrag.refresh_from_db()
    assert not eintrag.gefuehrt
    assert client.post(aktion, {'aktion': 'wieder_aufnehmen', 'eintrag': 'x'}).status_code == 404


def test_die_wiederaufnahme_ist_der_verwaltung_vorbehalten(client):
    eintrag = eintragen('gestrichen-fremd', gestrichen_am=timezone.localdate(), gestrichen_grund='x')
    daten = {'aktion': 'wieder_aufnehmen', 'eintrag': eintrag.pk, 'einwilligung': 'on'}
    ratsmitglied = mitglied_anlegen('ratsmitglied-w')
    rolle_geben(ratsmitglied, Gremium.KOORDINATIONSRAT)
    for konto in (eintrag.mitglied, ratsmitglied):
        client.force_login(konto)
        assert client.post(reverse('gremien:fachliste_aktion'), daten).status_code == 403
    eintrag.refresh_from_db()
    assert not eintrag.gefuehrt
