from django.apps import AppConfig


class UsuariosConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'usuarios'

    def ready(self):
        """
        Importa usuarios/signals.py para conectar los
        receptores de user_logged_in/user_logged_out/
        user_login_failed que registran RegistroAcceso.

        La importación se hace aquí, dentro de ready(), no al
        nivel del módulo: es el punto exacto en el que Django
        recomienda conectar señales, ya con todas las apps
        cargadas (evita problemas de importación circular
        durante el arranque).
        """
        import usuarios.signals  # noqa: F401
