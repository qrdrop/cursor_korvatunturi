from django.contrib import admin

from repositories.models import Repository, RepositoryTypePolicy


@admin.register(Repository)
class RepositoryAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "type", "mode", "created_at")
    search_fields = ("name", "type", "mode")


@admin.register(RepositoryTypePolicy)
class RepositoryTypePolicyAdmin(admin.ModelAdmin):
    list_display = ("id", "allow_deb", "allow_rpm", "allow_pypi", "allow_msi", "allow_generic", "updated_at")

    def has_add_permission(self, request):
        return not RepositoryTypePolicy.objects.exists()
