"""
Módulo de modelos de la aplicación Bloques.

Contiene dos modelos:

- BloqueHorario: representa el horario oficial de audiencias
  del tribunal (bloques concretos).
- ConfiguracionAgendamiento: parámetros generales del
  tribunal para el agendamiento (jornada, duración de bloque,
  horizonte de búsqueda). Es configuración global, con una
  única instancia posible.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.db import models


# =====================================================
# MODELO
# =====================================================

class BloqueHorario(models.Model):
    """
    Representa un bloque horario del horario oficial
    del tribunal.

    Los bloques del horario oficial nunca dejan de existir;
    no tienen un estado de "activo/inactivo". Lo que puede
    variar es si el algoritmo de agendamiento está habilitado
    para proponerlos automáticamente (ver
    permiteAgendamientoAutomatico). Este modelo no contiene
    ninguna lógica de validación: más adelante,
    ValidadorAgendamiento utilizará estos bloques solo para
    generar advertencias y propuestas de fecha, sin impedir
    agendar audiencias fuera de él.
    """

    # Hora de inicio del bloque.
    horaInicio = models.TimeField(
        verbose_name="Hora de inicio"
    )

    # Hora de término del bloque.
    horaTermino = models.TimeField(
        verbose_name="Hora de término"
    )

    # Orden del bloque dentro del horario oficial. Único,
    # ya que dos bloques no pueden ocupar la misma posición.
    orden = models.PositiveIntegerField(
        unique=True,
        verbose_name="Orden"
    )

    # Indica si el algoritmo de agendamiento puede proponer
    # este bloque automáticamente. No representa si el bloque
    # "existe" o no: el horario oficial siempre conserva
    # todos sus bloques; esto solo habilita/inhabilita su
    # propuesta automática.
    permiteAgendamientoAutomatico = models.BooleanField(
        default=True,
        verbose_name="Permite agendamiento automático"
    )

    # =================================================
    # CONFIGURACIÓN
    # =================================================

    class Meta:
        # Ordena automáticamente los bloques por su orden.
        ordering = ["orden"]

    def __str__(self):
        """
        Devuelve una representación legible del bloque,
        por ejemplo: "Bloque 1 (08:30 - 09:00)".
        """
        return (
            f"Bloque {self.orden} "
            f"({self.horaInicio.strftime('%H:%M')} - "
            f"{self.horaTermino.strftime('%H:%M')})"
        )


# =====================================================
# MODELO: CONFIGURACIÓN GENERAL DE AGENDAMIENTO
# =====================================================

class ConfiguracionAgendamiento(models.Model):
    """
    Parámetros generales de agendamiento del tribunal.

    Son comunes para todo el tribunal: no dependen de una
    competencia ni de un tipo de audiencia (esos casos ya
    están cubiertos por ReglaAgendamiento y DiaAtencion, en
    la app reglas_agendamiento).

    Existe una única instancia posible de este modelo (ver
    "claveUnica" más abajo).
    """

    # Hora de inicio de la jornada del tribunal.
    horaInicioJornada = models.TimeField(
        verbose_name="Hora de inicio de la jornada"
    )

    # Hora de término de la jornada del tribunal.
    horaTerminoJornada = models.TimeField(
        verbose_name="Hora de término de la jornada"
    )

    # Duración de cada bloque horario, en minutos.
    duracionBloque = models.PositiveIntegerField(
        verbose_name="Duración del bloque (minutos)"
    )

    # Cantidad de días que el sistema considera al buscar
    # automáticamente fechas disponibles para una audiencia.
    horizonteBusquedaDias = models.PositiveIntegerField(
        verbose_name="Horizonte de búsqueda (días)"
    )

    # -------------------------------------------------
    # GARANTÍA DE INSTANCIA ÚNICA
    # -------------------------------------------------
    # Campo técnico, no editable desde formularios. Al tener
    # un valor por defecto fijo (1) y ser unique=True, la
    # base de datos rechaza cualquier segundo registro: un
    # segundo INSERT también intentaría guardar claveUnica=1
    # y violaría la restricción de unicidad. Esta es una
    # garantía real a nivel de base de datos, no solo de la
    # aplicación.
    claveUnica = models.PositiveSmallIntegerField(
        default=1,
        unique=True,
        editable=False,
        verbose_name="Clave única (uso interno)"
    )

    def __str__(self):
        """
        Como solo puede existir una instancia, se identifica
        con un nombre fijo y descriptivo.
        """
        return "Configuración general de agendamiento"
