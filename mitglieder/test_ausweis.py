"""Der Mitgliedsausweis (FB-K8): PDF im Kartenformat, SVG-Vorschau, Prüfcode, Prüfseite, Download,
Anhang am Freischaltungsbrief — und was die Karte nicht verrät. Dazu die Maße: Sicherheitszone,
Zeilenabstände, Ruhezone des QR-Codes, Einpassen langer Namen, Buchstaben außerhalb von WinAnsi."""

import re
import struct
import zlib
from io import BytesIO

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone
from pypdf import PdfReader

from mitglieder import ausweis as aw
from mitglieder.models import Identitaetsstufe, Mitglied, Mitgliedsstatus
from mitglieder.post import freischaltung_senden, willkommen_senden
from mitglieder.profil import austreten
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen  # noqa: F401

pytestmark = pytest.mark.django_db(transaction=True)

PT = aw.PT
INNEN = aw.INNEN_MM
BREITE = aw.SEITE_BREITE_MM - 2 * INNEN
RAND = aw.BESCHNITT_MM + aw.SICHERHEIT_MM  # so weit vom Seitenrand bleibt alles Wichtige weg


@pytest.fixture(autouse=True)
def _basis(settings):
    settings.DDOE_BASIS_URL = "https://parlament.ddoe.at"


@pytest.fixture
def logo_kaputt(monkeypatch):
    """Das Logo lässt sich nicht lesen — jede Zeichnung scheitert mit ValueError."""

    def kaputt(*_a, **_k):
        raise ValueError("Logo-PNG nicht lesbar")

    aw._logo_schablone.cache_clear()
    monkeypatch.setattr(aw, "_png", kaputt)
    yield
    aw._logo_schablone.cache_clear()


def geprueftes_mitglied(name="anna", **extra):
    m = mitglied_anlegen(name, tage=400)
    m.first_name, m.last_name = "Anna", "Müller-Öhlinger"
    m.identitaetsstufe = Identitaetsstufe.GEPRUEFT
    for feld, wert in extra.items():
        setattr(m, feld, wert)
    m.save()
    return m


def audit(typ):
    """Die Ereignisse eines Typs ohne den Zeitstempel, den `anhaengen` selbst dazuschreibt."""
    return [
        {k: v for k, v in e.ereignis.items() if k != "zeit"}
        for e in AuditEintrag.objects.all()
        if e.ereignis.get("typ") == typ
    ]


def stroeme(pdf: bytes) -> list[bytes]:
    """Alle Flate-Ströme der Datei, entpackt — Inhalte der Seiten und das Logo."""
    return [zlib.decompress(s) for s in re.findall(rb"stream\n(.*?)\nendstream", pdf, re.S)]


def seiten(pdf: bytes) -> bytes:
    """Nur die Seiteninhalte (sie beginnen mit der Hintergrundfarbe „0.…“), ohne die Logo-Bits."""
    return b"\n".join(s for s in stroeme(pdf) if s.startswith(b"0."))


class Protokoll(aw.Zeichner):
    """Zeichnet nichts, merkt sich alles — für Maße, Abstände und Sicherheitszonen."""

    def __init__(self):
        self.texte, self.flaechen, self.logos, self.qrs = [], [], [], []

    def seite_beginnen(self, hintergrund):
        pass

    def flaeche(self, x, y, b, h, farbe, radius=0.0):
        self.flaechen.append((x, y, b, h))

    def text(self, x, y, inhalt, groesse, farbe, fett=False, kursiv=False, laufweite=0.0):
        self.texte.append((x, y, inhalt, groesse, aw.textbreite_mm(inhalt, groesse, fett, laufweite_pt=laufweite)))

    def logo(self, x, y, groesse, farbe):
        self.logos.append((x, y, groesse))

    def qr(self, x, y, groesse, matrix, farbe):
        self.qrs.append((x, y, groesse, len(matrix)))


