from django.contrib import admin

from artifacts.models import Artifact, DownloadLog, PackageMetadata


@admin.register(Artifact)
class ArtifactAdmin(admin.ModelAdmin):
    list_display = ("id", "repository", "name", "version", "architecture", "uploaded_at", "is_cached")
    list_filter = ("repository", "is_cached")
    search_fields = ("name", "path", "checksum")


@admin.register(PackageMetadata)
class PackageMetadataAdmin(admin.ModelAdmin):
    list_display = ("id", "artifact", "package_name", "version", "architecture")
    search_fields = ("package_name", "version")


@admin.register(DownloadLog)
class DownloadLogAdmin(admin.ModelAdmin):
    list_display = ("id", "artifact", "user", "timestamp", "ip_address")
    list_filter = ("timestamp",)
