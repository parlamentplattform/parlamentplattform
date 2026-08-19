from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from mitglieder.models import Mitglied


@admin.register(Mitglied)
class MitgliedAdmin(UserAdmin):
    list_display = ("username", "anzeigename", "beitritt", "identitaetsstufe", "is_active")
    list_filter = ("identitaetsstufe", "is_active")
    fieldsets = UserAdmin.fieldsets + (
        ("Mitgliedschaft", {"fields": ("beitritt", "identitaetsstufe", "pseudonym_oeffentlich")}),
    )
