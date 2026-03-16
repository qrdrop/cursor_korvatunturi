from __future__ import annotations

import logging
import os

from django.contrib.auth import get_user_model
from django.db import OperationalError, ProgrammingError

logger = logging.getLogger(__name__)
_BOOTSTRAP_DONE = False


def bootstrap_initial_admin_from_env() -> None:
    """Create first admin account if configured and none exists."""
    global _BOOTSTRAP_DONE
    if _BOOTSTRAP_DONE:
        return

    username = os.environ.get("DJANGO_INITIAL_ADMIN_USERNAME")
    password = os.environ.get("DJANGO_INITIAL_ADMIN_PASSWORD")
    email = os.environ.get("DJANGO_INITIAL_ADMIN_EMAIL", "admin@example.com")
    if not username or not password:
        return

    User = get_user_model()
    try:
        if User.objects.filter(is_superuser=True).exists():
            _BOOTSTRAP_DONE = True
            return
        user, created = User.objects.get_or_create(
            username=username,
            defaults={"email": email, "is_staff": True, "is_superuser": True},
        )
        if created:
            user.set_password(password)
            user.save(update_fields=["password"])
            logger.info("Bootstrapped initial admin user '%s' from environment.", username)
        else:
            user.is_staff = True
            user.is_superuser = True
            user.email = email
            user.set_password(password)
            user.save(update_fields=["is_staff", "is_superuser", "email", "password"])
            logger.info("Promoted and updated initial admin user '%s' from environment.", username)
        _BOOTSTRAP_DONE = True
    except (OperationalError, ProgrammingError):
        # Database tables may not be ready yet (startup before migrations).
        return
