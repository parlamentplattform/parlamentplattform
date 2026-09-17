"""Der Mitgliedsausweis (FB-K8): PDF im Kartenformat, SVG-Vorschau, Prüfcode, Prüfseite, Download,
Anhang am Freischaltungsbrief — und was die Karte nicht verrät."""

import re
import zlib

import pytest
from django.core import mail
from django.urls import reverse

from mitglieder import ausweis as aw
from mitglieder.models import Identitaetsstufe, Mitglied, Mitgliedsstatus
from mitglieder.post import freischaltung_senden, willkommen_senden
from mitglieder.profil import austreten
from verfahren.models import AuditEintrag
from verfahren.test_views_aktionen import mitglied_anlegen  # noqa: F401

pytestmark = pytest.mark.django_db

PT = aw.PT


@pytest.fixture(autouse=True)
def _basis(settings):
    settings.DDOE_BASIS_URL = "https://parlament.ddoe.at"


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


# ── Voraussetzungen und Prüfcode ──────────────────────────────────────────────────────────


def test_einen_ausweis_bekommt_nur_wer_mitglied_mit_gepruefter_identitaet_ist():
    m = mitglied_anlegen("neu", tage=1, stufe=Identitaetsstufe.UNGEPRUEFT)
    assert m.identitaetsstufe == Identitaetsstufe.UNGEPRUEFT and not aw.ausweis_moeglich(m)
    g = geprueftes_mitglied()
    assert aw.ausweis_moeglich(g)
    g.status = Mitgliedsstatus.AUSGESCHLOSSEN
    assert not aw.ausweis_moeglich(g)
    g.status = Mitgliedsstatus.PAUSIERT  # die Mitgliedschaft besteht — nur die Mitwirkung ruht
    assert aw.ausweis_moeglich(g)


def test_der_pruefcode_wird_einmal_vergeben_und_auditiert_ohne_werte():
    m = geprueftes_mitglied()
    code = aw.ausweis_code_sicherstellen(m)
    assert re.fullmatch(r"[0-9a-f]{10}", code) and m.ausweis_ausgestellt_am is not None
    assert aw.ausweis_code_sicherstellen(m) == code
    m.refresh_from_db()
    assert m.ausweis_code == code
    assert audit("ausweis_ausgestellt") == [{"typ": "ausweis_ausgestellt", "mitglied": m.pk}]
    assert aw.pruef_url(m) == f"https://parlament.ddoe.at/ausweis/{m.pk}/{code}/"


def test_die_angaben_der_karte_sind_deutsch_kurz_und_ohne_adresse():
    m = geprueftes_mitglied(gemeinde="Eferding")
    a = aw.ausweis_daten(m)
    assert a.name == "Anna Müller-Öhlinger" and a.nummer == m.pk and a.nummer_text == f"{m.pk:06d}"
    assert re.fullmatch(r"[A-Za-zäöüÄÖÜ]+ \d{4}", a.seit) and a.stufe == "geprüft"
    assert "Eferding" not in (a.name, a.seit, a.stufe, a.ausgestellt)
    m.first_name = m.last_name = ""
    m.pseudonym_oeffentlich = "Aurora"
    assert aw.ausweis_daten(m).name == "Aurora"  # ohne Klarname der Anzeigename, nie die Adresse


# ── PDF ───────────────────────────────────────────────────────────────────────────────────


def test_das_pdf_hat_kartenmass_mit_beschnitt_zwei_seiten_und_gueltige_querverweise():
    m = geprueftes_mitglied()
    pdf = aw.ausweis_pdf(m)
    assert pdf.startswith(b"%PDF-1.4") and pdf.rstrip().endswith(b"%%EOF")
    assert pdf.count(b"/Type /Page ") == 2 and b"/Count 2" in pdf
    breite, hoehe = round(88.60 * PT, 3), round(56.98 * PT, 3)
    assert f"/MediaBox [0 0 {breite:g} {hoehe:g}]".encode() in pdf
    trim = f"/TrimBox [{1.5 * PT:.3f} {1.5 * PT:.3f} {(88.60 - 1.5) * PT:.3f} {(56.98 - 1.5) * PT:.3f}]"
    assert trim.replace(".000", "").encode() in pdf or b"/TrimBox [4.252 4.252 246.898 157.218]" in pdf
    # Querverweise: jeder Offset zeigt auf „n 0 obj“
    xref_start = int(re.search(rb"startxref\n(\d+)\n%%EOF", pdf).group(1))
    assert pdf[xref_start:].startswith(b"xref\n")
    eintraege = re.findall(rb"(\d{10}) 00000 n ", pdf[xref_start:])
    for nr, offset in enumerate(eintraege, start=1):
        assert pdf[int(offset) :].startswith(f"{nr} 0 obj".encode())
    assert b"/Title (Mitgliedsausweis DD\xd6 Nr. " in pdf  # Ö in WinAnsi/PDFDoc