def protokoll(m, seite=aw.zeichne_vorderseite):
    p = Protokoll()
    seite(p, aw.ausweis_daten(m))
    return p


def in_der_sicherheitszone(p):
    """Alles Wichtige mindestens 3 mm innerhalb der Schnittkante — Texte samt Ober- und Unterlänge,
    Logo, QR-Feld."""
    for x, y, inhalt, groesse, breite in p.texte:
        oben, unten = y - 0.72 * groesse / PT, y + 0.22 * groesse / PT
        assert x >= RAND - 0.01 and x + breite <= aw.SEITE_BREITE_MM - RAND + 0.01, inhalt
        assert oben >= RAND - 0.01 and unten <= aw.SEITE_HOEHE_MM - RAND + 0.01, inhalt
    for x, y, _groesse in p.logos:
        assert x >= RAND - 0.01 and y >= RAND - 0.01
    for x, y, groesse, _n in p.qrs:
        assert x + groesse <= aw.SEITE_BREITE_MM - RAND + 0.01 and y + groesse <= aw.SEITE_HOEHE_MM - RAND + 0.01


def ohne_ueberlappung(p):
    """Texte auf einer Grundlinie stehen nebeneinander; Texte übereinander halten Zeilenabstand."""
    texte = sorted(p.texte, key=lambda t: (t[1], t[0]))
    for i, (x, y, inhalt, groesse, breite) in enumerate(texte):
        for x2, y2, inhalt2, groesse2, breite2 in texte[i + 1 :]:
            nebeneinander = x2 >= x + breite + 0.5 or x >= x2 + breite2 + 0.5
            if y2 == y:
                assert nebeneinander, (inhalt, inhalt2)
            elif not nebeneinander:
                assert y2 - y >= 0.75 * max(groesse, groesse2) / PT + 0.3, (inhalt, inhalt2)


def nichts_im_qr_feld(p):
    (fx, fy, fb, fh) = next(f for f in p.flaechen if f[2] == aw.QR_FELD_MM and f[3] == aw.QR_FELD_MM)
    for x, y, inhalt, groesse, breite in p.texte:
        oben, unten = y - 0.72 * groesse / PT, y + 0.22 * groesse / PT
        getrennt = x + breite <= fx or x >= fx + fb or unten <= fy or oben >= fy + fh
        assert getrennt, inhalt


# ── Voraussetzungen und Prüfcode ──────────────────────────────────────────────────────────


def test_einen_ausweis_bekommt_nur_wer_mitglied_mit_gepruefter_identitaet_ist():
    m = mitglied_anlegen("neu", tage=1, stufe=Identitaetsstufe.UNGEPRUEFT)
    assert m.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT and aw.ausweis_moeglich(m)
    g = geprueftes_mitglied()
    assert aw.ausweis_moeglich(g) and aw.ausweis_erstellbar(g)
    g.status = Mitgliedsstatus.AUSGESCHLOSSEN
    assert not aw.ausweis_moeglich(g)
    g.status = Mitgliedsstatus.PAUSIERT  # die Mitgliedschaft besteht — nur die Mitwirkung ruht
    assert aw.ausweis_moeglich(g)


def test_ohne_namen_auf_der_karte_ist_der_ausweis_nicht_erstellbar():
    m = geprueftes_mitglied(first_name="", last_name="", pseudonym_oeffentlich="")
    assert aw.ausweis_moeglich(m) and not aw.ausweis_erstellbar(m) and aw.name_fuer_karte(m) == ""
    assert "Mitglied" in m.anzeigename  # der Platzhalter ist kein Name
    m.pseudonym_oeffentlich = "Aurora"
    assert aw.ausweis_erstellbar(m) and aw.name_fuer_karte(m) == "Aurora"
    m.first_name, m.last_name = "  Anna ", "Müller "
    assert aw.name_fuer_karte(m) == "Anna Müller"  # Klarname vor Anzeigename, Leerraum bereinigt


