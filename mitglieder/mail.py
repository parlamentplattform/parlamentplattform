"""Gemeinsame Mailfußzeile: Textalternative und HTML mit eingebettetem Logo."""
from email.mime.image import MIMEImage
from pathlib import Path

from django.core.mail import EmailMultiAlternatives, get_connection
from django.core.mail.message import SafeMIMEMultipart
from django.template.loader import render_to_string
from django.utils.html import escape, linebreaks, urlize

LOGO = Path(__file__).parent / "static" / "mitglieder" / "ddoe-logo.png"
KONTAKT = "Direkte Demokratie Österreich\nplattform@ddoe.at\nhttps://www.ddoe.at\nUnterfreundorf 17, 4076 Unterfreundorf, Austria\nParteienregisterzahl: 502117"


class EmailMessage(EmailMultiAlternatives):
    def __init__(self, subject="", body="", from_email=None, to=None, **kwargs):
        super().__init__(subject, body.rstrip() + "\n\n—\n" + KONTAKT + "\n", from_email, to, **kwargs)
        html = render_to_string("mitglieder/post/brief.html", {
            "inhalt": linebreaks(urlize(escape(body))),
        })
        self.attach_alternative(html, "text/html")

    def message(self):
        message = super().message()
        # Das Logo gehört zur HTML-Alternative, nicht zur PDF-Anhangsliste.
        for teil in message.walk():
            if teil.get_content_type() == "multipart/alternative":
                payload = teil.get_payload()
                for i, kind in enumerate(payload):
                    if kind.get_content_type() == "text/html":
                        related = SafeMIMEMultipart(_subtype="related", encoding=self.encoding or "utf-8")
                        related.attach(kind)
                        logo = MIMEImage(LOGO.read_bytes(), _subtype="png")
                        logo.add_header("Content-ID", "<ddoe-logo>")
                        logo.add_header("Content-Disposition", "inline", filename="ddoe-logo.png")
                        related.attach(logo)
                        payload[i] = related
                break
        return message


def send_mail(subject, message, from_email, recipient_list, fail_silently=False,
              auth_user=None, auth_password=None, connection=None, html_message=None):
    connection = connection or get_connection(username=auth_user, password=auth_password,
                                              fail_silently=fail_silently)
    return EmailMessage(subject, message, from_email, recipient_list, connection=connection).send(
        fail_silently=fail_silently)
