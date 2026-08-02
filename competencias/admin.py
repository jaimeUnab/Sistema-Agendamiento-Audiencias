"""
Módulo de administración de la aplicación Competencias.

Registra el modelo Competencia en el panel de
administración de Django.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.contrib import admin

from .models import Competencia


# =====================================================
# ADMIN
# =====================================================

@admin.register(Competencia)
class CompetenciaAdmin(admin.ModelAdmin):
    """
    Administración del modelo Competencia.

    Permite administrar las competencias del sistema
    desde el panel de administración de Django.
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