def test_der_pruefcode_wird_einmal_vergeben_und_auditiert_ohne_werte():
    m = geprueftes_mitglied()
    code = aw.ausweis_code_sicherstellen(m)
    assert re.fullmatch(r"[0-9a-f]{10}", code) and m.ausweis_ausgestellt_am is not None
    assert aw.ausweis_code_sicherstellen(m) == code
    m.refresh_from_db()
    assert m.ausweis_code == code
    assert audit("ausweis_ausgestellt") == [{"typ": "ausweis_ausgestellt", "mitglied": m.pk}]
    assert aw.pruef_url(m) == f"https://parlament.ddoe.at/ausweis/{m.pk}/{code}/"


def test_zwei_gleichzeitige_erste_aufrufe_vergeben_genau_einen_code():
    m = geprueftes_mitglied()
    a, b = Mitglied.objects.get(pk=m.pk), Mitglied.objects.get(pk=m.pk)
    code_a = aw.ausweis_code_sicherstellen(a)
    code_b = aw.ausweis_code_sicherstellen(b)  # sieht in der Datenbank schon den Code von a
    assert code_a == code_b != "" and b.ausweis_ausgestellt_am == a.ausweis_ausgestellt_am
    assert len(audit("ausweis_ausgestellt")) == 1


def test_ein_code_ausserhalb_von_ascii_oder_ohne_vergabe_ist_nie_gueltig(client):
    m = geprueftes_mitglied()
    assert not aw.ausweis_gueltig(m, "a" * 10)  # noch kein Code vergeben — nichts zu vergleichen
    code = aw.ausweis_code_sicherstellen(m)
    assert aw.ausweis_gueltig(m, code)
    assert not aw.ausweis_gueltig(m, "") and not aw.ausweis_gueltig(None, code)
    assert not aw.ausweis_gueltig(m, "ünïcödé123") and not aw.ausweis_gueltig(m, code + " ")
    antwort = client.get(f"/ausweis/{m.pk}/%C3%BCn%C3%AFc%C3%B6d%C3%A9123/")
    assert antwort.status_code == 200 and 'data-stand="ungueltig"' in antwort.content.decode()


def test_die_angaben_der_karte_sind_deutsch_kurz_und_ohne_adresse(settings):
    m = geprueftes_mitglied(gemeinde="Eferding")
    a = aw.ausweis_daten(m)
    assert a.name == "Anna Müller-Öhlinger" and a.nummer == m.pk and a.nummer_text == f"{m.pk:06d}"
    assert re.fullmatch(r"[A-Za-zäöüÄÖÜ]+ \d{4}", a.seit) and a.stufe == "Beitrag verbucht"
    assert a.plattform == "parlament.ddoe.at" and a.pruef_adresse == f"parlament.ddoe.at/ausweis/{m.pk}/{a.code}"
    assert "Eferding" not in (a.name, a.seit, a.stufe, a.ausgestellt)
    m.identitaetsstufe = Identitaetsstufe.PRAESENZ
    assert aw.ausweis_daten(m).stufe == "persönlich geprüft"
    m.identitaetsstufe = Identitaetsstufe.EID
    assert aw.ausweis_daten(m).stufe == "elektronisch geprüft"
    m.first_name = m.last_name = ""
    m.pseudonym_oeffentlich = "Aurora"
    assert aw.ausweis_daten(m).name == "Aurora"  # ohne Klarname der Anzeigename, nie die Adresse
    settings.DDOE_BASIS_URL = "https://demo.example.org/"
    a = aw.ausweis_daten(m)
    assert a.plattform == "demo.example.org" and a.pruef_url == f"https://demo.example.org/ausweis/{m.pk}/{a.code}/"
    assert "demo.example.org" in PdfReader(BytesIO(aw.ausweis_pdf(m))).pages[0].extract_text()


# ── Schrift und Maße ──────────────────────────────────────────────────────────────────────


