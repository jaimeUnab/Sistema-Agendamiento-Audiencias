"""
Módulo de modelos de la aplicación Competencias.

Contiene el modelo Competencia, que representa las
materias/competencias que puede tratar una audiencia.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.db import models


# =====================================================
# MODELO
# =====================================================

class Competencia(models.Model):
    """
    Representa una competencia (materia) que puede
    asignarse a una audiencia.

    No define relaciones todavía; se agregarán en tareas
    técnicas posteriores.
    """

    # Nombre de la competencia. Único, ya que no pueden
    # existir dos competencias con el mismo nombre.
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre"
    )

    # Descripción de la competencia. Puede quedar en blanco.
    descripcion = models.TextField(
        blank=True,
        verbose_name="Descripción"
    )

    # Indica si la competencia está actualmente vigente.
    activa = models.BooleanField(
        default=True,
        verbose_name="Activa"
    )

    # =================================================
    # CONFIGURACIÓN
    # =================================================

    class Meta:
        # Ordena automáticamente las competencias por nombre.
        ordering = ["nombre"]

    def __str__(self):
        """
        Devuelve el nombre de la competencia.
        """
        return self.nombre
