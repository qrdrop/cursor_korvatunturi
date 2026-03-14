"""URL configuration for artifact repository service."""

from django.contrib import admin
from django.urls import include, path

from api.views import ArtifactDownloadView, PyPISimpleIndexDetailView, PyPISimpleIndexView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("api.urls")),
    path("repo/<str:repository>/<path:artifact_path>", ArtifactDownloadView.as_view(), name="artifact-download"),
    path("simple/", PyPISimpleIndexView.as_view(), name="pypi-simple-index"),
    path("simple/<str:package_name>/", PyPISimpleIndexDetailView.as_view(), name="pypi-simple-index-detail"),
]
