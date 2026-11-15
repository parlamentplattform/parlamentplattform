"""Öffentliche Quellen-Nachlese; ausschließlich lesende GET-Ansichten."""

import json

from django.core.paginator import Paginator
from django.db.models import Count, Exists, OuterRef
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_safe

from faktenbasis.models import (
    Kundmachungsnachweis,
    Norm,
    NormText,
    PersonalAbruf,
    PersonalAggregat,
    PersonalRessortAbruf,
    PersonalRessorttabelle,
    RisAenderungsseite,
    RisImport,
    VfghEntscheidungsstand,
)
from faktenbasis.verwaltung import darf_aktualisieren
from parameter.models import zahl
from plattform_core.novellenfundstelle import VERSION as NOVELLENFASSUNG
from plattform_core.novellenfundstelle import novellenfundstelle


@require_safe
def index(request):
    normen = Norm.objects.select_related("importlauf").annotate(
        hat_text=Exists(NormText.objects.filter(norm_id=OuterRef("pk"))),
    )
    seiten = Paginator(normen, max(1, min(100, zahl("faktenbasis-seitengroesse", 20))))
    return render(request, "faktenbasis/index.html", {
        "seite": seiten.get_page(request.GET.get("seite")),
        "umfang": Norm.objects.aggregate(schnappschuesse=Count("pk"), dokumente=Count("ris_id", distinct=True)),
        "letzter": RisImport.objects.first(),
        "erfolg": RisImport.objects.filter(erfolgreich=True).first(),
        "darf_aktualisieren": darf_aktualisieren(request.user),
    })


def _texte_des_dokuments(norm):
    return NormText.objects.filter(
        norm__ris_id=norm.ris_id, norm__ebene=norm.ebene,
        norm__gesetzesnummer=norm.gesetzesnummer, norm__bundesland=norm.bundesland,
    )


@require_safe
def norm(request, pk):
    eintrag = get_object_or_404(Norm.objects.select_related("importlauf"), pk=pk)
    novelle = None
    if (eintrag.ebene == "Bund" and not eintrag.bundesland) or (eintrag.ebene == "Land" and eintrag.bundesland):
        novelle = novellenfundstelle(eintrag.rohdaten, eintrag.ris_id, eintrag.stand, bundesland=eintrag.bundesland)
    kundmachung = None
    if novelle:
        kundmachung = Kundmachungsnachweis.objects.filter(norm=eintrag).defer("original").first()
    return render(request, "faktenbasis/norm.html", {
        "norm": eintrag,
        "novelle": novelle,
        "kundmachung": kundmachung,
        "novellenfassung": NOVELLENFASSUNG,
        "fassungen": Norm.objects.filter(ris_id=eintrag.ris_id).order_by("-stand", "-pk"),
        "rohdaten": json.dumps(eintrag.rohdaten, ensure_ascii=False, indent=2),
        "texte": eintrag.texte.defer("xml"),
        "textvergleich_moeglich": _texte_des_dokuments(eintrag).order_by("pk")[1:2].exists(),
        "letzter_textabruf": eintrag.textabrufe.first(),
        "textabrufe": eintrag.textabrufe.select_related("inhalt").all(),
        "darf_aktualisieren": darf_aktualisieren(request.user),
    })


@require_safe
def aenderungen(request):
    staende = RisAenderungsseite.objects.defer("original")
    seiten = Paginator(staende, max(1, min(100, zahl("faktenbasis-seitengroesse", 20))))
    return render(request, "faktenbasis/aenderungen.html", {
        "seite": seiten.get_page(request.GET.get("seite")),
    })


@require_safe
def vfgh(request):
    staende = VfghEntscheidungsstand.objects.only("dokumentnummer", "entschieden_am", "ecli", "geschaeftszahlen")
    seiten = Paginator(staende, max(1, min(100, zahl("faktenbasis-seitengroesse", 20))))
    return render(request, "faktenbasis/vfgh.html", {"seite": seiten.get_page(request.GET.get("seite"))})


@require_safe
def vfgh_detail(request, pk):
    stand = get_object_or_404(VfghEntscheidungsstand.objects.defer("original"), pk=pk)
    return render(request, "faktenbasis/vfgh_detail.html", {"stand": stand})


@require_safe
def kundmachung(request, pk):
    beleg = get_object_or_404(
        Kundmachungsnachweis.objects.only("dokumentnummer", "kundgemacht_am", "eli"), pk=pk,
    )
    normen = Norm.objects.filter(
        kundmachungsnachweis__dokumentnummer=beleg.dokumentnummer,
        kundmachungsnachweis__kundgemacht_am=beleg.kundgemacht_am,
    ).values(
        "pk", "kurztitel", "ris_id", "stand",
        "kundmachungsnachweis__original_sha256", "kundmachungsnachweis__parser_fassung",
    )
    seiten = Paginator(normen, max(1, min(100, zahl("faktenbasis-seitengroesse", 20))))
    return render(request, "faktenbasis/kundmachung.html", {
        "beleg": beleg, "seite": seiten.get_page(request.GET.get("seite")),
    })


