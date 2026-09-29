"""Testkonten wirken nicht mit und zählen nirgends (Prüfung 0.50.0, P-7).

Die Grundgesamtheit der Anteilsschwelle kennt keine Testkonten (`stimmberechtigte_zaehlen`) — also
darf sie auch der Zähler nicht kennen, sonst rechnen Zähler und Nenner mit verschiedenen
Personenkreisen (Grundregel 6, § 5 Abs 3 lit b). Kachel und View sperren gleich. Gespeichert
bleiben die Unterstützungen, die Testkonten früher erklärt haben (Grundregel 7)."""

import pytest
from django.urls import reverse

from mitglieder.models import Mitglied
from verfahren.aehnlichkeit import aehnliche_antraege
from verfahren.archiv import archiv
from verfahren.hinweise import HINWEISE, kachel_sperre, mitwirkungssperre
from verfahren.models import Unterstuetzung, antrag_einbringen
from verfahren.test_views_aktionen import ANTRAG, mitglied_anlegen, ordnung  # noqa: F401

pytestmark = pytest.mark.django_db


def _testkonto(name: str = "probe") -> Mitglied:
    """Wie Migration 0020: aktiv, geprüft, aber Testkonto."""
    m = mitglied_anlegen(name)
    Mitglied.objects.filter(pk=m.pk).update(testkonto=True)
    return Mitglied.objects.get(pk=m.pk)


def _feld(client, name: str, url: str = "/parlament/") -> str:
    html = client.get(url).content.decode()
    return html.split(f'id="feld-{name}"')[1].split("</section>")[0]


def test_testkonto_ist_in_kachel_und_view_gleich_gesperrt(client, ordnung):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen("autorin"), **ANTRAG, ordnung=ordnung)
    probe = _testkonto()
    assert mitwirkungssperre(probe) == "testkonto"
    assert kachel_sperre("testkonto") == {"code": "testkonto", "kurz": "Testkonto", "link": None, "link_text": ""}
    client.force_login(probe)
    feld = _feld(client, "filter")
    assert f'id="u-filter-{antrag.pk}"' not in feld and 'sperre">Testkonto</span>' in feld

    antwort = client.post(
        reverse("verfahren:unterstuetzen", args=[antrag.pk]), {"weiter": "/parlament/", "feld": "filter"}
    )
    assert antwort.url == "/parlament/?hinweis=testkonto&feld=filter#feld-filter"
    assert str(HINWEISE["testkonto"]["text"]) in _feld(client, "filter", antwort.url.split("#")[0])

    # Von der Antragsseite und beim Einbringen: die 403-Seite mit dem richtigen Grund
    antwort = client.post(reverse("verfahren:unterstuetzen", args=[antrag.pk]))
    assert antwort.status_code == 403
    html = antwort.content.decode()
    assert "Testkonto — ohne Mitwirkung." in html and "ausgeschlossen" not in html
    assert client.get(reverse("verfahren:einbringen")).status_code == 403
    assert antrag.unterstuetzungen.count() == 0


def test_unterstuetzungen_von_testkonten_zaehlen_nirgends(client, ordnung):  # noqa: F811
    antrag = antrag_einbringen(mitglied_anlegen("autorin"), **ANTRAG, ordnung=ordnung)  # Schwelle 2
    antrag.unterstuetzungen.create(mitglied=mitglied_anlegen("echt"))
    antrag.unterstuetzungen.create(mitglied=_testkonto())  # vor der Stilllegung erklärt (Demo-Konten)
    antrag.fortschreiben()
    assert antrag.phase == "unterstuetzung"
    assert antrag.unterstuetzungen.count() == 2  # gespeichert bleibt sie
    assert Unterstuetzung.gueltige().filter(antrag=antrag).count() == 1
    assert client.get(reverse("verfahren:antrag", args=[antrag.pk])).context["unterstuetzungen"] == 1
    assert archiv(antrag)["antrag"]["unterstuetzungen"] == 1
    treffer = aehnliche_antraege(ANTRAG["titel"], ANTRAG["wortlaut"], None).treffer
    assert [t["beteiligung"] for t in treffer] == [1]
