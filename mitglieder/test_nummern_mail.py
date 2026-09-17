from importlib import import_module
from types import SimpleNamespace

import pytest
from django.apps import apps
from django.core import mail

from mitglieder.ausweis import ausweis_erstellbar
from mitglieder.mail import EmailMessage, send_mail
from mitglieder.models import Mitglied
from mitglieder.nummern import sicherstellen

pytestmark = pytest.mark.django_db


def test_bestandsnummerierung_bewahrt_ids_und_testkonten():
    test = Mitglied.objects.create(username="test", pk=2)
    michael = Mitglied.objects.create(username="michael", email="didide@ddoe.at", pk=6, ausweis_code="abc123")
    danach = Mitglied.objects.create(username="danach", pk=9)
    import_module("mitglieder.migrations.0020_nummern_bestand").bestand(
        apps, SimpleNamespace(connection=SimpleNamespace(alias="default")))
    for m in (test, michael, danach):
        m.refresh_from_db()
    assert test.pk == 2 and test.testkonto and test.mitgliedsnummer is None
    assert not ausweis_erstellbar(test)
    assert michael.pk == 6 and michael.mitgliedsnummer == 1 and michael.ausweis_code == "abc123"
    assert danach.pk == 9 and danach.mitgliedsnummer == 2
    neu = Mitglied.objects.create(username="neu")
    vor_vergabe_geladen = Mitglied.objects.get(pk=neu.pk)
    assert sicherstellen(neu) == 3
    assert sicherstellen(vor_vergabe_geladen) == 3
    assert sicherstellen(Mitglied.objects.create(username="weiter")) == 4


def test_mail_hat_text_html_eingebettetes_logo_und_unveraenderten_pdf_anhang():
    n = EmailMessage("Test", '<script>alert("x")</script>\nhttps://parlament.ddoe.at/', "plattform@ddoe.at", ["test@example.org"])
    n.attach("karte.pdf", b"%PDF-test", "application/pdf")
    mime = n.message()
    assert len(n.attachments) == 1
    teile = list(mime.walk())
    assert sum(t.get_content_type() == "image/png" for t in teile) == 1
    assert sum(t.get_content_type() == "application/pdf" for t in teile) == 1
    html = next(t.get_payload(decode=True).decode() for t in teile if t.get_content_type() == "text/html")
    assert 'src="cid:ddoe-logo"' in html and "<script>" not in html
    assert "Unterfreundorf 17" in n.body and "502117" in html
    assert "https://www.ddoe.at" in n.body
    assert send_mail("Test", "Text", "plattform@ddoe.at", ["test@example.org"]) == 1
    assert mail.outbox[-1].alternatives[0].mimetype == "text/html"


def test_testkonto_bekommt_keine_nummer_und_keine_mitgliederpost():
    from mitglieder.postausgang import beauftragen
    m = Mitglied.objects.create(username="testkonto", testkonto=True, email="test@example.org")
    assert sicherstellen(m) is None
    assert not beauftragen(m, "willkommen")
    assert mail.outbox == []