@require_safe
def textvergleich(request, pk, mit=None):
    basis = get_object_or_404(
        NormText.objects.select_related("norm").defer("xml", "norm__rohdaten"), pk=pk,
    )
    moegliche_texte = _texte_des_dokuments(basis.norm).exclude(pk=basis.pk)
    vergleich = None
    texte = ()
    if mit is not None:
        vergleich = get_object_or_404(
            moegliche_texte.select_related("norm").defer("xml", "norm__rohdaten"), pk=mit,
        )
        texte = (basis, vergleich)
    seiten = Paginator(
        moegliche_texte.values("pk", "erfasst_am", "xml_hash", "parser_fassung", "norm__stand"),
        max(1, min(100, zahl("faktenbasis-seitengroesse", 20))),
    )
    return render(request, "faktenbasis/textvergleich.html", {
        "basis": basis, "vergleich": vergleich, "texte": texte,
        "seite": seiten.get_page(request.GET.get("seite")),
        "wortlaut_gleich": vergleich is not None and basis.text == vergleich.text,
        "pruefsumme_gleich": vergleich is not None and basis.xml_hash == vergleich.xml_hash,
    })


@require_safe
def importantwort(request, pk):
    lauf = get_object_or_404(RisImport, pk=pk, erfolgreich=True)
    antwort = JsonResponse(lauf.antwort, json_dumps_params={"ensure_ascii": False, "indent": 2})
    antwort["Content-Disposition"] = f'attachment; filename="ris-import-{lauf.pk}.json"'
    return antwort


@require_safe
def textxml(request, pk):
    inhalt = get_object_or_404(NormText.objects.select_related("norm"), pk=pk)
    antwort = HttpResponse(bytes(inhalt.xml), content_type="application/xml; charset=utf-8")
    antwort["Content-Disposition"] = f'attachment; filename="ris-dokument-{inhalt.pk}.xml"'
    antwort["X-Content-Type-Options"] = "nosniff"
    return antwort


@require_safe
def personal(request):
    seiten = Paginator(PersonalAggregat.objects.all(), max(1, min(100, zahl("faktenbasis-seitengroesse", 20))))
    return render(request, "faktenbasis/personal.html", {
        "seite": seiten.get_page(request.GET.get("seite")), "letzter": PersonalAbruf.objects.first(),
    })


@require_safe
def personal_detail(request, pk):
    a = get_object_or_404(PersonalAggregat, pk=pk)
    abrufe = Paginator(a.abrufe.all(), max(1, min(100, zahl("faktenbasis-seitengroesse", 20))))
    return render(request, "faktenbasis/personal_detail.html", {"aggregat": a, "abrufe": abrufe.get_page(request.GET.get("seite"))})


@require_safe
def personal_nachweis(request, pk):
    a = get_object_or_404(PersonalAggregat, pk=pk)
    daten = {k: getattr(a, k) for k in ("id", "datenjahr", "bereich", "einheit", "beamte", "vertragliches_personal",
        "gesamt", "quelle", "publikation", "seite", "tabelle", "original_sha256", "parser_fassung")}
    daten["erfasst_am"] = a.erfasst_am.isoformat()
    antwort = JsonResponse(daten, json_dumps_params={"ensure_ascii": False, "indent": 2})
    antwort["Content-Disposition"] = f'attachment; filename="personal-aggregat-{a.pk}.json"'
    antwort["X-Content-Type-Options"] = "nosniff"
    return antwort


@require_safe
def personal_ressorts(request):
    seiten = Paginator(PersonalRessorttabelle.objects.all(), max(1, min(100, zahl("faktenbasis-seitengroesse", 20))))
    return render(request, "faktenbasis/ressorts.html", {
        "seite": seiten.get_page(request.GET.get("seite")), "letzter": PersonalRessortAbruf.objects.first(),
    })


@require_safe
def personal_ressorts_detail(request, pk):
    t = get_object_or_404(PersonalRessorttabelle, pk=pk)
    abrufe = Paginator(t.abrufe.all(), max(1, min(100, zahl("faktenbasis-seitengroesse", 20))))
    return render(request, "faktenbasis/ressorttabelle.html", {
        "tabelle": t, "abrufe": abrufe.get_page(request.GET.get("seite")),
    })


@require_safe
def personal_ressorts_nachweis(request, pk):
    t = get_object_or_404(PersonalRessorttabelle, pk=pk)
    daten = {k: getattr(t, k) for k in ("id", "datenjahr", "einheit", "ressorts", "gesamt", "quelle",
        "publikation", "seite", "methodik_seite", "tabelle", "original_sha256", "parser_fassung")}
    daten["stichtag"] = t.stichtag.isoformat()
    daten["erfasst_am"] = t.erfasst_am.isoformat()
    antwort = JsonResponse(daten, json_dumps_params={"ensure_ascii": False, "indent": 2})
    antwort["Content-Disposition"] = f'attachment; filename="personal-ressorts-{t.pk}.json"'
    antwort["X-Content-Type-Options"] = "nosniff"
    return antwort
