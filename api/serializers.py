from rest_framework import serializers

from artifacts.models import Artifact
from repositories.models import Repository


class RepositorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Repository
        fields = ("id", "name", "type", "mode", "remote_url", "created_at")
        read_only_fields = ("id", "created_at")

    def validate(self, attrs):
        mode = attrs.get("mode", getattr(self.instance, "mode", Repository.Mode.LOCAL))
        remote_url = attrs.get("remote_url")
        if mode == Repository.Mode.REMOTE and not remote_url:
            raise serializers.ValidationError("remote_url is required for remote repositories.")
        return attrs


class ArtifactSerializer(serializers.ModelSerializer):
    repository = serializers.SlugRelatedField(slug_field="name", read_only=True)
    package_name = serializers.CharField(source="package_metadata.package_name", read_only=True)

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
        )


class ArtifactUploadSerializer(serializers.Serializer):
    repository = serializers.PrimaryKeyRelatedField(queryset=Repository.objects.all())
    file = serializers.FileField()
    expected_checksum = serializers.CharField(required=False, allow_blank=False, min_length=64, max_length=64)
