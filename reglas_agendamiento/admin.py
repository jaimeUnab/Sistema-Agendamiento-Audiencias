"""
Módulo de administración de la aplicación Reglas de
Agendamiento.

Registra el modelo ReglaAgendamiento en el panel de
administración de Django.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.contrib import admin

from .models import ReglaAgendamiento


# =====================================================
# ADMIN
# =====================================================

@admin.register(ReglaAgendamiento)
class ReglaAgendamientoAdmin(admin.ModelAdmin):
    """
    Administración del modelo ReglaAgendamiento.

    Permite administrar las reglas de agendamiento del
    sistema desde el panel de administración de Django.
    """

    # Columnas que se mostrarán en la lista.
    list_display = (
        "competencia",
        "diaSemana",
        "activa",
    )

    # Campos por los cuales se podrá buscar.
    #
    # competencia es una FK, por lo que la búsqueda se
    # realiza a través de su campo "nombre" (no es posible
    # buscar directamente sobre una relación).
    search_fields = (
        "competencia__nombre",
    )

    # Filtros laterales.
    list_filter = (
        "competencia",
        "activa",
    )
