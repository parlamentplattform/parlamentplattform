"""Eine neuere Datei ersetzt keinen ausdrücklich verlangten älteren Auftragstext."""

import pytest

from ki import auftraege


@pytest.fixture
def auftragsdateien(tmp_path, monkeypatch):
    monkeypatch.setattr(auftraege, "ORDNER", tmp_path)
    for nummer, inhalt in [(1, "Erster unveränderter Auftrag."), (3, "Neuer Auftrag mit anderer Eingabe.")]:
        (tmp_path / f"rechtsbezug-v{nummer}.md").write_text(inhalt, encoding="utf-8")
    return tmp_path


def test_ausdruecklich_alte_fassung_bleibt_trotz_neuerer_datei_erhalten(auftragsdateien):
    alt = auftraege.auftrag_laden("rechtsbezug", nummer=1)
    assert alt.text == "Erster unveränderter Auftrag." and alt.version == "rechtsbezug-v1"
    assert auftraege.auftrag_laden("rechtsbezug").version == "rechtsbezug-v3"
    assert auftraege.auftrag_laden("rechtsbezug", nummer=3).version == "rechtsbezug-v3"
    assert [a.nummer for a in auftraege.auftragsversionen()] == [1, 3]


def test_fehlende_nummer_faellt_nicht_auf_andere_fassung_zurueck(auftragsdateien):
    with pytest.raises(KeyError):
        auftraege.auftrag_laden("rechtsbezug", nummer=2)
    with pytest.raises(KeyError):
        auftraege.auftrag_laden("fremderzweck", nummer=1)


@pytest.mark.parametrize("nummer", [True, False, 0, -1, "1", 1.5])
def test_ungueltige_nummer_wird_nicht_zum_auftrag(auftragsdateien, nummer):
    with pytest.raises(ValueError):
        auftraege.auftrag_laden("rechtsbezug", nummer=nummer)
