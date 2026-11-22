"""GP-129: Jeder Audit-Eintrag steht mit der schreibenden Handlung in einer Transaktion — oder
die Ausnahme ist begründet, oder die Fassung ist bei der zuständigen App gemeldet.

Die Prüfung liegt in `tools/audit_klammer.py` (rein lexikalisch, führt nichts aus)."""

from __future__ import annotations

import textwrap

from tools import audit_klammer


def test_keine_audit_stelle_bleibt_ungeklaert():
    offen = [f"{s.datei}:{s.zeile} {s.funktion}" for s in audit_klammer.stellen() if s.einstufung == "offen"]
    assert offen == []


def test_jede_begruendung_ist_ein_ganzer_satz():
    for schluessel, grund in audit_klammer.BEGRUENDET.items():
        assert ":" in schluessel
        assert len(grund) > 30 and grund.endswith("."), schluessel


def test_jede_gemeldete_stelle_nennt_ihr_paket():
    for schluessel, paket in audit_klammer.ZU_FASSEN.items():
        assert ":" in schluessel
        assert paket.split()[0] in {"gremien", "mandatare", "mitglieder", "siegel", "oberflaeche", "ki-faktenbasis"}


def test_register_uebersicht_und_anstoss_sind_selbst_gefasst():
    eigene = [
        s for s in audit_klammer.stellen() if s.datei.split("/")[0] in {"parameter", "uebersicht", "anstoss", "plattform_core"}
    ]
    assert eigene, "die Registerverwaltung schreibt Audit-Einträge"
    assert {s.einstufung for s in eigene} <= {"atomic", "aufrufer", "begruendet"}


def _baum(tmp_path, quelltext: str):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "ansichten.py").write_text(textwrap.dedent(quelltext), encoding="utf-8")
    return {s.funktion: s.einstufung for s in audit_klammer.stellen(tmp_path)}


def test_die_einstufung_erkennt_klammer_dekorator_aufrufer_und_luecke(tmp_path):
    einstufung = _baum(
        tmp_path,
        """
        from django.db import transaction

        @transaction.atomic
        def dekoriert():
            AuditEintrag.anhaengen({})

        def geklammert():
            with transaction.atomic():
                AuditEintrag.anhaengen({})

        def helfer():
            AuditEintrag.anhaengen({})

        def ansicht():
            with transaction.atomic():
                helfer()

        def luecke():
            AuditEintrag.anhaengen({})

        class Modell:
            def methode(self):
                AuditEintrag.anhaengen({})

            def aufrufer(self):
                with transaction.atomic():
                    self.methode()
        """,
    )
    assert einstufung == {
        "dekoriert": "atomic",
        "geklammert": "atomic",
        "helfer": "aufrufer",
        "luecke": "offen",
        "Modell.methode": "aufrufer",
    }


def test_ein_ungefasster_aufrufer_nimmt_dem_helfer_die_klammer(tmp_path):
    einstufung = _baum(
        tmp_path,
        """
        from django.db import transaction

        def helfer():
            AuditEintrag.anhaengen({})

        def gefasst():
            with transaction.atomic():
                helfer()

        def ungefasst():
            helfer()
        """,
    )
    assert einstufung == {"helfer": "offen"}


def test_tests_zaehlen_weder_als_stelle_noch_als_aufrufer(tmp_path):
    (tmp_path / "app").mkdir()
    (tmp_path / "app" / "test_x.py").write_text("def t():\n    AuditEintrag.anhaengen({})\n", encoding="utf-8")
    assert audit_klammer.stellen(tmp_path) == []
