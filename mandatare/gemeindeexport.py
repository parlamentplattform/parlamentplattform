"""Das eigene Mandat für den persönlichen JSON-Export (`mitglieder.profil.daten_export`): die Gemeindearbeit und
seit GP-089 der ganze Ordner je Mandat (`mandat_exportieren`) — mit den Vermerken und Stempeln am Mandat, den
Vertrauensfragen samt eigenen Stellungnahmen und dem Sitzungstag jedes Sammelberichts.

Was bewusst nicht im Ordner steht, nennt `EXPORT_AUSNAHMEN` mit Grund; was unter einem anderen Schlüssel als
seinem Feldnamen steht, `EXPORT_SCHLUESSEL`. `test_mandatsexport.py` prüft jedes Feld dieser App dagegen."""

from django.db.models import Prefetch

from mandatare.models import (
    Gemeindehaushaltsquelle,
    Gemeindeprojekt,
    Gemeindesitzungsquelle,
    Ratsinitiative,
    Rechenschaft,
    Sprechstunde,
    Vertrauensfrage,
)

_VERSCHACHTELT = "steht durch die Verschachtelung fest"
_KENNZIFFER = "steht als Gemeindekennziffer (gemeindekennziffer)"

#: Felder, die der Ordner eines Mandats bewusst nicht führt — je (Modell, Feld) der Grund.
EXPORT_AUSNAHMEN = {
    ("Mandat", "mitglied_id"): "das Konto selbst — der Export ist der dieses Kontos",
    ("Mandat", "foto"): "Bilddaten; foto_typ zeigt, dass ein Lichtbild hinterlegt ist — abrufbar unter /mandatare/<mandat>/foto",
    ("FreiwilligeBegruendung", "id"): "höchstens eine je Eintrag; sie steht am Eintrag",
    **{
        (modell, feld): _VERSCHACHTELT
        for modell, feld in (
            ("Aufgabe", "mandat_id"), ("Bericht", "mandat_id"), ("Rechenschaft", "mandat_id"),
            ("FreiwilligeBegruendung", "rechenschaft_id"), ("Vertrauensfrage", "mandat_id"),
            ("Stellungnahme", "vertrauensfrage_id"), ("Sitzung", "mandat_id"), ("Tagesordnungspunkt", "sitzung_id"),
            ("Livemeldung", "sitzung_id"), ("Sprechstunde", "mandat_id"), ("Ratsinitiative", "mandat_id"),
            ("Ratsmeldung", "initiative_id"), ("Gemeindehaushaltsquelle", "mandat_id"),
            ("Gemeindeprojekt", "mandat_id"), ("Gemeindeprojektstand", "projekt_id"),
        )
    },
    **{
        (modell, "gemeinde_id"): _KENNZIFFER
        for modell in (
            "Sprechstunde", "Ratsinitiative", "Gemeindesitzungsquelle", "Gemeindehaushaltsquelle", "Gemeindeprojekt",
        )
    },
}

#: Felder, die unter einem anderen Schlüssel als ihrem Namen stehen — je (Modell, Feld) der Schlüssel.
EXPORT_SCHLUESSEL = {
    ("Mandat", "id"): "mandat",
    ("Mandat", "gemeinde_id"): "gemeindekennziffer",
    ("Aufgabe", "id"): "aufgabe",
    ("Bericht", "id"): "bericht",
    ("Rechenschaft", "id"): "rechenschaft",
    ("FreiwilligeBegruendung", "text"): "freiwillige_begruendung",
    ("FreiwilligeBegruendung", "eingetragen_am"): "freiwillige_begruendung_am",
    ("Vertrauensfrage", "id"): "vertrauensfrage",
    ("Stellungnahme", "id"): "stellungnahme",
    ("Sitzung", "id"): "sitzung",
    ("Tagesordnungspunkt", "id"): "punkt",
    ("Livemeldung", "id"): "meldung",
    ("Sprechstunde", "id"): "sprechstunde",
    ("Ratsinitiative", "id"): "initiative",
    ("Ratsmeldung", "id"): "meldung",
    ("Gemeindesitzungsquelle", "id"): "quelle",
    ("Gemeindehaushaltsquelle", "id"): "quelle",
    ("Gemeindeprojekt", "id"): "projekt",
    ("Gemeindeprojektstand", "id"): "stand",
}


