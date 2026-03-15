from __future__ import annotations

from django.http import FileResponse, Http404, HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import generics, permissions, status
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView

from api.serializers import ArtifactSerializer, ArtifactUploadSerializer, RepositorySerializer
from artifacts.models import Artifact, DownloadLog, PackageMetadata
from artifacts.services import process_artifact_upload
from auditing.services import log_audit_event
from proxy.services import fetch_and_cache_remote_artifact
from repositories.models import Repository
from artifact_storage.backends import LocalFileStorageBackend
from users.permissions import can_read, can_write


def _client_ip(request) -> str | None:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR")


def _repositories_for_user(user):
    if user.is_superuser:
        return Repository.objects.all()
    return Repository.objects.filter(user_roles__user=user).distinct()


class RepositoryListCreateView(generics.ListCreateAPIView):
    serializer_class = RepositorySerializer

    def get_queryset(self):
        return _repositories_for_user(self.request.user)

    def perform_create(self, serializer):
        if not (self.request.user.is_superuser or self.request.user.is_staff):
            raise PermissionDenied("Only admin users can create repositories.")
        repository = serializer.save()
        log_audit_event(
            action="repository.created",
            actor=self.request.user,
            repository=repository,
            payload={"type": repository.type, "mode": repository.mode},
            ip_address=_client_ip(self.request),
        )


class ArtifactUploadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = ArtifactUploadSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        repository = serializer.validated_data["repository"]
        if not can_write(request.user, repository):
            raise PermissionDenied("You do not have maintainer access to this repository.")
        try:
            artifact = process_artifact_upload(
                repository=repository,
                uploaded_file=serializer.validated_data["file"],
                user=request.user,
                expected_checksum=serializer.validated_data.get("expected_checksum"),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        output = ArtifactSerializer(artifact)
        return Response(output.data, status=status.HTTP_201_CREATED)


class ArtifactListView(generics.ListAPIView):
    serializer_class = ArtifactSerializer

    def get_queryset(self):
        repos = _repositories_for_user(self.request.user)
        return (
            Artifact.objects.select_related("repository", "uploaded_by", "package_metadata")
            .filter(repository__in=repos)
            .order_by("-uploaded_at")
        )


class ArtifactDownloadView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, repository: str, artifact_path: str):
        if ".." in artifact_path:
            raise Http404("Invalid artifact path")
        repo = get_object_or_404(Repository, name=repository)
        if not can_read(request.user, repo):
            raise PermissionDenied("You do not have access to this repository.")

        artifact = Artifact.objects.filter(repository=repo, path=artifact_path).first()
        if not artifact and repo.mode == Repository.Mode.REMOTE:
            artifact = fetch_and_cache_remote_artifact(
                repository=repo,
                artifact_path=artifact_path,
                user=request.user,
            )
        if not artifact:
            raise Http404("Artifact not found")

        backend = LocalFileStorageBackend()
        absolute_path = backend.retrieve(artifact.storage_path)
        response = FileResponse(open(absolute_path, "rb"), as_attachment=True, filename=artifact.name)
        response["X-Checksum-SHA256"] = artifact.checksum
        DownloadLog.objects.create(artifact=artifact, user=request.user, ip_address=_client_ip(request))
        log_audit_event(
            action="artifact.downloaded",
            actor=request.user,
            repository=repo,
            artifact=artifact,
            payload={"path": artifact.path},
            ip_address=_client_ip(request),
        )
        return response


class PyPISimpleIndexView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        repos = _repositories_for_user(request.user).filter(type=Repository.Type.PYPI)
        package_names = (
            PackageMetadata.objects.filter(artifact__repository__in=repos)
            .values_list("package_name", flat=True)
            .distinct()
        )
        links = "\n".join(
            [f'<a href="/simple/{name.lower().replace("_", "-")}/">{name}</a><br/>' for name in package_names]
        )
        return HttpResponse(f"<html><body>{links}</body></html>", content_type="text/html")


class PyPISimpleIndexDetailView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, package_name: str):
        repos = _repositories_for_user(request.user).filter(type=Repository.Type.PYPI)
        artifacts = Artifact.objects.filter(
            repository__in=repos,
            package_metadata__package_name__iexact=package_name,
        ).select_related("repository")
        links = []
        for artifact in artifacts:
            href = f"/repo/{artifact.repository.name}/{artifact.path}#sha256={artifact.checksum}"
            links.append(f'<a href="{href}">{artifact.name}</a><br/>')
        return HttpResponse("<html><body>" + "\n".join(links) + "</body></html>", content_type="text/html")
