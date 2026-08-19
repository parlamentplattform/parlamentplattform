"""Admin: Der Audit-Log ist strikt read-only; das Stimmregister taucht bewusst
NICHT im Admin auf (F-25) — es gibt keinen bequemen Klickpfad zum Stimmverhalten."""

from django.contrib import admin

from verfahren.models import (
    Antrag,
    AntragsFassung,
    AuditEintrag,
    Kategorie,
    Kommentar,
    Unterstuetzung,
    Verfahrensordnung,
)


class FassungInline(admin.StackedInline):
    model = AntragsFassung
    extra = 0


@admin.register(Antrag)
class AntragAdmin(admin.ModelAdmin):
    list_display = ("id", "titel", "phase", "ebene", "hervorgehoben", "phase_beginn", "eingebracht_von")
    list_filter = ("phase", "ebene", "hervorgehoben")
    inlines = [FassungInline]
    readonly_fields = ("policy_snapshot", "phase", "phase_beginn")


@admin.register(Verfahrensordnung)
class VerfahrensordnungAdmin(admin.ModelAdmin):
    list_display = ("policy_id", "version", "aktiv", "beschlossen_am")


@admin.register(Unterstuetzung)
class UnterstuetzungAdmin(admin.ModelAdmin):
    list_display = ("antrag", "mitglied", "erklaert_am")


@admin.register(AuditEintrag)
class AuditAdmin(admin.ModelAdmin):
    list_display = ("lfd", "zeit", "ereignis", "hash")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(Kommentar)
class KommentarAdmin(admin.ModelAdmin):
    list_display = ("antrag", "mitglied", "erstellt_am")


@admin.register(Kategorie)
class KategorieAdmin(admin.ModelAdmin):
    list_display = ("reihenfolge", "slug", "name", "aktiv")
    list_filter = ("aktiv",)
