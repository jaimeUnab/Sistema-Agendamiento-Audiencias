"""
Módulo de administración de la aplicación Salas.

Registra el modelo Sala en el panel de administración
de Django.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.contrib import admin

from .models import Sala


# =====================================================
# ADMIN
# =====================================================

@admin.register(Sala)
class SalaAdmin(admin.ModelAdmin):
    """
    Administración del modelo Sala.

    Permite administrar las salas del tribunal desde el
    panel de administración de Django.
    """

    # Columnas que se mostrarán en la lista.
    list_display = (
        "nombre",
        "activa",
    )

    # Campos por los cuales se podrá buscar.
    search_fields = (
        "nombre",
    )

    # Orden por defecto.
    ordering = (
        "nombre",
    )
