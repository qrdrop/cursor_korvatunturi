from django.apps import AppConfig


class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "users"

    def ready(self) -> None:
        from users.bootstrap import bootstrap_initial_admin_from_env

        bootstrap_initial_admin_from_env()
