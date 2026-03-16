from __future__ import annotations

from django import forms

from repositories.models import Repository, RepositoryTypePolicy
from repositories.policies import repository_type_choices


class ArtifactUploadForm(forms.Form):
    repository = forms.ModelChoiceField(queryset=Repository.objects.none())
    file = forms.FileField()
    expected_checksum = forms.CharField(required=False, min_length=64, max_length=64)

    def __init__(self, *args, repository_queryset=None, **kwargs):
        super().__init__(*args, **kwargs)
        if repository_queryset is not None:
            self.fields["repository"].queryset = repository_queryset


class RepositoryCreateForm(forms.ModelForm):
    class Meta:
        model = Repository
        fields = ("name", "type", "mode", "remote_url")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["type"].choices = repository_type_choices()

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("mode") == Repository.Mode.REMOTE and not cleaned.get("remote_url"):
            self.add_error("remote_url", "remote_url is required for remote repositories.")
        return cleaned


class RepositoryTypePolicyForm(forms.ModelForm):
    class Meta:
        model = RepositoryTypePolicy
        fields = ("allow_deb", "allow_rpm", "allow_pypi", "allow_msi", "allow_generic")
