"""
Comando de gestión: cargar_bloques.

Crea automáticamente los bloques horarios oficiales del
tribunal (carga inicial de BloqueHorario).
"""

# =====================================================
# IMPORTACIONES
# =====================================================

from datetime import datetime, time, timedelta

from django.core.management.base import BaseCommand
from django.db import transaction

from bloques.models import BloqueHorario


# =====================================================
# CONSTANTES DEL HORARIO OFICIAL
# =====================================================

# Hora de inicio del primer bloque.
HORA_INICIO = time(8, 0)

# Hora de inicio del último bloque (ese bloque termina a
# las 00:00 del día siguiente).
HORA_FIN = time(23, 30)

# Duración de cada bloque, en minutos.
DURACION_BLOQUE = 30


# =====================================================
# COMANDO
# =====================================================

class Command(BaseCommand):
    """
    Comando "cargar_bloques".

    Genera los bloques horarios oficiales, de DURACION_BLOQUE
    minutos cada uno, desde HORA_INICIO hasta el bloque que
    comienza en HORA_FIN. No se generan bloques entre las
    00:00 y las 07:59, ya que ese rango está fuera del
    horario oficial del tribunal.

    Es idempotente: si ya existen bloques cargados, no crea
    duplicados y solo informa que no realizó cambios.
    """

    help = "Crea los bloques horarios oficiales del sistema (carga inicial)."

    def handle(self, *args, **options):
        # -------------------------------------------------
        # Evita duplicados: si ya existe al menos un bloque,
        # no se realiza ninguna inserción.
        # -------------------------------------------------

        if BloqueHorario.objects.exists():
            self.stdout.write(
                self.style.WARNING(
                    "Ya existen bloques horarios cargados. "
                    "No se realizó ninguna inserción."
                )
            )
            return

        # -------------------------------------------------
        # Genera la secuencia de bloques a partir de las
        # constantes definidas arriba.
        #
        # Se usa un datetime de referencia (en vez de operar
        # directamente sobre time) porque TimeField no admite
        # sumas con timedelta; datetime sí, y al pasar de las
        # 23:30 a las 00:00 del día siguiente, .time() vuelve
        # a extraer correctamente la hora "00:00".
        # -------------------------------------------------

        hora_actual = datetime.combine(datetime.today(), HORA_INICIO)
        hora_limite = datetime.combine(datetime.today(), HORA_FIN)
        duracion = timedelta(minutes=DURACION_BLOQUE)

        bloques_a_crear = []
        orden = 1

        while hora_actual <= hora_limite:
            bloques_a_crear.append(
                BloqueHorario(
                    horaInicio=hora_actual.time(),
                    horaTermino=(hora_actual + duracion).time(),
                    orden=orden,
                    activo=True,
                )
            )

            hora_actual += duracion
            orden += 1

        # -------------------------------------------------
        # Inserta todos los bloques en una única transacción:
        # o se crean todos, o no se crea ninguno.
        # -------------------------------------------------

        with transaction.atomic():
            BloqueHorario.objects.bulk_create(bloques_a_crear)

        self.stdout.write(
            self.style.SUCCESS(
                f"Se crearon {len(bloques_a_crear)} bloques horarios correctamente."
            )
        )
