"""
Módulo de modelos de la aplicación Bloques.

Contiene el modelo BloqueHorario, que representa el
horario oficial de audiencias del tribunal.
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

    Los bloques únicamente describen el horario oficial;
    este modelo no contiene ninguna lógica de validación.
    Más adelante, ValidadorAgendamiento utilizará estos
    bloques solo para generar advertencias y propuestas de
    fecha, sin impedir agendar audiencias fuera de él.
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

    # Indica si el bloque está actualmente vigente.
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
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
