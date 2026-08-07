"""
Módulo de administración de la aplicación Tipos de Audiencia.

Registra el modelo TipoAudiencia en el panel de
administración de Django.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.contrib import admin

from .models import TipoAudiencia


# =====================================================
# ADMIN
# =====================================================

@admin.register(TipoAudiencia)
class TipoAudienciaAdmin(admin.ModelAdmin):
    """
    Administración del modelo TipoAudiencia.

    Permite administrar los tipos de audiencia del sistema
    desde el panel de administración de Django.
    """

    # Columnas que se mostrarán en la lista.
    list_display = (
        "competencia",
        "nombre",
        "plazoMinimoDias",
        "plazoMaximoDias",
        "tipoPlazo",
        "activo",
    )

    # Campos por los cuales se podrá buscar.
    search_fields = (
        "nombre",
    )

    # Filtros laterales.
    list_filter = (
        "competencia",
        "tipoPlazo",
    )
