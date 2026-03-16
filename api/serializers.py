from rest_framework import serializers

from artifacts.models import Artifact, PackageMetadata
from repositories.models import Repository
from repositories.policies import enabled_repository_types


class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = ("id", "name", "type", "mode", "remote_url", "created_at")
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        repository_type = attrs.get("type", getattr(self.instance, "type", None))
        if repository_type and repository_type not in set(enabled_repository_types()):
            raise serializers.ValidationError(
                f"Repository type '{repository_type}' is disabled by admin policy."
            )
        mode = attrs.get("mode", getattr(self.instance, "mode", Repository.Mode.LOCAL))
        remote_url = attrs.get("remote_url")
        if mode == Repository.Mode.REMOTE and not remote_url:
            raise serializers.ValidationError("remote_url is required for remote repositories.")
        return attrs


class ArtifactSerializer(serializers.ModelSerializer):
    repository = serializers.SlugRelatedField(slug_field="name", read_only=True)
    package_name = serializers.SerializerMethodField()
    dependencies = serializers.SerializerMethodField()
    metadata_json = serializers.SerializerMethodField()

    class Meta:
        model = Artifact
        fields = (
            "id",
            "repository",
            "name",
            "path",
            "version",
            "architecture",
            "checksum",
            "size",
            "uploaded_at",
            "uploaded_by",
            "is_cached",
            "package_name",
            "dependencies",
            "metadata_json",
        )

    def get_package_name(self, obj):
        try:
            return obj.package_metadata.package_name
        except PackageMetadata.DoesNotExist:
            return ""

    def get_dependencies(self, obj):
        try:
            return obj.package_metadata.dependencies
        except PackageMetadata.DoesNotExist:
            return []

    def get_metadata_json(self, obj):
        try:
            return obj.package_metadata.metadata_json
        except PackageMetadata.DoesNotExist:
            return {}


class ArtifactUploadSerializer(serializers.Serializer):
    repository = serializers.PrimaryKeyRelatedField(queryset=Repository.objects.all())
    file = serializers.FileField()
    expected_checksum = serializers.CharField(required=False, allow_blank=False, min_length=64, max_length=64)
