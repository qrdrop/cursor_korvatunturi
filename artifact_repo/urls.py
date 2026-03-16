"""URL configuration for artifact repository service."""

from django.contrib import admin
from django.shortcuts import redirect
from django.urls import include, path

from api.views import ArtifactDownloadView, PyPISimpleIndexDetailView, PyPISimpleIndexView


def _legacy_admin_create_repository_redirect(request):
    return redirect("webui-admin-create-repository")


def _legacy_admin_repository_types_redirect(request):
    return redirect("webui-admin-repository-types")


urlpatterns = [
    path(
        "admin/repositories/new/",
        _legacy_admin_create_repository_redirect,
        name="legacy-admin-create-repository",
    ),
    path(
        "admin/repository-types/",
        _legacy_admin_repository_types_redirect,
        name="legacy-admin-repository-types",
    ),
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("", include("webui.urls")),
    path("repo/<str:repository>/<path:artifact_path>", ArtifactDownloadView.as_view(), name="artifact-download"),
    path("simple/", PyPISimpleIndexView.as_view(), name="pypi-simple-index"),
    path("simple/<str:package_name>/", PyPISimpleIndexDetailView.as_view(), name="pypi-simple-index-detail"),
]