def test_unicode_namen_bleiben_im_pdf_unveraendert():
    for vor, nach in (("Đorđe", "Đukić"), ("Łukasz", "Şahin"), ("Мария", "Петрова")):
        m = geprueftes_mitglied(first_name=vor, last_name=nach)
        pdf = aw.ausweis_pdf(m)
        assert f"{vor} {nach}" in PdfReader(BytesIO(pdf)).pages[0].extract_text()
        assert b"/FontFile2" in pdf
        m.delete()


def test_die_schriftbreiten_kennen_fett_und_normal():
    assert aw._BREITEN["n"] == 556 and aw._BREITEN_FETT["n"] == 611 and aw._BREITEN_FETT["b"] == 611
    assert aw._BREITEN_FETT["Ä"] == 722 and aw._BREITEN_FETT["@"] == 975 and aw._BREITEN_FETT[":"] == 333
    assert aw.textbreite_mm("Anna", 10, fett=True) > aw.textbreite_mm("Anna", 10)
    assert aw.textbreite_mm("ab", 10, laufweite_pt=2) == pytest.approx(aw.textbreite_mm("ab", 10) + 2 / PT)


def test_lange_namen_werden_kleiner_oder_zweizeilig_statt_abgeschnitten():
    assert aw._name_zeilen("Anna Müller-Öhlinger", BREITE) == [("Anna Müller-Öhlinger", 13)]
    lang = "Maximiliane Josefine Antonia Habsburg-Lothringen-Wittelsbach"
    zeilen = aw._name_zeilen(lang, BREITE)
    assert len(zeilen) == 2 and " ".join(z for z, _g in zeilen) == lang
    assert all(6 <= g <= 8.5 and aw.textbreite_mm(z, g, True) <= BREITE for z, g in zeilen)
    (einzeln,) = aw._name_zeilen("Donaudampfschifffahrtsgesellschaftskapitänswitwenrente", BREITE)
    assert einzeln[1] < 9 and aw.textbreite_mm(einzeln[0], einzeln[1], True) <= BREITE
    umbruch = aw._umbrechen("ein zwei drei vier fünf sechs sieben acht", 10, 25)
    assert " ".join(umbruch) == "ein zwei drei vier fünf sechs sieben acht" and len(umbruch) >= 3
    assert all(aw.textbreite_mm(z, 10) <= 25 for z in umbruch)  # keine Zeile breiter als erlaubt


@pytest.mark.parametrize(
    ("vorname", "nachname"),
    [
        ("Anna", "Müller-Öhlinger"),
        ("Maximiliane Josefine Antonia", "Habsburg-Lothringen-Wittelsbach"),
        ("Anna", "Donaudampfschifffahrtsgesellschaftskapitänswitwenrente"),
        ("X", "Y"),
    ],
)
def test_beide_seiten_halten_sicherheitszone_und_zeilenabstaende(vorname, nachname):
    m = geprueftes_mitglied(first_name=vorname, last_name=nachname, identitaetsstufe=Identitaetsstufe.EID)
    vorne = protokoll(m)
    in_der_sicherheitszone(vorne)
    ohne_ueberlappung(vorne)
    nichts_im_qr_feld(vorne)
    name_zeilen = aw._name_zeilen(aw.ausweis_daten(m).name, BREITE)
    gezeichnet = [(t[2], t[3]) for t in vorne.texte]
    assert all((z, g) in gezeichnet for z, g in name_zeilen)
    hinten = protokoll(m, aw.zeichne_rueckseite)
    in_der_sicherheitszone(hinten)
    ohne_ueberlappung(hinten)
    assert any("lit b" in t[2] for t in hinten.texte)
    assert any("Nachweis: elektronisch geprüft" in t[2] for t in hinten.texte)


