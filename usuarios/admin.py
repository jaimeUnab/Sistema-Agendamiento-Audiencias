from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import RegistroAcceso, Usuario


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


@admin.register(RegistroAcceso)
class RegistroAccesoAdmin(admin.ModelAdmin):
    """
    Administración de solo lectura del modelo RegistroAcceso.

    No se pueden agregar, modificar ni eliminar registros desde
    el panel de administración: son evidencia de auditoría y
    solo los crea ServicioRegistroAcceso (usuarios/services.py)
    a partir de eventos reales de acceso (usuarios/signals.py,
    usuarios/middleware.py), nunca a mano.
    """

    # Columnas que se mostrarán en la lista
    list_display = (
        "fechaHora",
        "tipoEvento",
        "usuario",
        "nombreUsuarioIntentado",
        "direccionIp",
    )

    # Filtros laterales
    list_filter = (
        "tipoEvento",
        "exitoso",
        "fechaHora",
    )

    # Campos por los cuales se podrá buscar
    search_fields = (
        "nombreUsuarioIntentado",
        "direccionIp",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False