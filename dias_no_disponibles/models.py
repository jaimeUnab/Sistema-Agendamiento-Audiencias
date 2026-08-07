"""
Módulo de modelos de la aplicación Días No Disponibles.

Contiene el modelo DiaNoDisponible, que representa las
fechas en las que el tribunal no atiende (feriados, cierres,
mantenciones, suspensiones judiciales, etc.).
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.db import models


# =====================================================
# ENUMERACIONES
# =====================================================

class TipoDiaNoDisponible(models.TextChoices):
    """
    Define los motivos por los cuales una fecha queda
    marcada como no disponible para agendar audiencias.
    """

    FERIADO = "FERIADO", "Feriado"
    CIERRE_TRIBUNAL = "CIERRE_TRIBUNAL", "Cierre de tribunal"
    MANTENCION = "MANTENCION", "Mantención"
    SUSPENSION_JUDICIAL = "SUSPENSION_JUDICIAL", "Suspensión judicial"
    OTRO = "OTRO", "Otro"


# =====================================================
# MODELO
# =====================================================

class DiaNoDisponible(models.Model):
    """
    Representa una fecha en la que el tribunal no atiende.

    No define relaciones todavía; se agregarán en tareas
    técnicas posteriores.
    """

    # Fecha no disponible. Única, ya que no puede existir
    # más de un registro para la misma fecha.
    fecha = models.DateField(
        unique=True,
        verbose_name="Fecha"
    )

    # Motivo o descripción del día no disponible.
    motivo = models.CharField(
        max_length=255,
        verbose_name="Motivo"
    )

    # Tipo de día no disponible.
    tipo = models.CharField(
        max_length=25,
        choices=TipoDiaNoDisponible.choices,
        verbose_name="Tipo"
    )

    # Indica si el registro está actualmente vigente.
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )

    # =================================================
    # CONFIGURACIÓN
    # =================================================

    class Meta:
        # Ordena automáticamente por fecha.
        ordering = ["fecha"]

    def __str__(self):
        """
        Devuelve "YYYY-MM-DD - Tipo", por ejemplo:
        "2026-09-18 - Feriado".
        """
        return f"{self.fecha.isoformat()} - {self.get_tipo_display()}"