def test_der_qr_code_hat_vier_module_ruhezone_im_weissen_feld():
    m = geprueftes_mitglied()
    p = protokoll(m)
    ((x, y, groesse, n),) = p.qrs
    assert n in (29, 33, 37) and aw.QR_RAND_MM / (groesse / n) >= 4  # ISO/IEC 18004: 4 Module
    (feld,) = [f for f in p.flaechen if f[2] == aw.QR_FELD_MM and f[3] == aw.QR_FELD_MM]
    assert feld[0] + aw.QR_RAND_MM == pytest.approx(x) and feld[1] + aw.QR_RAND_MM == pytest.approx(y)


# ── PDF ───────────────────────────────────────────────────────────────────────────────────


def test_pdf_hat_eine_seite_kartenmass_beschnitt_und_eingebettete_schriften():
    pdf = aw.ausweis_pdf(geprueftes_mitglied())
    leser = PdfReader(BytesIO(pdf), strict=True)
    assert len(leser.pages) == 1
    seite = leser.pages[0]
    assert [float(v)/PT for v in seite.mediabox] == pytest.approx([0, 0, 88.6, 56.98], abs=0.001)
    assert [float(v)/PT for v in seite.trimbox] == pytest.approx([1.5, 1.5, 87.1, 55.48], abs=0.001)
    assert seite.bleedbox == seite.mediabox
    assert b"/FontFile2" in pdf and b"/ToUnicode" in pdf


def test_pdf_enthaelt_name_nummer_nachweis_logo_und_qr():
    m = geprueftes_mitglied()
    pdf = aw.ausweis_pdf(m)
    seite = PdfReader(BytesIO(pdf)).pages[0]
    text = seite.extract_text()
    assert m.get_full_name() in text and f"{m.pk:06d}" in text
    assert "Beitrag verbucht" in text and "MITGLIEDSAUSWEIS" in text
    assert len(seite.images) == 1
    assert seite.get_contents().get_data().count(b"\nf*") > 200


def test_ein_unlesbares_logo_wird_ein_valueerror_kein_absturz(tmp_path):
    breite, hoehe, flaeche, roh = aw._png()
    assert (breite, hoehe) == (500, 500) and len(flaeche) == 500 * 500 and roh.startswith(b"\x89PNG")
    kein_png = tmp_path / "kein.png"
    kein_png.write_bytes(b"GIF89a" + b"\0" * 20)
    with pytest.raises(ValueError):
        aw._png(str(kein_png))
    palette = tmp_path / "palette.png"
    kopf = b"\x89PNG\r\n\x1a\n" + b"\x00\x00\x00\x0dIHDR"
    palette.write_bytes(kopf + struct.pack(">IIBBBBB", 2, 2, 8, 3, 0, 0, 0) + b"\0\0\0\0")
    with pytest.raises(ValueError):
        aw._png(str(palette))
    kurz = tmp_path / "kurz.png"
    kurz.write_bytes(kopf + b"\x00" * 5)
    with pytest.raises(ValueError):
        aw._png(str(kurz))


# ── SVG-Vorschau ──────────────────────────────────────────────────────────────────────────


def test_die_vorschau_zeigt_die_geschnittene_karte_und_laedt_das_logo_nur_einmal():
    m = geprueftes_mitglied()
    vorne, hinten = aw.ausweis_svg(m)
    assert hinten == ""
    for svg in (vorne,):
        assert svg.startswith("<svg ") and 'viewBox="1.5 1.5 85.6 53.98"' in svg and "<script" not in svg
        assert '<use href="#ausweis-logo-bild"/>' in svg
    assert vorne.count("data:image/png;base64,") == 1 and 'id="ausweis-logo-bild"' in vorne
    assert "data:image/png;base64," not in hinten
    assert "Anna Müller-Öhlinger" in vorne and f"{m.pk:06d}" in vorne and "MITGLIEDSAUSWEIS" in vorne
    assert 'id="ausweis-v-karte"' in vorne
    assert 'aria-label="Mitgliedsausweis, Vorderseite: Anna Müller-Öhlinger, Nr. ' in vorne
    assert "Nachweis Beitrag verbucht" in vorne
    assert aw._svg_text('a"b<c>&') == "a&quot;b&lt;c&gt;&amp;"


