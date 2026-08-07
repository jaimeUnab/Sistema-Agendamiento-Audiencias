"""
Módulo de modelos de la aplicación Reglas de Agendamiento.

Contiene el modelo ReglaAgendamiento, que define en qué
días de la semana una competencia puede agendar audiencias.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.db import models

from competencias.models import Competencia


# =====================================================
# ENUMERACIONES
# =====================================================

class DiaSemana(models.TextChoices):
    """
    Define los días hábiles de la semana disponibles
    para el agendamiento de audiencias.

    No incluye sábado ni domingo, ya que el tribunal
    no atiende esos días.
    """

    LUNES = "LUNES", "Lunes"
    MARTES = "MARTES", "Martes"
    MIERCOLES = "MIERCOLES", "Miércoles"
    JUEVES = "JUEVES", "Jueves"
    VIERNES = "VIERNES", "Viernes"


# =====================================================
# MODELO
# =====================================================

class ReglaAgendamiento(models.Model):
    """
    Representa una regla de agendamiento: habilita a una
    competencia para agendar audiencias en un día de la
    semana determinado.

    No define relaciones adicionales todavía; se agregarán
    en tareas técnicas posteriores.
    """

    # Competencia a la que se aplica esta regla.
    # PROTECT: no se permite eliminar una competencia que
    # todavía tenga reglas de agendamiento asociadas.
    competencia = models.ForeignKey(
        Competencia,
        on_delete=models.PROTECT,
        related_name="reglas_agendamiento",
        verbose_name="Competencia"
    )

    # Día de la semana habilitado por esta regla.
    diaSemana = models.CharField(
        max_length=10,
        choices=DiaSemana.choices,
        verbose_name="Día de la semana"
    )

    # Indica si la regla está actualmente vigente.
    activa = models.BooleanField(
        default=True,
        verbose_name="Activa"
    )

    # =================================================
    # CONFIGURACIÓN
    # =================================================

    class Meta:
        # Una misma competencia no puede repetir el mismo
        # día de la semana dos veces.
        constraints = [
            models.UniqueConstraint(
                fields=["competencia", "diaSemana"],
                name="unique_regla_por_competencia_y_dia"
            )
        ]

        # Ordena automáticamente por competencia y día de la semana.
        ordering = ["competencia", "diaSemana"]

    def __str__(self):
        """
        Devuelve "Competencia - Día", por ejemplo:
        "Familia - Martes".
        """
        return f"{self.competencia} - {self.get_diaSemana_display()}"