def test_der_seiteninhalt_traegt_name_nummer_und_qr_module_das_logo_ist_eine_schablone():
    m = geprueftes_mitglied()
    pdf = aw.ausweis_pdf(m)
    inhalte = b"\n".join(stroeme(pdf))
    assert "Anna Müller-Öhlinger".encode("cp1252") in inhalte and b"MITGLIEDSAUSWEIS" in inhalte
    assert f"{m.pk:06d}".encode() in inhalte and b"/Logo Do" in inhalte
    assert inhalte.count(b" re") > 200  # die dunklen Module des QR-Codes als Rechtecke
    assert b"/ImageMask true" in pdf and b"/Width 500 /Height 500" in pdf
    breite, hoehe, bits = aw._logo_schablone()
    assert (breite, hoehe) == (500, 500) and len(bits) == 500 * ((500 + 7) // 8)
    anteil = sum(bin(b).count("0") for b in bits) / (8 * len(bits))
    assert 0.05 < anteil < 0.6  # gemalt wird das Schwarze des Logos, nicht die volle Scheibe
    assert aw.pruef_url(m).encode() not in inhalte  # der Link steht nur im QR und auf der Rückseite ohne https
    assert aw.pruef_url(m).replace("https://", "").encode() in inhalte


def test_lange_namen_werden_kleiner_statt_abgeschnitten():
    m = geprueftes_mitglied()
    m.first_name, m.last_name = "Maximiliane Josefine Antonia", "Habsburg-Lothringen-Wittelsbach"
    m.save()
    a = aw.ausweis_daten(m)
    groesse = aw._einpassen(a.name, 13, aw.SEITE_BREITE_MM - 2 * (aw.BESCHNITT_MM + 5), True, 8)
    assert 8 <= groesse < 13
    assert aw.textbreite_mm(a.name, groesse, True) <= aw.SEITE_BREITE_MM - 2 * (aw.BESCHNITT_MM + 5) or groesse == 8
    zeilen = aw._umbrechen("ein zwei drei vier fünf sechs sieben acht", 10, 25)
    assert " ".join(zeilen) == "ein zwei drei vier fünf sechs sieben acht" and len(zeilen) >= 3
    assert all(aw.textbreite_mm(z, 10) <= 25 for z in zeilen)  # keine Zeile breiter als erlaubt


# ── SVG-Vorschau ──────────────────────────────────────────────────────────────────────────


def test_die_vorschau_zeigt_beide_seiten_mit_eigenen_kennungen():
    m = geprueftes_mitglied()
    vorne, hinten = aw.ausweis_svg(m)
    for svg in (vorne, hinten):
        assert svg.startswith("<svg ") and 'viewBox="0 0 88.6 56.98"' in svg and "<script" not in svg
    assert "Anna Müller-Öhlinger" in vorne and f"{m.pk:06d}" in vorne and "MITGLIEDSAUSWEIS" in vorne
    assert 'id="ausweis-v-karte"' in vorne and 'id="ausweis-h-karte"' in hinten
    assert aw.pruef_url(m).replace("https://", "") in hinten
    assert "data:image/png;base64," in vorne  # das Logo


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
    assert "/profil/#ausweis" in brief.body
    assert audit("post")[-1] == {"typ": "post", "art": "freischaltung", "mitglied": m.pk, "anhang": True}
    assert not freischaltung_senden(m)  # einmal je Konto


def test_der_willkommensbrief_kuendigt_den_ausweis_nur_an():
    m = mitglied_anlegen("neu", tage=1, stufe=Identitaetsstufe.UNGEPRUEFT)
    m.beitritt = m.beitritt or __import__("django.utils.timezone", fromlist=["localdate"]).localdate()
    m.save()
    assert willkommen_senden(m)
    brief = mail.outbox[-1]
    assert brief.attachments == [] and "Mitgliedsausweis" in brief.body and "Kartenformat" in brief.body
    assert audit("post")[-1]["anhang"] is False


# ── Web: Download und Prüfseite ───────────────────────────────────────────────────────────


def test_den_ausweis_laedt_nur_das_eigene_gepruefte_konto(client):
    url = reverse("mitglieder:profil_ausweis")
    antwort = client.get(url)
    assert antwort.status_code == 302 and "anmelden" in antwort["Location"]
    ungeprueft = mitglied_anlegen("neu", tage=1, stufe=Identitaetsstufe.UNGEPRUEFT)
    client.force_login(ungeprueft)
    antwort = client.get(url, follow=True)
    assert antwort.redirect_chain[-1][0] == reverse("mitglieder:profil")
    assert "mit der Freischaltung" in antwort.content.decode()
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
    assert "mit der Freischaltung" in hinweis and "<svg" not in hinweis
    m = geprueftes_mitglied()
    client.force_login(m)
    html = client.get(reverse("mitglieder:profil")).content.decode()
    karte = html.split('id="ausweis"')[1].split('id="austritt"')[0]
    assert karte.count("<svg ") == 2 and reverse("mitglieder:profil_ausweis") in karte
    assert "Anna Müller-Öhlinger" in karte and "herunterladen (PDF, Kartenformat)" in karte


def test_die_pruefseite_sagt_gueltig_oder_nicht_gueltig_und_nennt_keinen_namen(client):
    m = geprueftes_mitglied()
    code = aw.ausweis_code_sicherstellen(m)
    html = client.get(f"/ausweis/{m.pk}/{code}/").content.decode()
    assert 'data-stand="gueltig"' in html and f"Nr. {m.pk:06d} ist gültig" in html
    assert "Anna" not in html and "Müller" not in html and "Identität geprüft" in html
    falsch = client.get(f"/ausweis/{m.pk}/{'0' * 10}/").content.decode()
    assert 'data-stand="ungueltig"' in falsch and "keinen gültigen Mitgliedsausweis" in falsch
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
