from django.urls import path
from rest_framework.authtoken.views import obtain_auth_token

from api.views import ArtifactListView, ArtifactUploadView, RepositoryListCreateView

urlpatterns = [
    path("auth/token/", obtain_auth_token, name="auth-token"),
    path("repositories/", RepositoryListCreateView.as_view(), name="repositories"),
    path("artifacts/", ArtifactListView.as_view(), name="artifacts"),
    path("artifacts/upload/", ArtifactUploadView.as_view(), name="artifact-upload"),
]