# ── Post ──────────────────────────────────────────────────────────────────────────────────


def test_der_freischaltungsbrief_traegt_den_ausweis_als_pdf_anhang():
    m = geprueftes_mitglied()
    assert freischaltung_senden(m)
    brief = mail.outbox[-1]
    assert len(brief.attachments) == 1
    name, inhalt, typ = brief.attachments[0]
    assert name == f"Mitgliedsausweis-DDOE-{m.pk:06d}.pdf" and typ == "application/pdf"
    assert inhalt.startswith(b"%PDF-1.4")
    assert f"Mitgliedsausweis Nr. {m.pk:06d} als PDF im Kartenformat" in brief.body
    assert "mit geprüftem Nachweis besteht" in brief.body and "/profil/#ausweis" in brief.body
    assert audit("post")[-1] == {"typ": "post", "art": "freischaltung", "mitglied": m.pk, "anhang": True}
    assert not freischaltung_senden(m)  # einmal je Konto


def test_der_willkommensbrief_enthaelt_den_vorlaeufigen_ausweis():
    m = mitglied_anlegen("neu", tage=1, stufe=Identitaetsstufe.UNGEPRUEFT)
    m.first_name = "Anna"
    m.beitritt = m.beitritt or timezone.localdate()
    m.save()
    assert willkommen_senden(m)
    brief = mail.outbox[-1]
    assert len(brief.attachments) == 1 and "Mitgliedsausweis" in brief.body
    assert "Prüfung ausständig" in PdfReader(BytesIO(brief.attachments[0][1])).pages[0].extract_text()
    assert audit("post")[-1]["anhang"] is True


def test_ohne_namen_geht_der_brief_ohne_anhang_und_das_profil_bittet_um_den_namen(client):
    m = geprueftes_mitglied(first_name="", last_name="", pseudonym_oeffentlich="")
    assert freischaltung_senden(m)
    brief = mail.outbox[-1]
    assert brief.attachments == [] and "sobald er erzeugt ist" in brief.body
    assert audit("post")[-1]["anhang"] is False
    client.force_login(m)
    html = client.get(reverse("mitglieder:profil")).content.decode()
    karte = html.split('id="ausweis"')[1].split('id="austritt"')[0]
    assert "einen Namen auf der Karte" in karte and "<svg" not in karte
    antwort = client.get(reverse("mitglieder:profil_ausweis"), follow=True)
    assert antwort.redirect_chain[-1][0] == reverse("mitglieder:profil")
    assert "einen Namen auf der Karte" in antwort.content.decode()


def test_bei_einer_stoerung_geht_der_brief_ohne_anhang_und_das_profil_bleibt_bedienbar(client, logo_kaputt):
    m = geprueftes_mitglied()
    assert freischaltung_senden(m)
    brief = mail.outbox[-1]
    assert brief.attachments == [] and "sobald er erzeugt ist" in brief.body
    assert audit("post")[-1]["anhang"] is False
    client.force_login(m)
    html = client.get(reverse("mitglieder:profil")).content.decode()
    karte = html.split('id="ausweis"')[1].split('id="austritt"')[0]
    assert "gerade nicht erzeugen" in karte and "<svg" not in karte
    antwort = client.get(reverse("mitglieder:profil_ausweis"), follow=True)
    assert antwort.redirect_chain[-1][0] == reverse("mitglieder:profil")
    assert "gerade nicht erzeugen" in antwort.content.decode()


# ── Web: Download und Prüfseite ───────────────────────────────────────────────────────────


