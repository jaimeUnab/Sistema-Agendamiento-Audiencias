"""
Módulo de modelos de la aplicación Reglas de Agendamiento.

Contiene dos modelos:

- ReglaAgendamiento: configura el plazo legal para una
  combinación de Competencia + TipoAudiencia.
- DiaAtencion: define en qué días de la semana atiende cada
  competencia. Reemplaza la función que antes cumplía
  ReglaAgendamiento (que originalmente representaba esto
  mismo, antes de repurposarse hacia el plazo legal).
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.db import models

from competencias.models import Competencia
from tipos_audiencia.models import TipoAudiencia


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


class TipoPlazo(models.TextChoices):
    """
    Define si un plazo legal se cuenta en días hábiles o en
    días corridos.

    Antes vivía en tipos_audiencia/models.py (como
    TipoAudiencia.tipoPlazo); se traslada aquí porque ahora
    es ReglaAgendamiento quien define el plazo legal, no
    TipoAudiencia.
    """

    HABIL = "HABIL", "Hábil"
    CORRIDO = "CORRIDO", "Corrido"


# =====================================================
# MODELO: PLAZO LEGAL
# =====================================================

class ReglaAgendamiento(models.Model):
    """
    Configura el plazo legal de agendamiento para una
    combinación específica de Competencia + TipoAudiencia.

    No define el día de la semana habilitado: eso lo hace
    DiaAtencion.
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

    # Tipo de audiencia al que se aplica esta regla.
    # PROTECT: no se permite eliminar un tipo de audiencia que
    # todavía tenga reglas de agendamiento asociadas.
    tipoAudiencia = models.ForeignKey(
        TipoAudiencia,
        on_delete=models.PROTECT,
        related_name="reglas_agendamiento",
        verbose_name="Tipo de audiencia"
    )

    # Plazo mínimo para agendar, en la unidad indicada por
    # unidadPlazo.
    #
    # null=True, blank=True: es opcional. Existen reglas que
    # solo definen un piso ("al menos N días de anticipación",
    # sin tope superior) o solo un techo ("dentro de los N días
    # siguientes", sin piso mínimo). Ver plazoMaximo más abajo y
    # audiencias/services.py:_dentroDePlazo(), que interpreta
    # las cuatro combinaciones posibles (solo mínimo, solo
    # máximo, ambos, ninguno).
    plazoMinimo = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Plazo mínimo"
    )

    # Plazo máximo para agendar, en la unidad indicada por
    # unidadPlazo.
    #
    # null=True, blank=True: mismo criterio que plazoMinimo,
    # ver su comentario.
    plazoMaximo = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Plazo máximo"
    )

    # Indica si el plazo se cuenta en días hábiles o corridos.
    unidadPlazo = models.CharField(
        max_length=10,
        choices=TipoPlazo.choices,
        verbose_name="Unidad de plazo"
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
        # Una misma combinación de competencia y tipo de
        # audiencia no puede tener más de una regla de plazo.
        constraints = [
            models.UniqueConstraint(
                fields=["competencia", "tipoAudiencia"],
                name="unique_regla_por_competencia_y_tipo"
            )
        ]

        # Ordena automáticamente por competencia y tipo de audiencia.
        ordering = ["competencia", "tipoAudiencia"]

    def __str__(self):
        """
        Devuelve "Competencia - TipoAudiencia (descripción del
        plazo)", por ejemplo: "Familia - Preparatoria (5-30
        Hábil)". Como plazoMinimo/plazoMaximo ahora son
        opcionales de forma independiente, la descripción se
        arma según cuál de los dos esté configurado (nunca
        muestra "None"), con el mismo criterio que
        audiencias/services.py:_dentroDePlazo() usa para
        interpretar la regla.
        """
        unidad = self.get_unidadPlazo_display()

        if self.plazoMinimo is not None and self.plazoMaximo is not None:
            descripcion_plazo = f"{self.plazoMinimo}-{self.plazoMaximo} {unidad}"
        elif self.plazoMinimo is not None:
            descripcion_plazo = f"mínimo {self.plazoMinimo} {unidad}"
        elif self.plazoMaximo is not None:
            descripcion_plazo = f"máximo {self.plazoMaximo} {unidad}"
        else:
            descripcion_plazo = "sin restricción de plazo"

        return f"{self.competencia} - {self.tipoAudiencia} ({descripcion_plazo})"


# =====================================================
# MODELO: DÍA DE ATENCIÓN
# =====================================================

class DiaAtencion(models.Model):
    """
    Representa un día de la semana en que una competencia
    atiende audiencias.

    Cumple la función que antes cumplía ReglaAgendamiento,
    antes de que ese modelo se repurposara hacia el plazo
    legal (ver ReglaAgendamiento más arriba).
    """

    # Competencia a la que se aplica este día de atención.
    # PROTECT: no se permite eliminar una competencia que
    # todavía tenga días de atención asociados.
    competencia = models.ForeignKey(
        Competencia,
        on_delete=models.PROTECT,
        related_name="dias_atencion",
        verbose_name="Competencia"
    )

    # Día de la semana habilitado.
    diaSemana = models.CharField(
        max_length=10,
        choices=DiaSemana.choices,
        verbose_name="Día de la semana"
    )

    # Indica si el día de atención está actualmente vigente.
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
                name="unique_dia_atencion_por_competencia"
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
