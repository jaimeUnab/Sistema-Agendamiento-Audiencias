from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    """
    Administración del modelo Usuario.

    Permite administrar los usuarios del sistema
    desde el panel de administración de Django.
    """

    # Columnas que se mostrarán en la lista
    list_display = (
        "nombre",
        "email",
        "rol",
        "is_active",
        "is_staff",
    )

    # Campos por los cuales se podrá buscar
    search_fields = (
        "nombre",
        "email",
    )

    # Filtros laterales
    list_filter = (
        "rol",
        "is_active",
    )

    # Orden por defecto
    ordering = (
        "nombre",
    )