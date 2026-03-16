from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import Http404
from django.shortcuts import redirect
from django.views.generic import FormView, TemplateView

from artifacts.models import Artifact
from artifacts.services import process_artifact_upload
from auditing.services import log_audit_event
from repositories.models import Repository, RepositoryTypePolicy
from users.models import UserRole
from users.permissions import can_read, can_write
from webui.forms import ArtifactUploadForm, RepositoryCreateForm, RepositoryTypePolicyForm


def repositories_for_user(user):
    if user.is_superuser:
        return Repository.objects.all()
    return Repository.objects.filter(user_roles__user=user).distinct()


class HomeRedirectView(LoginRequiredMixin, TemplateView):
    template_name = "webui/home.html"

    def get(self, request, *args, **kwargs):
        return redirect("webui-dashboard")


class DashboardView(LoginRequiredMixin, TemplateView):
    template_name = "webui/dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        repos = repositories_for_user(self.request.user)
        context["repositories"] = repos.order_by("name")
        context["artifact_count"] = Artifact.objects.filter(repository__in=repos).count()
        return context


class PackageBrowseView(LoginRequiredMixin, TemplateView):
    template_name = "webui/package_browse.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        repos = repositories_for_user(self.request.user)
        repo_id = self.request.GET.get("repo")
        query = self.request.GET.get("q", "").strip()

        artifacts = Artifact.objects.filter(repository__in=repos).select_related("repository", "package_metadata")
        if repo_id:
            artifacts = artifacts.filter(repository_id=repo_id)
        if query:
            artifacts = artifacts.filter(name__icontains=query)

        context["artifacts"] = artifacts.order_by("-uploaded_at")[:500]
        context["repositories"] = repos.order_by("name")
        context["query"] = query
        context["repo_id"] = repo_id
        return context


class RepositoryDetailView(LoginRequiredMixin, TemplateView):
    template_name = "webui/repository_detail.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        repository = Repository.objects.filter(name=self.kwargs["name"]).first()
        if not repository or not can_read(self.request.user, repository):
            raise Http404("Repository not found")
        context["repository"] = repository
        context["artifacts"] = (
            Artifact.objects.filter(repository=repository)
            .select_related("package_metadata", "uploaded_by")
            .order_by("-uploaded_at")
        )
        return context


class UploadArtifactView(LoginRequiredMixin, FormView):
    template_name = "webui/upload_artifact.html"
    form_class = ArtifactUploadForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        writable_repos = [repo.id for repo in repositories_for_user(self.request.user) if can_write(self.request.user, repo)]
        kwargs["repository_queryset"] = Repository.objects.filter(id__in=writable_repos).order_by("name")
        return kwargs

    def form_valid(self, form):
        try:
            artifact = process_artifact_upload(
                repository=form.cleaned_data["repository"],
                uploaded_file=form.cleaned_data["file"],
                user=self.request.user,
                expected_checksum=form.cleaned_data.get("expected_checksum") or None,
            )
        except ValueError as exc:
            form.add_error(None, str(exc))
            return self.form_invalid(form)
        messages.success(self.request, f"Uploaded artifact {artifact.name}")
        return redirect("webui-repository-detail", name=artifact.repository.name)


class StaffRequiredMixin(UserPassesTestMixin):
    def test_func(self):
        user = self.request.user
        return user.is_authenticated and (user.is_superuser or user.is_staff)


class AdminCreateRepositoryView(LoginRequiredMixin, StaffRequiredMixin, FormView):
    template_name = "webui/admin_create_repository.html"
    form_class = RepositoryCreateForm

    def form_valid(self, form):
        repository = form.save()
        UserRole.objects.get_or_create(
            user=self.request.user,
            repository=repository,
            defaults={"role": UserRole.Role.ADMIN},
        )
        log_audit_event(
            action="repository.created",
            actor=self.request.user,
            repository=repository,
            payload={"source": "webui"},
        )
        messages.success(self.request, f"Created repository '{repository.name}'")
        return redirect("webui-dashboard")


class AdminRepositoryTypePolicyView(LoginRequiredMixin, StaffRequiredMixin, FormView):
    template_name = "webui/admin_repository_types.html"
    form_class = RepositoryTypePolicyForm

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs["instance"] = RepositoryTypePolicy.load()
        return kwargs

    def form_valid(self, form):
        policy = form.save()
        messages.success(
            self.request,
            "Updated allowed repository types: " + ", ".join(policy.enabled_types()),
        )
        return redirect("webui-admin-repository-types")
