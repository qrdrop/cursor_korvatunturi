from django.contrib import admin

from repositories.models import Repository


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "type", "mode", "created_at")
    search_fields = ("name", "type", "mode")
