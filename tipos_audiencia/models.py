"""
Módulo de modelos de la aplicación Tipos de Audiencia.

Contiene el modelo TipoAudiencia, que define los tipos de
audiencia disponibles para cada competencia, junto con sus
plazos legales de agendamiento.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.db import models

from competencias.models import Competencia


# =====================================================
# ENUMERACIONES
# =====================================================

class TipoPlazo(models.TextChoices):
    """
    Define si el plazo de un tipo de audiencia se cuenta
    en días hábiles o en días corridos.
    """

    HABIL = "HABIL", "Hábil"
    CORRIDO = "CORRIDO", "Corrido"


# =====================================================
# MODELO
# =====================================================

class TipoAudiencia(models.Model):
    """
    Representa un tipo de audiencia asociado a una
    competencia, junto con sus plazos legales de
    agendamiento.

    El nombre no es único globalmente: distintas
    competencias pueden tener tipos de audiencia con el
    mismo nombre, pero una misma competencia no puede
    repetir el mismo nombre dos veces (ver UniqueConstraint
    en Meta).
    """

    # Competencia a la que pertenece este tipo de audiencia.
    # PROTECT: no se permite eliminar una competencia que
    # todavía tenga tipos de audiencia asociados.
    competencia = models.ForeignKey(
        Competencia,
        on_delete=models.PROTECT,
        related_name="tipos_audiencia",
        verbose_name="Competencia"
    )

    # Nombre del tipo de audiencia.
    nombre = models.CharField(
        max_length=100,
        verbose_name="Nombre"
    )

    # Descripción del tipo de audiencia.
    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción"
    )

    # Plazo mínimo, en días, para agendar este tipo de audiencia.
    plazoMinimoDias = models.PositiveIntegerField(
        verbose_name="Plazo mínimo (días)"
    )

    # Plazo máximo, en días, para agendar este tipo de audiencia.
    plazoMaximoDias = models.PositiveIntegerField(
        verbose_name="Plazo máximo (días)"
    )

    # Horizonte de búsqueda, en días, utilizado más adelante
    # para proponer fechas disponibles.
    horizonteBusquedaDias = models.PositiveIntegerField(
        verbose_name="Horizonte de búsqueda (días)"
    )

    # Indica si el plazo se cuenta en días hábiles o corridos.
    tipoPlazo = models.CharField(
        max_length=10,
        choices=TipoPlazo.choices,
        verbose_name="Tipo de plazo"
    )

    # Indica si el tipo de audiencia está actualmente vigente.
    activo = models.BooleanField(
        default=True,
        verbose_name="Activo"
    )

    # =================================================
    # CONFIGURACIÓN
    # =================================================

    class Meta:
        # Una misma competencia no puede repetir el mismo
        # nombre de tipo de audiencia dos veces.
        constraints = [
            models.UniqueConstraint(
                fields=["competencia", "nombre"],
                name="unique_tipo_audiencia_por_competencia"
            )
        ]

        # Ordena automáticamente por competencia y nombre.
        ordering = ["competencia", "nombre"]

    def __str__(self):
        """
        Devuelve "Competencia - Nombre", por ejemplo:
        "Familia - Preparatoria".
        """
        return f"{self.competencia} - {self.nombre}"
