"""Gemeinsames Formularfeld für Links auf öffentliche Unterlagen."""

from urllib.parse import urlsplit

from django import forms
from django.core.validators import URLValidator
from django.utils.translation import gettext as _
from django.utils.translation import gettext_lazy

from mandatare.models import QUELLEN_URL_MAX


def _oeffentliche_url_pruefen(url):
    URLValidator(schemes=["https"])(url)
    teile = urlsplit(url)
    if teile.username is not None or teile.password is not None or "\\" in url:
        raise forms.ValidationError(_("Der Link darf keine Zugangsdaten oder Rückstriche enthalten."))


def quellen_url_feld():
    return forms.CharField(
        label=gettext_lazy("Öffentlicher HTTPS-Link"),
        required=False,
        max_length=QUELLEN_URL_MAX,
        validators=[_oeffentliche_url_pruefen],
        widget=forms.URLInput,
    )
