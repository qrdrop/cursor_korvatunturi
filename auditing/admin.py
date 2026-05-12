from django.contrib import admin

from auditing.models import AuditEvent


@admin.register(AuditEvent)
class AuditEventAdmin(admin.ModelAdmin):
    list_display = ("id", "action", "actor", "repository", "artifact_id", "created_at")
    list_filter = ("action", "repository")
    search_fields = ("action", "payload")
