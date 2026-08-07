"""
Módulo de administración de la aplicación Días No
Disponibles.

Registra el modelo DiaNoDisponible en el panel de
administración de Django.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.contrib import admin

from .models import DiaNoDisponible


# =====================================================
# ADMIN
# =====================================================

@admin.register(DiaNoDisponible)
class DiaNoDisponibleAdmin(admin.ModelAdmin):
    """
    Administración del modelo DiaNoDisponible.

    Permite administrar los días no disponibles del
    sistema desde el panel de administración de Django.
    """

    # Columnas que se mostrarán en la lista.
    list_display = (
        "fecha",
        "tipo",
        "activo",
    )

    # Campos por los cuales se podrá buscar.
    search_fields = (
        "motivo",
    )

    # Filtros laterales.
    list_filter = (
        "tipo",
        "activo",
    )
