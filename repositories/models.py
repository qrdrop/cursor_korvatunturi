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