def mandate_fuer_export(mitglied):
    return mitglied.mandate.select_related("gemeinde").defer("foto").prefetch_related(
        Prefetch("sprechstunden", queryset=Sprechstunde.objects.select_related("gemeinde").order_by("pk")),
        Prefetch("ratsinitiativen", queryset=Ratsinitiative.objects.select_related("gemeinde").order_by("pk")),
        "ratsinitiativen__meldungen",
        Prefetch(
            "aufgaben__gemeindesitzungsquellen",
            queryset=Gemeindesitzungsquelle.objects.select_related("gemeinde").order_by("pk"),
        ),
        Prefetch("haushaltsquellen", queryset=Gemeindehaushaltsquelle.objects.select_related("gemeinde").order_by("pk")),
        Prefetch("gemeindeprojekte", queryset=Gemeindeprojekt.objects.select_related("gemeinde").order_by("pk")),
        "gemeindeprojekte__staende",
        "berichte",
        Prefetch("rechenschaft", queryset=Rechenschaft.objects.select_related("freiwillige_begruendung")),
        "sitzungen__punkte",
        "sitzungen__meldungen",
        Prefetch("vertrauensfragen", queryset=Vertrauensfrage.objects.select_related("antrag").order_by("pk")),
        "vertrauensfragen__stellungnahmen",
        "vertrauensfragen__anlaesse",
    )


def mandat_exportieren(md) -> dict:
    """Der Ordner eines eigenen Mandats (GP-089): Angaben, Vermerke und Stempel am Mandat (§ 7 Abs 3, Abs 10
    lit f und h), Gemeindearbeit, Aufgaben, Berichte mit ihrem Sitzungstag, Rechenschaft, Sitzungen im
    Live-Modus und die Vertrauensfragen samt eigenen Stellungnahmen. Die Schlüssel bis 0.114.0 bleiben, wie
    sie waren; dazu kommen die bis dahin fehlenden Felder. Am besten mit `mandate_fuer_export` geladen."""
    return {
        "mandat": md.pk,
        "bezeichnung": md.bezeichnung,
        "ebene": md.ebene,
        "gebiet": md.gebiet,
        "angetreten": md.angetreten,
        "beendet": md.beendet,
        "vorstellung": md.vorstellung,
        "kandidatur": md.kandidatur_id,
        "foto_typ": md.foto_typ,
        "vertrauen_entzogen_am": md.vertrauen_entzogen_am,
        "rueckgabe_ersucht_bis": md.rueckgabe_ersucht_bis,
        "rueckgabezusage": md.rueckgabezusage,
        "rueckgabezusage_am": md.rueckgabezusage_am,
        "mandatsvereinbarung_lit_h_am": md.mandatsvereinbarung_lit_h_am,
        "mandatsvereinbarung_endet_am": md.mandatsvereinbarung_endet_am,
        "vertretung_beendet_am": md.vertretung_beendet_am,
        "bestaetigt_am": md.bestaetigt_am,
        "gemeindearbeit": gemeindearbeit_exportieren(md),
        "aufgaben": [
            {
                "aufgabe": a.pk,
                "titel": a.titel,
                "beschreibung": a.beschreibung,
                "frist": a.frist,
                "sitzungstag": a.sitzungstag,
                "status": a.status,
                "antrag": a.antrag_id,
                "erstellt_am": a.erstellt_am,
                "aktualisiert_am": a.aktualisiert_am,
            }
            for a in md.aufgaben.all()
        ],
        "berichte": [
            {
                "bericht": b.pk,
                "art": b.art,
                "monat": b.monat,
                "aufgabe": b.aufgabe_id,  # der Sitzungstag eines Sammelberichts
                "text": b.text,
                "eingereicht_am": b.eingereicht_am,
            }
            for b in md.berichte.all()
        ],
        "rechenschaft": [_rechenschaft_exportieren(r) for r in md.rechenschaft.all()],
        # FB-L5: die Sitzungen im Live-Modus mit Tagesordnung und Meldungen
        "sitzungen": [
            {
                "sitzung": s.pk,
                "aufgabe": s.aufgabe_id,
                "beginn": s.beginn,
                "ende": s.ende,
                "ende_durch_hoechstdauer": s.ende_durch_hoechstdauer,
                "stream": s.stream,
                "punkte": [
                    {"punkt": p.pk, "nummer": p.nummer, "titel": p.titel, "antrag": p.antrag_id, "erstellt_am": p.erstellt_am}
                    for p in s.punkte.all()
                ],
                "meldungen": [
                    {"meldung": x.pk, "zeitpunkt": x.zeitpunkt, "punkt": x.punkt_id, "text": x.text,
                     "stimme": x.stimme, "abgestimmt": x.abgestimmt, "berichtigt": x.berichtigt_id}
                    for x in s.meldungen.all()
                ],
            }
            for s in md.sitzungen.all()
        ],
        "vertrauensfragen": [_vertrauensfrage_exportieren(vf) for vf in md.vertrauensfragen.all()],
    }


