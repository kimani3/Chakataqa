from django.contrib import admin

from .models import ContactMessage


@admin.register(ContactMessage)
class ContactMessageAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "organisation", "created_at")
    search_fields = ("name", "email", "organisation", "message")
    readonly_fields = ("created_at",)
