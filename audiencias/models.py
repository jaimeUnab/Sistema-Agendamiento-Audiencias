"""
Módulo de modelos de la aplicación Audiencias.

Contiene dos modelos:

- Audiencia: representa el agendamiento de una audiencia
  judicial.
- RegistroTrazabilidad: audita las operaciones (creación,
  modificación, baja) realizadas sobre una Audiencia.

Este módulo solo define la estructura de datos. No implementa
todavía ninguna regla de negocio: ni cálculo de plazos, ni
validación de conflictos de sala/bloque, ni disponibilidad,
ni propuesta automática de fecha, ni el servicio que
efectivamente registre la trazabilidad. Esas reglas se
agregarán más adelante mediante servicios de negocio
independientes.
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from bloques.models import BloqueHorario
from causas.models import Causa
from salas.models import Sala
from tipos_audiencia.models import TipoAudiencia


# =====================================================
# ENUMERACIONES
# =====================================================

class EstadoAudiencia(models.TextChoices):
    """
    Define los estados posibles de una audiencia.

    Por ahora solo existen estos dos: una audiencia está
    vigente (PROGRAMADA) o fue dejada sin efecto (ELIMINADA,
    baja lógica, nunca eliminación física).
    """

    PROGRAMADA = "PROGRAMADA", "Programada"
    ELIMINADA = "ELIMINADA", "Eliminada"


class AccionTrazabilidad(models.TextChoices):
    """
    Define las operaciones sobre una Audiencia que
    RegistroTrazabilidad puede registrar.
    """

    CREACION = "CREACION", "Creación"
    MODIFICACION = "MODIFICACION", "Modificación"
    BAJA = "BAJA", "Baja"


# =====================================================
# MODELO
# =====================================================

class Audiencia(models.Model):
    """
    Representa el agendamiento de una audiencia judicial.

    No define relación directa con Competencia: la
    competencia se obtiene indirectamente a través de
    "causa" o de "tipoAudiencia" (ambas ya la referencian).
    """

    # -------------------------------------------------
    # RELACIONES
    # -------------------------------------------------
    # Las cuatro relaciones con catálogos usan PROTECT: una
    # audiencia es información histórica y no debe perderse
    # ni quedar huérfana si el catálogo relacionado se elimina
    # (el catálogo, en ese caso, simplemente no podrá
    # eliminarse mientras existan audiencias que lo usen).

    # Causa judicial sobre la que se agenda la audiencia.
    causa = models.ForeignKey(
        Causa,
        on_delete=models.PROTECT,
        related_name="audiencias",
        verbose_name="Causa"
    )

    # Tipo de audiencia (y, a través de él, su competencia y
    # sus plazos legales).
    tipoAudiencia = models.ForeignKey(
        TipoAudiencia,
        on_delete=models.PROTECT,
        related_name="audiencias",
        verbose_name="Tipo de audiencia"
    )

    # Sala física donde se realizará la audiencia.
    sala = models.ForeignKey(
        Sala,
        on_delete=models.PROTECT,
        related_name="audiencias",
        verbose_name="Sala"
    )

    # -------------------------------------------------
    # BLOQUES Y HORARIO
    # -------------------------------------------------

    # Primer bloque horario ocupado por la audiencia. Junto
    # con "cantidadBloques" define qué bloques consecutivos
    # utiliza (por ejemplo, bloqueInicio=bloque 10 y
    # cantidadBloques=2 significa que usa los bloques 10 y 11).
    bloqueInicio = models.ForeignKey(
        BloqueHorario,
        on_delete=models.PROTECT,
        related_name="audiencias",
        verbose_name="Bloque de inicio"
    )

    # Cantidad de bloques consecutivos que ocupa la audiencia,
    # a partir de "bloqueInicio".
    cantidadBloques = models.PositiveIntegerField(
        # Validación estructural: una audiencia no puede
        # ocupar 0 bloques. No valida disponibilidad ni
        # continuidad real de los bloques (eso corresponde a
        # un futuro validador de negocio).
        validators=[MinValueValidator(1)],
        verbose_name="Cantidad de bloques"
    )

    # Fecha en la que se realizará la audiencia.
    fecha = models.DateField(
        verbose_name="Fecha"
    )

    # Hora de inicio "fotografiada" al momento de registrar la
    # audiencia. No se recalcula a partir de BloqueHorario: si
    # el horario oficial cambia después, esta audiencia
    # conserva su hora histórica tal como quedó registrada.
    horaInicio = models.TimeField(
        verbose_name="Hora de inicio"
    )

    # Hora de término "fotografiada", con el mismo criterio
    # que horaInicio.
    horaTermino = models.TimeField(
        verbose_name="Hora de término"
    )

    # -------------------------------------------------
    # ESTADO
    # -------------------------------------------------

    # Estado de la audiencia. Toda audiencia nace PROGRAMADA;
    # pasa a ELIMINADA únicamente mediante una baja lógica
    # (no se borra el registro de la base de datos).
    estado = models.CharField(
        max_length=15,
        choices=EstadoAudiencia.choices,
        default=EstadoAudiencia.PROGRAMADA,
        verbose_name="Estado"
    )

    # Motivo de la baja. Opcional: solo se espera que se use
    # cuando la audiencia pasa a ELIMINADA (esa lógica todavía
    # no está implementada, se agrega en una etapa posterior).
    motivoBaja = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Motivo de baja"
    )

    # -------------------------------------------------
    # AUDITORÍA DE CREACIÓN
    # -------------------------------------------------

    # Fecha y hora de creación del registro. auto_now_add la
    # asigna automáticamente una única vez, al crear la
    # audiencia, y Django la vuelve no editable a partir de
    # ahí: no puede modificarse en ediciones posteriores.
    # Servirá como fecha de referencia para el cálculo de
    # plazos legales en una etapa futura.
    fechaCreacion = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha de creación"
    )

    # Usuario del sistema que registró la audiencia.
    usuarioCreacion = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="audiencias_creadas",
        verbose_name="Usuario que creó la audiencia"
    )

    # =================================================
    # CONFIGURACIÓN
    # =================================================

    class Meta:
        # Ordena automáticamente por fecha y hora de inicio.
        # No fue pedido explícitamente; se agrega solo por
        # consistencia con el resto de los modelos del
        # proyecto, que siempre definen un orden por defecto.
        ordering = ["fecha", "horaInicio"]

    def __str__(self):
        """
        Devuelve una representación legible de la audiencia,
        por ejemplo:
        "Audiencia RIT 1234-2024 - 2026-09-18 09:00".
        """
        return (
            f"Audiencia RIT {self.causa.rit} - "
            f"{self.fecha.isoformat()} "
            f"{self.horaInicio.strftime('%H:%M')}"
        )


# =====================================================
# MODELO: TRAZABILIDAD
# =====================================================

class RegistroTrazabilidad(models.Model):
    """
    Audita una operación realizada sobre una Audiencia.

    Permite reconstruir qué audiencia fue afectada, qué
    usuario realizó la operación, cuándo, qué operación fue,
    y cuáles eran los valores antes y después del cambio.

    Solo define la estructura de datos: el servicio que
    efectivamente crea estos registros (ServicioTrazabilidad)
    se implementará en una etapa posterior. Por eso mismo,
    este modelo no impide todavía su modificación o
    eliminación por código: esa restricción se aplicará más
    adelante a nivel de administración/permisos, no aquí.
    """

    # Audiencia afectada por la operación.
    # PROTECT: un registro de trazabilidad es, en sí mismo,
    # información histórica; no debe perderse ni quedar
    # huérfano si la audiencia referenciada se eliminara
    # físicamente (lo cual, además, hoy no ocurre: Audiencia
    # solo tiene baja lógica).
    audiencia = models.ForeignKey(
        Audiencia,
        on_delete=models.PROTECT,
        related_name="registros_trazabilidad",
        verbose_name="Audiencia"
    )

    # Usuario que realizó la operación.
    usuario = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="registros_trazabilidad",
        verbose_name="Usuario"
    )

    # Fecha y hora en que ocurrió la operación. auto_now_add
    # la asigna una única vez, al crear el registro, y no se
    # modifica después (mismo criterio que
    # Audiencia.fechaCreacion).
    fechaHora = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Fecha y hora"
    )

    # Operación realizada sobre la audiencia.
    accion = models.CharField(
        max_length=15,
        choices=AccionTrazabilidad.choices,
        verbose_name="Acción"
    )

    # Valores de la audiencia antes de la operación. Queda en
    # blanco en una creación (no existían valores previos).
    valoresAnteriores = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Valores anteriores"
    )

    # Valores de la audiencia después de la operación.
    valoresNuevos = models.JSONField(
        null=True,
        blank=True,
        verbose_name="Valores nuevos"
    )

    # =================================================
    # CONFIGURACIÓN
    # =================================================

    class Meta:
        # Ordena automáticamente del registro más reciente al
        # más antiguo, el orden natural para revisar un
        # historial.
        ordering = ["-fechaHora"]

    def __str__(self):
        """
        Devuelve "Acción - Audiencia - FechaHora", por
        ejemplo: "Creación - Audiencia RIT 1234-2024... - ...".
        """
        return (
            f"{self.get_accion_display()} - "
            f"{self.audiencia} - "
            f"{self.fechaHora.strftime('%Y-%m-%d %H:%M')}"
        )