def _rechenschaft_exportieren(r) -> dict:
    freiwillig = r.freiwillige
    return {
        "rechenschaft": r.pk,
        "aufgabe": r.aufgabe_id,
        "antrag": r.antrag_id,
        "gegenstand": r.gegenstand,
        "sitzung_am": r.sitzung_am,
        "beschluss_plattform": r.beschluss_plattform,
        "stimme": r.stimme,
        "begruendung": r.begruendung,
        "eingetragen_am": r.eingetragen_am,
        "punkt": r.punkt_id,
        "nachgetragen_am": r.nachgetragen_am,
        "quelle": r.quelle,
        "freiwillige_begruendung": freiwillig.text if freiwillig else None,
        "freiwillige_begruendung_am": freiwillig.eingetragen_am if freiwillig else None,
    }


def _vertrauensfrage_exportieren(vf) -> dict:
    """Eine Vertrauensfrage oder ein Bestätigungsantrag zum eigenen Mandat (§ 7 Abs 10): Anlässe, Zahlen des
    Einbringungstags, Sperrhinweis, Vermerke des Rechtsschutzes, Zeitpunkte der Wirkungen, eigene Stellungnahmen."""
    return {
        "vertrauensfrage": vf.pk,
        "antrag": vf.antrag_id,
        "phase": vf.antrag.phase,
        "art": vf.art,
        "anlaesse": sorted(r.pk for r in vf.anlaesse.all()),
        "anlass_ausstaende": vf.anlass_ausstaende,
        "stimmberechtigte_partei_am_einbringungstag": vf.stimmberechtigte_partei_am_einbringungstag,
        "schwelle_partei": vf.schwelle_partei,
        "schwelle_erreicht_am": vf.schwelle_erreicht_am,
        "sperrhinweis": vf.sperrhinweis,
        "sperre_beschluss": vf.sperre_beschluss_id,
        "angefochten_am": vf.angefochten_am,
        "aktenkennung": vf.aktenkennung,
        "entscheidung": vf.entscheidung,
        "entschieden_am": vf.entschieden_am,
        "wirkungen_ab": vf.wirkungen_ab,
        "wirkungen_endgueltig_am": vf.wirkungen_endgueltig_am,
        "verstaendigt_am": vf.verstaendigt_am,
        "ergebnis_veroeffentlicht_am": vf.ergebnis_veroeffentlicht_am,
        "stellungnahmen": [
            {"stellungnahme": s.pk, "text": s.text, "erstellt_am": s.erstellt_am} for s in vf.stellungnahmen.all()
        ],
    }


def gemeindearbeit_exportieren(mandat):
    """Zuordnung und Verlauf einschließlich früherer Stände des eigenen Mandats."""
    return {
        "gemeindekennziffer": mandat.gemeinde.kennziffer if mandat.gemeinde_id else None,
        "sprechstunden": [
            {
                "sprechstunde": s.pk, "gemeindekennziffer": s.gemeinde.kennziffer,
                "beginn": s.beginn, "ende": s.ende, "treffpunkt": s.treffpunkt,
                "veroeffentlicht_am": s.veroeffentlicht_am, "abgesagt_am": s.abgesagt_am,
            }
            for s in mandat.sprechstunden.all()
        ],
        "ratsinitiativen": [
            {
                "initiative": i.pk, "gemeindekennziffer": i.gemeinde.kennziffer,
                "art": i.art, "titel": i.titel, "text": i.text, "veroeffentlicht_am": i.veroeffentlicht_am,
                "meldungen": [
                    {
                        "meldung": m.pk, "art": m.art, "datum": m.datum, "text": m.text,
                        "quellen_url": m.quellen_url, "eingetragen_am": m.eingetragen_am,
                    }
                    for m in i.meldungen.all()
                ],
            }
            for i in mandat.ratsinitiativen.all()
        ],
        "sitzungsquellen": [
            {
                "quelle": q.pk, "aufgabe": a.pk, "gemeindekennziffer": q.gemeinde.kennziffer,
                "sitzung_am": q.sitzung_am, "art": q.art, "url": q.url, "erfasst_am": q.erfasst_am,
            }
            for a in mandat.aufgaben.all()
            for q in a.gemeindesitzungsquellen.all()
        ],
        "haushaltsquellen": [
            {
                "quelle": q.pk, "gemeindekennziffer": q.gemeinde.kennziffer,
                "jahr": q.jahr, "bis_jahr": q.bis_jahr, "art": q.art, "url": q.url, "erfasst_am": q.erfasst_am,
            }
            for q in mandat.haushaltsquellen.all()
        ],
        "projekte": [
            {
                "projekt": p.pk, "gemeindekennziffer": p.gemeinde.kennziffer, "veroeffentlicht_am": p.veroeffentlicht_am,
                "staende": [
                    {
                        "stand": s.pk, "lage": s.lage, "titel": s.titel, "vermerk": s.vermerk,
                        "quelle": s.quelle, "stand_am": s.stand_am, "erfasst_am": s.erfasst_am,
                    }
                    for s in p.staende.all()
                ],
            }
            for p in mandat.gemeindeprojekte.all()
        ],
    }
