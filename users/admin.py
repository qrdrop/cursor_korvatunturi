from django.contrib import admin

from users.models import UserRole


@admin.register(UserRole)
class UserRoleAdmin(admin.ModelAdmin):
    list_display = ("id", "user", "repository", "role")
    list_filter = ("role", "repository")
    search_fields = ("user__username", "repository__name")
