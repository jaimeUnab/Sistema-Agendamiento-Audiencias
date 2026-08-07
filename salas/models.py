"""
Módulo de modelos de la aplicación Salas.

Contiene el modelo Sala, que representa las salas físicas
del tribunal donde pueden realizarse las audiencias.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.db import models


# =====================================================
# MODELO
# =====================================================

class Sala(models.Model):
    """
    Representa una sala del tribunal.

    No define relaciones todavía; se agregarán en tareas
    técnicas posteriores.
    """

    # Nombre de la sala. Único, ya que no pueden existir
    # dos salas con el mismo nombre.
    nombre = models.CharField(
        max_length=100,
        unique=True,
        verbose_name="Nombre"
    )

    # Indica si la sala está actualmente vigente.
    activa = models.BooleanField(
        default=True,
        verbose_name="Activa"
    )

    # =================================================
    # CONFIGURACIÓN
    # =================================================

    class Meta:
        # Ordena automáticamente las salas por nombre.
        ordering = ["nombre"]

    def __str__(self):
        """
        Devuelve el nombre de la sala.
        """
        return self.nombre
