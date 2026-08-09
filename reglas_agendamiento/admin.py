"""
Módulo de administración de la aplicación Reglas de
Agendamiento.

Registra los modelos ReglaAgendamiento y DiaAtencion en el
panel de administración de Django.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.contrib import admin

from .models import DiaAtencion, ReglaAgendamiento


# =====================================================
# ADMIN: PLAZO LEGAL
# =====================================================

@admin.register(ReglaAgendamiento)
class ReglaAgendamientoAdmin(admin.ModelAdmin):
    """
    Administración del modelo ReglaAgendamiento.

    Permite administrar el plazo legal (por competencia y
    tipo de audiencia) desde el panel de administración
    de Django.
    """

    # Columnas que se mostrarán en la lista.
    list_display = (
        "competencia",
        "tipoAudiencia",
        "plazoMinimo",
        "plazoMaximo",
        "unidadPlazo",
        "activa",
    )

    # Campos por los cuales se podrá buscar.
    #
    # competencia y tipoAudiencia son FK, por lo que la
    # búsqueda se realiza a través de su campo "nombre" (no es
    # posible buscar directamente sobre una relación).
    search_fields = (
        "competencia__nombre",
        "tipoAudiencia__nombre",
    )

    # Filtros laterales.
    list_filter = (
        "competencia",
        "unidadPlazo",
        "activa",
    )


# =====================================================
# ADMIN: DÍA DE ATENCIÓN
# =====================================================

@admin.register(DiaAtencion)
class DiaAtencionAdmin(admin.ModelAdmin):
    """
    Administración del modelo DiaAtencion.

    Permite administrar los días de la semana en que atiende
    cada competencia desde el panel de administración
    de Django.
    """

    # Columnas que se mostrarán en la lista.
    list_display = (
        "competencia",
        "diaSemana",
        "activa",
    )

    # Campos por los cuales se podrá buscar.
    search_fields = (
        "competencia__nombre",
    )

    # Filtros laterales.
    list_filter = (
        "competencia",
        "activa",
    )
