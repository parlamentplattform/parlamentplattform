"""Die Live-Vorschau des WeicherFilters (FB-B2) zeigt dieselben Zeilen wie das Parlament."""

import re

import pytest
from django.urls import reverse

from verfahren.models import Favorit, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def test_gp072_vorschau_zeigt_den_gemerkten_stern(client, ordnung):  # noqa: F811
    """GP-072 (OCR-08): Die Vorschau kannte die Favoriten nicht — der Stern stand leer, und sein
    Klick entfernte den Favoriten, statt ihn zu setzen."""
    ich = mitglied_anlegen('ich')
    antrag = antrag_einbringen(mitglied_anlegen('autor'), **ANTRAG, ordnung=ordnung)
    Favorit.objects.create(antrag=antrag, mitglied=ich)
    client.force_login(ich)
    liste = client.post(reverse('verfahren:filter_vorschau'), {}, HTTP_HX_REQUEST='true').content.decode()
    form = re.search(
        r'action="{}".*?</form>'.format(re.escape(reverse('verfahren:favorisieren', args=[antrag.pk]))), liste, re.S
    )
    assert form is not None
    assert 'aria-pressed="true"' in form.group(0)
