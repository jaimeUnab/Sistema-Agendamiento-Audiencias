"""
Módulo de modelos de la aplicación Tipos de Audiencia.

Contiene el modelo TipoAudiencia, que define los tipos de
audiencia disponibles en el sistema.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.db import models


# =====================================================
# MODELO
# =====================================================

class TipoAudiencia(models.Model):
    """
    Representa un tipo de audiencia.

    Es un catálogo transversal: ya no está asociado a una
    competencia específica (antes lo estaba). El plazo legal
    de cada tipo de audiencia depende de la combinación
    Competencia + TipoAudiencia, y se define en
    ReglaAgendamiento (app reglas_agendamiento), no aquí.
    """

    # Nombre del tipo de audiencia. Único, ya que ahora es un
    # catálogo transversal (no está acotado por competencia).
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre"
    )

    # Descripción del tipo de audiencia.
    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción"
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
        # Ordena automáticamente por nombre. Antes se ordenaba
        # también por competencia, pero ese campo ya no existe
        # en este modelo.
        ordering = ["nombre"]

    def __str__(self):
        """
        Devuelve el nombre del tipo de audiencia.
        """
        return self.nombre
