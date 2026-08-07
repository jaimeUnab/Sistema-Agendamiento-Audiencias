"""
Módulo de administración de la aplicación Bloques.

Registra el modelo BloqueHorario en el panel de
administración de Django.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.contrib import admin

from .models import BloqueHorario


# =====================================================
# ADMIN
# =====================================================

@admin.register(BloqueHorario)
class BloqueHorarioAdmin(admin.ModelAdmin):
    """
    Administración del modelo BloqueHorario.

    Permite administrar el horario oficial de audiencias
    del tribunal desde el panel de administración de Django.
    """

    # Columnas que se mostrarán en la lista.
    list_display = (
        "orden",
        "horaInicio",
        "horaTermino",
        "permiteAgendamientoAutomatico",
    )

    # Campos por los cuales se podrá buscar.
    search_fields = (
        "orden",
    )

    # Orden por defecto.
    ordering = (
        "orden",
    )
