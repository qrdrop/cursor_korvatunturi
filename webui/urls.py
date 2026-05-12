from django.contrib.auth import views as auth_views
from django.urls import path

from webui.views import (
    AdminCreateRepositoryView,
    AdminRepositoryTypePolicyView,
    DashboardView,
    HomeRedirectView,
    PackageBrowseView,
    RepositoryDetailView,
    UploadArtifactView,
)

urlpatterns = [
    path("", HomeRedirectView.as_view(), name="webui-home"),
    path("login/", auth_views.LoginView.as_view(template_name="webui/login.html"), name="webui-login"),
    path("logout/", auth_views.LogoutView.as_view(next_page="webui-login"), name="webui-logout"),
    path("dashboard/", DashboardView.as_view(), name="webui-dashboard"),
    path("packages/", PackageBrowseView.as_view(), name="webui-packages"),
    path("repositories/<str:name>/", RepositoryDetailView.as_view(), name="webui-repository-detail"),
    path("upload/", UploadArtifactView.as_view(), name="webui-upload"),
    path("manage/repositories/new/", AdminCreateRepositoryView.as_view(), name="webui-admin-create-repository"),
    path(
        "manage/repository-types/",
        AdminRepositoryTypePolicyView.as_view(),
        name="webui-admin-repository-types",
    ),
]