def test_den_ausweis_laedt_nur_das_eigene_gepruefte_konto(client):
    url = reverse("mitglieder:profil_ausweis")
    antwort = client.get(url)
    assert antwort.status_code == 302 and "anmelden" in antwort["Location"]
    ungeprueft = mitglied_anlegen("neu", tage=1, stufe=Identitaetsstufe.UNGEPRUEFT)
    client.force_login(ungeprueft)
    antwort = client.get(url, follow=True)
    assert antwort.redirect_chain[-1][0] == reverse("mitglieder:profil")
    assert "Namen auf der Karte" in antwort.content.decode()
    m = geprueftes_mitglied()
    client.force_login(m)
    antwort = client.get(url)
    assert antwort.status_code == 200 and antwort["Content-Type"] == "application/pdf"
    assert antwort["Content-Disposition"] == f'attachment; filename="Mitgliedsausweis-DDOE-{m.pk:06d}.pdf"'
    assert antwort.content.startswith(b"%PDF-1.4") and "no-store" in antwort["Cache-Control"]


def test_das_profil_zeigt_die_vorschau_oder_sagt_wann_der_ausweis_kommt(client):
    ungeprueft = mitglied_anlegen("neu", tage=1, stufe=Identitaetsstufe.UNGEPRUEFT)
    client.force_login(ungeprueft)
    html = client.get(reverse("mitglieder:profil")).content.decode()
    assert 'id="ausweis"' in html
    hinweis = html.split('id="ausweis"')[1].split('id="austritt"')[0]
    assert "Namen auf der Karte" in hinweis and "<svg" not in hinweis
    m = geprueftes_mitglied()
    client.force_login(m)
    html = client.get(reverse("mitglieder:profil")).content.decode()
    karte = html.split('id="ausweis"')[1].split('id="austritt"')[0]
    assert karte.count("<svg ") == 1 and karte.count("data:image/png;base64,") == 1
    assert reverse("mitglieder:profil_ausweis") in karte and 'viewBox="1.5 1.5 85.6 53.98"' in karte
    assert "Anna Müller-Öhlinger" in karte and "herunterladen (PDF, Kartenformat)" in karte
    assert "Ausweisnummer ist Ihre Mitgliedsnummer" in karte


def test_die_pruefseite_sagt_gueltig_oder_nicht_gueltig_und_nennt_keinen_namen(client):
    m = geprueftes_mitglied()
    code = aw.ausweis_code_sicherstellen(m)
    antwort = client.get(f"/ausweis/{m.pk}/{code}/")
    html = antwort.content.decode()
    assert "no-store" in antwort["Cache-Control"]
    assert 'data-stand="gueltig"' in html and f"Nr. {m.pk:06d} ist gültig" in html and "&#10003;" in html
    assert "Anna" not in html and "Müller" not in html and "Nachweis Beitrag verbucht" in html
    falsch = client.get(f"/ausweis/{m.pk}/{'0' * 10}/").content.decode()
    assert 'data-stand="ungueltig"' in falsch and "keinen gültigen Mitgliedsausweis" in falsch
    assert "geprüftem Nachweis, oder der Code stimmt nicht" in falsch and "&#10007;" in falsch
    assert client.get("/ausweis/999999/abcdefabcd/").status_code == 200
    assert 'data-stand="ungueltig"' in client.get("/ausweis/999999/abcdefabcd/").content.decode()
    # Ohne vergebenen Code gibt es nichts zu prüfen — auch nicht mit leerem Vergleich
    ohne = geprueftes_mitglied("ohne")
    assert 'data-stand="ungueltig"' in client.get(f"/ausweis/{ohne.pk}/{'a' * 10}/").content.decode()


def test_nach_dem_austritt_ist_der_ausweis_nicht_mehr_gueltig(client):
    m = geprueftes_mitglied()
    code = aw.ausweis_code_sicherstellen(m)
    austreten(m)
    m = Mitglied.objects.get(pk=m.pk)
    assert not aw.ausweis_moeglich(m)
    assert 'data-stand="ungueltig"' in client.get(f"/ausweis/{m.pk}/{code}/").content.decode()
