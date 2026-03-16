from django.db import models


class Repository(models.Model):
    class Type(models.TextChoices):
        DEB = "deb", "Debian APT"
        RPM = "rpm", "RPM"
        PYPI = "pypi", "PyPI"
        MSI = "msi", "MSI"
        GENERIC = "generic", "Generic"

    class Mode(models.TextChoices):
        LOCAL = "local", "Local"
        REMOTE = "remote", "Remote"
        VIRTUAL = "virtual", "Virtual"

    name = models.CharField(max_length=120, unique=True)
    type = models.CharField(max_length=20, choices=Type.choices)
    mode = models.CharField(max_length=20, choices=Mode.choices, default=Mode.LOCAL)
    remote_url = models.URLField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ("name",)

    def __str__(self) -> str:
        return f"{self.name} ({self.type}/{self.mode})"


class RepositoryTypePolicy(models.Model):
    """Singleton policy controlling which repository package types are allowed."""

    allow_deb = models.BooleanField(default=True)
    allow_rpm = models.BooleanField(default=True)
    allow_pypi = models.BooleanField(default=True)
    allow_msi = models.BooleanField(default=True)
    allow_generic = models.BooleanField(default=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Repository type policy"
        verbose_name_plural = "Repository type policies"

    @classmethod
    def load(cls) -> "RepositoryTypePolicy":
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj

    def save(self, *args, **kwargs):
        self.pk = 1
        return super().save(*args, **kwargs)

    def enabled_types(self) -> list[str]:
        enabled: list[str] = []
        if self.allow_deb:
            enabled.append(Repository.Type.DEB)
        if self.allow_rpm:
            enabled.append(Repository.Type.RPM)
        if self.allow_pypi:
            enabled.append(Repository.Type.PYPI)
        if self.allow_msi:
            enabled.append(Repository.Type.MSI)
        if self.allow_generic:
            enabled.append(Repository.Type.GENERIC)
        return enabled
