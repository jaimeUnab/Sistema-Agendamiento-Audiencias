"""
Módulo de modelos de la aplicación Causas.

Contiene el modelo Causa, que representa una causa judicial
sobre la cual pueden agendarse audiencias.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.db import models

from competencias.models import Competencia


# =====================================================
# MODELO
# =====================================================

class Causa(models.Model):
    """
    Representa una causa judicial.

    Modelo mínimo: solo contiene los datos de identificación
    de la causa (RIT, RUC, carátula) y su competencia. No
    incluye tribunal, estado procesal, fecha de ingreso,
    materia ni litigantes porque no están definidos todavía.
    """

    # Competencia a la que pertenece esta causa. Permite que,
    # al ingresar el RIT, el sistema recupere también la
    # competencia asociada.
    # PROTECT: no se permite eliminar una competencia que
    # todavía tenga causas asociadas (mismo criterio que
    # TipoAudiencia.competencia y ReglaAgendamiento.competencia).
    competencia = models.ForeignKey(
        Competencia,
        on_delete=models.PROTECT,
        related_name="causas",
        verbose_name="Competencia"
    )

    # RIT (Rol Interno del Tribunal). Es un identificador, no
    # un valor numérico: se almacena como texto para conservar
    # su formato exacto (guiones, ceros iniciales, etc.).
    rit = models.CharField(
        max_length=20,
        verbose_name="RIT"
    )

    # RUC (Rol Único de Causa). Mismo criterio que RIT: texto,
    # no número.
    ruc = models.CharField(
        max_length=20,
        verbose_name="RUC"
    )

    # Carátula de la causa (por ejemplo, "Fiscal de Chile con
    # Juan Pérez").
    caratulado = models.CharField(
        max_length=255,
        verbose_name="Carátulo"
    )

    # =================================================
    # CONFIGURACIÓN
    # =================================================

    class Meta:
        # Ordena automáticamente por RIT. No fue pedido
        # explícitamente; se agrega solo por consistencia con
        # el resto de los modelos del proyecto, que siempre
        # definen un orden por defecto.
        ordering = ["rit"]

    def __str__(self):
        """
        Devuelve "RIT <rit> - <carátula>", por ejemplo:
        "RIT 1234-2024 - Fiscal de Chile con Juan Pérez".
        """
        return f"RIT {self.rit} - {self.caratulado}"
