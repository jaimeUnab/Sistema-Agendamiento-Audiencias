"""
Prueba automatizada de la Métrica 1 del proyecto de título:
"Propuesta automática de fechas".

Evalúa GeneradorPropuestaFecha (audiencias/services.py) contra 30
escenarios distintos, agrupados en 6 categorías (casos normales,
con ocupación, con días de atención, con reglas y plazos, con
bloques, y casos límite), y calcula el porcentaje de escenarios en
que el servicio se comporta correctamente, contrastándolo contra
el criterio de éxito definido para esta métrica (>= 95%).

REGLAS DE DISEÑO DE ESTA PRUEBA:

- No usa la base de datos real del proyecto: corre sobre la base
  de datos de pruebas que Django crea y destruye automáticamente
  (TestCase), igual que el resto de los archivos de este paquete.
- No depende de datos precargados (ni de un management command,
  ni de una migración de datos): cada escenario crea, dentro de
  este mismo archivo, todo lo que GeneradorPropuestaFecha necesita
  para ejecutarse (Competencia, TipoAudiencia, Sala, Causa,
  DiaAtencion, ReglaAgendamiento y, cuando corresponde, Audiencia
  de ocupación), usando exclusivamente los modelos y campos reales
  del proyecto.
- Cada uno de los 30 escenarios opera sobre su propia Competencia,
  TipoAudiencia, Sala y Causa (creadas exclusivamente para ese
  escenario, con un nombre/RIT que incluye su número), para que no
  exista ninguna interferencia entre escenarios. Todos comparten
  únicamente el catálogo global de BloqueHorario y la única
  ConfiguracionAgendamiento posible, igual que ocurre en el
  sistema real (ver bloques/models.py).
- fecha_referencia es siempre una fecha fija de calendario (nunca
  la fecha del día en que se ejecuta la prueba), para que el
  resultado sea exactamente reproducible en cualquier momento.
- La verificación de cada escenario no compara contra una fecha
  esperada "adivinada" a mano: cada verificación vuelve a calcular,
  de forma independiente (sin invocar el código de
  GeneradorPropuestaFecha ni sus funciones internas), la propiedad
  que ese escenario está diseñado para poner a prueba (por
  ejemplo: que ninguna propuesta se solape con los bloques que este
  mismo archivo dejó ocupados, o que la clasificación dentro/fuera
  de plazo de cada propuesta corresponda a la regla configurada) y
  la contrasta contra lo que devolvió GeneradorPropuestaFecha.
- El porcentaje final surge de contar cuántos de los 30 escenarios
  cumplieron TODAS sus verificaciones al ejecutar realmente el
  servicio: no se inventa ni se asume ningún resultado.
- No modifica ningún archivo existente del proyecto (ni de
  producción ni de pruebas).
"""

# =====================================================
# IMPORTACIONES
# =====================================================

import datetime
import os

from django.test import TestCase

from bloques.models import BloqueHorario, ConfiguracionAgendamiento
from causas.models import Causa
from competencias.models import Competencia
from reglas_agendamiento.models import (
    DiaAtencion,
    DiaSemana,
    ReglaAgendamiento,
    TipoPlazo,
)
from salas.models import Sala
from tipos_audiencia.models import TipoAudiencia
from usuarios.models import Usuario

from audiencias.models import Audiencia, EstadoAudiencia
from audiencias.services import GeneradorPropuestaFecha


# =====================================================
# CONSTANTES DE LA MÉTRICA
# =====================================================

CRITERIO_PORCENTAJE_MINIMO = 95
TOTAL_CASOS = 30

# Archivo de evidencia: queda en el mismo directorio que esta
# prueba, junto al resto de los archivos de audiencias/tests/.
RUTA_EVIDENCIA = os.path.join(
    os.path.dirname(__file__),
    "evidencia_metrica_1_propuesta_automatica.txt",
)

# Fechas de referencia fijas (nunca la fecha del día en que se
# ejecuta la prueba, para que el resultado sea reproducible).
# Confirmadas como lunes/miércoles/sábado reales de calendario.
FECHA_LUNES = datetime.date(2026, 9, 7)
FECHA_MIERCOLES = datetime.date(2026, 9, 9)
FECHA_SABADO = datetime.date(2026, 9, 12)

DIAS_LUNES_A_VIERNES = [
    DiaSemana.LUNES,
    DiaSemana.MARTES,
    DiaSemana.MIERCOLES,
    DiaSemana.JUEVES,
    DiaSemana.VIERNES,
]

REGLA_AMPLIA = {"plazoMinimo": 1, "plazoMaximo": 90, "unidadPlazo": TipoPlazo.CORRIDO}
REGLA_ESTANDAR = {"plazoMinimo": 5, "plazoMaximo": 30, "unidadPlazo": TipoPlazo.CORRIDO}

# Mapa día-de-semana de Python (weekday(): 0=lunes) -> DiaSemana,
# usado únicamente por las verificaciones de esta prueba (no
# importa el mapa privado de audiencias/services.py: se define de
# forma independiente para que la verificación sea un oráculo
# separado del propio código evaluado).
_MAPA_DIA_SEMANA = {
    0: DiaSemana.LUNES,
    1: DiaSemana.MARTES,
    2: DiaSemana.MIERCOLES,
    3: DiaSemana.JUEVES,
    4: DiaSemana.VIERNES,
}


# =====================================================
# LOS 30 ESCENARIOS
# =====================================================
# Cada escenario especifica exactamente los datos que crea
# (dias_atencion, cantidad_bloques, regla, fecha_referencia,
# ocupaciones) y qué verificaciones adicionales corren sobre el
# resultado, además de las verificaciones estructurales que se
# aplican siempre a los 30 (cantidad de propuestas, clasificación
# dentro/fuera de plazo, día habilitado, ausencia de solape con lo
# ocupado, y bloques consecutivos reales).
#
# "ocupaciones" es una lista de tuplas
# (fecha, orden_de_bloque_inicial, cantidad_de_bloques) que esta
# misma prueba usa para crear Audiencia PROGRAMADA de ocupación en
# la sala propia del escenario.

ESCENARIOS = [
    # ---------------- CASOS NORMALES ----------------
    {
        "numero": 1,
        "categoria": "Casos normales",
        "descripcion": "Disponibilidad amplia, régimen estándar",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": REGLA_ESTANDAR,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
    },
    {
        "numero": 2,
        "categoria": "Casos normales",
        "descripcion": "Fecha de referencia en mitad de semana (miércoles)",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": REGLA_ESTANDAR,
        "fecha_referencia": FECHA_MIERCOLES,
        "ocupaciones": [],
    },
    {
        "numero": 3,
        "categoria": "Casos normales",
        "descripcion": "Fecha de referencia en fin de semana (sábado)",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": REGLA_ESTANDAR,
        "fecha_referencia": FECHA_SABADO,
        "ocupaciones": [],
    },
    {
        "numero": 4,
        "categoria": "Casos normales",
        "descripcion": "Distinta cantidad de bloques (2) con disponibilidad amplia",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 2,
        "regla": REGLA_ESTANDAR,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
    },
    {
        "numero": 5,
        "categoria": "Casos normales",
        "descripcion": "Distinta competencia y tipo de audiencia, disponibilidad amplia",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": REGLA_ESTANDAR,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
    },
    {
        "numero": 6,
        "categoria": "Casos normales",
        "descripcion": "Combinación cruzada (competencia, tipo y bloques distintos)",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 3,
        "regla": REGLA_ESTANDAR,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
    },

    # ---------------- CASOS CON OCUPACIÓN ----------------
    {
        "numero": 7,
        "categoria": "Casos con ocupación",
        "descripcion": "Sala parcialmente ocupada (una audiencia)",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [(datetime.date(2026, 9, 8), 5, 2)],
    },
    {
        "numero": 8,
        "categoria": "Casos con ocupación",
        "descripcion": "Varios bloques ocupados el mismo día, con una franja libre",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [
            (datetime.date(2026, 9, 8), 1, 10),
            (datetime.date(2026, 9, 8), 12, 9),
        ],
    },
    {
        "numero": 9,
        "categoria": "Casos con ocupación",
        "descripcion": "Varias audiencias ocupando fechas distintas",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [
            (datetime.date(2026, 9, 8), 1, 20),
            (datetime.date(2026, 9, 9), 1, 20),
            (datetime.date(2026, 9, 10), 1, 20),
        ],
    },
    {
        "numero": 10,
        "categoria": "Casos con ocupación",
        "descripcion": "Ocupación que obliga a buscar fechas posteriores",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [
            (datetime.date(2026, 9, 8), 1, 20),
            (datetime.date(2026, 9, 9), 1, 20),
            (datetime.date(2026, 9, 10), 1, 20),
            (datetime.date(2026, 9, 11), 1, 20),
        ],
    },
    {
        "numero": 11,
        "categoria": "Casos con ocupación",
        "descripcion": "Ocupación fragmentada (huecos sueltos de 1 bloque)",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [
            (datetime.date(2026, 9, 8), 1, 1),
            (datetime.date(2026, 9, 8), 3, 1),
            (datetime.date(2026, 9, 8), 5, 1),
            (datetime.date(2026, 9, 8), 7, 1),
        ],
    },

    # ---------------- CASOS CON DÍAS DE ATENCIÓN ----------------
    {
        "numero": 12,
        "categoria": "Casos con días de atención",
        "descripcion": "Varios días habilitados (lunes a viernes)",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
        "primera_dentro_de_dias": 7,
    },
    {
        "numero": 13,
        "categoria": "Casos con días de atención",
        "descripcion": "Un solo día habilitado por semana (martes)",
        "dias_atencion": [DiaSemana.MARTES],
        "cantidad_bloques": 1,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
        "separacion_dias_esperada": 7,
    },
    {
        "numero": 14,
        "categoria": "Casos con días de atención",
        "descripcion": "Días no consecutivos habilitados (lunes y jueves)",
        "dias_atencion": [DiaSemana.LUNES, DiaSemana.JUEVES],
        "cantidad_bloques": 1,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
    },

    # ---------------- CASOS CON REGLAS Y PLAZOS ----------------
    {
        "numero": 15,
        "categoria": "Casos con reglas y plazos",
        "descripcion": "Regla con plazo amplio (mínimo bajo, máximo alto)",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": {"plazoMinimo": 1, "plazoMaximo": 90, "unidadPlazo": TipoPlazo.CORRIDO},
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
    },
    {
        "numero": 16,
        "categoria": "Casos con reglas y plazos",
        "descripcion": "Plazo mínimo y máximo ajustados (10 a 20 días corridos)",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": {"plazoMinimo": 10, "plazoMaximo": 20, "unidadPlazo": TipoPlazo.CORRIDO},
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
    },
    {
        "numero": 17,
        "categoria": "Casos con reglas y plazos",
        "descripcion": "Plazo contado en días hábiles (no corridos)",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": {"plazoMinimo": 5, "plazoMaximo": 30, "unidadPlazo": TipoPlazo.HABIL},
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
    },
    {
        "numero": 18,
        "categoria": "Casos con reglas y plazos",
        "descripcion": "Plazo muy estrecho, sala libre (completa con fuera de plazo)",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": {"plazoMinimo": 1, "plazoMaximo": 2, "unidadPlazo": TipoPlazo.CORRIDO},
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
    },
    {
        "numero": 19,
        "categoria": "Casos con reglas y plazos",
        "descripcion": "Sin ReglaAgendamiento configurada para la combinación",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": None,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
    },
    {
        "numero": 20,
        "categoria": "Casos con reglas y plazos",
        "descripcion": "Plazo muy estrecho y sala ocupada dentro de esa ventana",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": {"plazoMinimo": 1, "plazoMaximo": 2, "unidadPlazo": TipoPlazo.CORRIDO},
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [
            (datetime.date(2026, 9, 8), 1, 20),
            (datetime.date(2026, 9, 9), 1, 20),
        ],
    },

    # ---------------- CASOS CON BLOQUES ----------------
    {
        "numero": 21,
        "categoria": "Casos con bloques",
        "descripcion": "1 bloque solicitado",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
    },
    {
        "numero": 22,
        "categoria": "Casos con bloques",
        "descripcion": "2 bloques consecutivos solicitados",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 2,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
    },
    {
        "numero": 23,
        "categoria": "Casos con bloques",
        "descripcion": "3 bloques consecutivos solicitados",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 3,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
    },
    {
        "numero": 24,
        "categoria": "Casos con bloques",
        "descripcion": "4 bloques consecutivos solicitados",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 4,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [],
    },
    {
        "numero": 25,
        "categoria": "Casos con bloques",
        "descripcion": "Bloques fragmentados por ocupación (fuerza otra franja)",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 3,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [
            (datetime.date(2026, 9, 8), 1, 2),
            (datetime.date(2026, 9, 8), 4, 2),
            (datetime.date(2026, 9, 8), 7, 2),
            (datetime.date(2026, 9, 8), 10, 2),
            (datetime.date(2026, 9, 8), 13, 2),
        ],
    },

    # ---------------- CASOS LÍMITE ----------------
    {
        "numero": 26,
        "categoria": "Casos límite",
        "descripcion": "Poca disponibilidad (1 bloque libre por día)",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [
            (datetime.date(2026, 9, 8), 1, 9),
            (datetime.date(2026, 9, 8), 11, 10),
            (datetime.date(2026, 9, 9), 1, 9),
            (datetime.date(2026, 9, 9), 11, 10),
            (datetime.date(2026, 9, 10), 1, 9),
            (datetime.date(2026, 9, 10), 11, 10),
        ],
    },
    {
        "numero": 27,
        "categoria": "Casos límite",
        "descripcion": "Alta ocupación (varios días casi completos)",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [
            (datetime.date(2026, 9, 8), 1, 18),
            (datetime.date(2026, 9, 9), 1, 18),
            (datetime.date(2026, 9, 10), 1, 18),
            (datetime.date(2026, 9, 11), 1, 18),
            (datetime.date(2026, 9, 14), 1, 18),
        ],
    },
    {
        "numero": 28,
        "categoria": "Casos límite",
        "descripcion": "Pocos días de atención combinados con ocupación total del primero",
        "dias_atencion": [DiaSemana.MARTES],
        "cantidad_bloques": 1,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [(datetime.date(2026, 9, 8), 1, 20)],
        "separacion_dias_esperada": 7,
    },
    {
        "numero": 29,
        "categoria": "Casos límite",
        "descripcion": "Plazo estrecho combinado con alta ocupación (no alcanza 3 dentro de plazo)",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 1,
        "regla": {"plazoMinimo": 1, "plazoMaximo": 5, "unidadPlazo": TipoPlazo.CORRIDO},
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [
            (datetime.date(2026, 9, 8), 1, 20),
            (datetime.date(2026, 9, 9), 1, 20),
        ],
    },
    {
        "numero": 30,
        "categoria": "Casos límite",
        "descripcion": "Varios bloques solicitados combinados con poca disponibilidad",
        "dias_atencion": DIAS_LUNES_A_VIERNES,
        "cantidad_bloques": 4,
        "regla": REGLA_AMPLIA,
        "fecha_referencia": FECHA_LUNES,
        "ocupaciones": [
            (datetime.date(2026, 9, 8), 4, 1),
            (datetime.date(2026, 9, 8), 8, 1),
            (datetime.date(2026, 9, 8), 12, 1),
            (datetime.date(2026, 9, 8), 16, 1),
            (datetime.date(2026, 9, 8), 20, 1),
            (datetime.date(2026, 9, 9), 4, 1),
            (datetime.date(2026, 9, 9), 8, 1),
            (datetime.date(2026, 9, 9), 12, 1),
            (datetime.date(2026, 9, 9), 16, 1),
            (datetime.date(2026, 9, 9), 20, 1),
        ],
    },
]

assert len(ESCENARIOS) == TOTAL_CASOS, (
    f"Se esperaban {TOTAL_CASOS} escenarios y hay {len(ESCENARIOS)} definidos."
)


# =====================================================
# PRUEBA
# =====================================================

class MetricaPropuestaAutomaticaTests(TestCase):
    """
    Ejecuta los 30 escenarios contra GeneradorPropuestaFecha y
    calcula el porcentaje de éxito de la Métrica 1.
    """

    @classmethod
    def setUpTestData(cls):
        # Usuario técnico, requerido por Audiencia.usuarioCreacion
        # para las Audiencia de ocupación que crean algunos
        # escenarios. No se usa para iniciar sesión.
        cls.usuario = Usuario.objects.create(
            nombre="Usuario de prueba - métrica 1",
            email="metrica.propuesta.automatica@example.com",
        )

        # Catálogo global de bloques horarios: 08:00 a 18:00, cada
        # 30 minutos (20 bloques, orden 1 a 20), todos habilitados
        # para agendamiento automático. Es el único catálogo de
        # BloqueHorario que existe en la base de datos de pruebas,
        # igual que en el sistema real (ver
        # bloques/management/commands/cargar_bloques.py).
        cls.bloques = []
        actual = datetime.datetime.combine(datetime.date(2000, 1, 1), datetime.time(8, 0))
        fin_jornada = datetime.datetime.combine(datetime.date(2000, 1, 1), datetime.time(18, 0))
        orden = 1
        while actual < fin_jornada:
            siguiente = actual + datetime.timedelta(minutes=30)
            cls.bloques.append(
                BloqueHorario.objects.create(
                    horaInicio=actual.time(),
                    horaTermino=siguiente.time(),
                    orden=orden,
                    permiteAgendamientoAutomatico=True,
                )
            )
            actual = siguiente
            orden += 1

        # Única ConfiguracionAgendamiento posible (claveUnica=1),
        # con un horizonte de búsqueda amplio: algunos escenarios
        # (por ejemplo, un solo día de atención habilitado por
        # semana) necesitan varias semanas de margen para reunir 3
        # propuestas.
        cls.configuracion = ConfiguracionAgendamiento.objects.create(
            horaInicioJornada=datetime.time(8, 0),
            horaTerminoJornada=datetime.time(18, 0),
            duracionBloque=30,
            horizonteBusquedaDias=120,
        )

    def setUp(self):
        self.bloques_por_orden = {b.orden: b for b in self.bloques}

    # =================================================
    # CONSTRUCCIÓN DE CADA ESCENARIO
    # =================================================

    def _crear_escenario(self, numero, dias_atencion, regla):
        """
        Crea la Competencia, TipoAudiencia, Sala y Causa
        exclusivas del escenario "numero", junto con sus
        DiaAtencion y (si corresponde) su ReglaAgendamiento.
        """
        competencia = Competencia.objects.create(
            nombre=f"Competencia caso {numero:02d}", activa=True
        )
        tipo = TipoAudiencia.objects.create(
            nombre=f"Tipo de audiencia caso {numero:02d}", activo=True
        )
        sala = Sala.objects.create(nombre=f"Sala caso {numero:02d}", activa=True)
        causa = Causa.objects.create(
            competencia=competencia,
            rit=f"C-{numero:02d}-2026",
            ruc=f"RUC-{numero:02d}-2026",
            caratulado=f"Causa de prueba - caso {numero:02d}",
        )

        for dia in dias_atencion:
            DiaAtencion.objects.create(
                competencia=competencia, diaSemana=dia, activa=True
            )

        if regla is not None:
            ReglaAgendamiento.objects.create(
                competencia=competencia,
                tipoAudiencia=tipo,
                plazoMinimo=regla.get("plazoMinimo"),
                plazoMaximo=regla.get("plazoMaximo"),
                unidadPlazo=regla["unidadPlazo"],
                activa=True,
            )

        return {"competencia": competencia, "tipo": tipo, "sala": sala, "causa": causa}

    def _ocupar(self, escenario, fecha, orden_inicio, cantidad):
        """
        Crea una Audiencia PROGRAMADA que ocupa "cantidad" bloques
        consecutivos desde "orden_inicio", en la sala del
        escenario, en "fecha". Solo sala/fecha/bloqueInicio/
        cantidadBloques/estado son relevantes para el cálculo de
        ocupación de GeneradorPropuestaFecha
        (_rangosOcupados/_buscarBloquesLibres); causa/tipoAudiencia/
        usuarioCreacion se completan porque el modelo los exige,
        sin intervenir en ese cálculo.
        """
        bloque_inicio = self.bloques_por_orden[orden_inicio]
        bloque_final = self.bloques_por_orden[orden_inicio + cantidad - 1]
        Audiencia.objects.create(
            causa=escenario["causa"],
            tipoAudiencia=escenario["tipo"],
            sala=escenario["sala"],
            bloqueInicio=bloque_inicio,
            cantidadBloques=cantidad,
            fecha=fecha,
            horaInicio=bloque_inicio.horaInicio,
            horaTermino=bloque_final.horaTermino,
            estado=EstadoAudiencia.PROGRAMADA,
            usuarioCreacion=self.usuario,
        )

    # =================================================
    # VERIFICACIONES (oráculos independientes)
    # =================================================
    # Cada una recibe las propuestas realmente devueltas por
    # GeneradorPropuestaFecha y recalcula, por su cuenta, si la
    # propiedad correspondiente se cumple. Devuelven (ok, detalle).

    def _dias_transcurridos(self, fecha_referencia, fecha, unidad):
        if unidad == TipoPlazo.CORRIDO:
            return (fecha - fecha_referencia).days
        # HABIL: lunes a sábado cuentan, domingo no. Ningún
        # escenario de esta prueba crea DiaNoDisponible, así que
        # no hay feriados que excluir (a diferencia de
        # _contarDiasHabiles en audiencias/services.py, que sí los
        # excluye; no hace falta reproducir esa parte porque en
        # estos 30 escenarios nunca aplica).
        contador = 0
        actual = fecha_referencia
        while actual != fecha:
            actual += datetime.timedelta(days=1)
            if actual.weekday() != 6:
                contador += 1
        return contador

    def _verificar_cantidad(self, propuestas, esperado):
        if len(propuestas) != esperado:
            return False, (
                f"Se esperaban {esperado} propuestas y se obtuvieron "
                f"{len(propuestas)}."
            )
        return True, f"Se obtuvieron exactamente {esperado} propuestas."

    def _verificar_dia_habilitado(self, propuestas, dias_atencion):
        dias_validos = set(dias_atencion)
        for p in propuestas:
            dia = _MAPA_DIA_SEMANA.get(p["fecha"].weekday())
            if dia is None or dia not in dias_validos:
                return False, (
                    f"La fecha {p['fecha']} no cae en un día de atención "
                    "habilitado para este escenario."
                )
        return True, "Todas las propuestas caen en un día de atención habilitado."

    def _verificar_bloques_consecutivos(self, propuestas, cantidad_bloques):
        for p in propuestas:
            if p["cantidadBloques"] != cantidad_bloques:
                return False, "cantidadBloques de la propuesta no coincide con lo solicitado."
            orden_inicio = p["bloqueInicio"].orden
            bloque_final_esperado = self.bloques_por_orden.get(
                orden_inicio + cantidad_bloques - 1
            )
            if bloque_final_esperado is None or p["horaTermino"] != bloque_final_esperado.horaTermino:
                return False, (
                    f"La propuesta del {p['fecha']} no usa "
                    f"{cantidad_bloques} bloques consecutivos reales."
                )
        return True, "Todas las propuestas usan bloques consecutivos reales."

    def _verificar_sin_solape(self, propuestas, ocupaciones):
        rangos_por_fecha = {}
        for (fecha_ocupada, orden_inicio, cantidad) in ocupaciones:
            rangos_por_fecha.setdefault(fecha_ocupada, []).append(
                (orden_inicio, orden_inicio + cantidad - 1)
            )

        for p in propuestas:
            orden_inicio = p["bloqueInicio"].orden
            orden_fin = orden_inicio + p["cantidadBloques"] - 1
            for (o_inicio, o_fin) in rangos_por_fecha.get(p["fecha"], []):
                if orden_inicio <= o_fin and o_inicio <= orden_fin:
                    return False, (
                        f"La propuesta del {p['fecha']} (bloques "
                        f"{orden_inicio}-{orden_fin}) se solapa con la "
                        f"ocupación registrada ({o_inicio}-{o_fin})."
                    )
        return True, "Ninguna propuesta se solapa con la ocupación registrada."

    def _verificar_clasificacion_plazo(self, propuestas, fecha_referencia, regla):
        for p in propuestas:
            if regla is None:
                deberia_estar_fuera = False
            else:
                dias = self._dias_transcurridos(
                    fecha_referencia, p["fecha"], regla["unidadPlazo"]
                )
                dentro = True
                if regla.get("plazoMinimo") is not None and dias < regla["plazoMinimo"]:
                    dentro = False
                if regla.get("plazoMaximo") is not None and dias > regla["plazoMaximo"]:
                    dentro = False
                deberia_estar_fuera = not dentro

            if p["fueraDePlazo"] != deberia_estar_fuera:
                return False, (
                    f"La propuesta del {p['fecha']} quedó marcada "
                    f"fueraDePlazo={p['fueraDePlazo']}, pero según la regla "
                    f"configurada debería ser {deberia_estar_fuera}."
                )

            if deberia_estar_fuera and (
                "Fecha propuesta fuera del plazo legal." not in p["advertencias"]
            ):
                return False, (
                    f"La propuesta del {p['fecha']} está fuera de plazo "
                    "pero no tiene la advertencia esperada."
                )

        return True, "La clasificación dentro/fuera de plazo de cada propuesta es correcta."

    def _verificar_orden_cronologico(self, propuestas, fecha_referencia):
        anterior = fecha_referencia
        for p in propuestas:
            if p["fecha"] <= anterior:
                return False, "Las propuestas no quedaron en orden cronológico ascendente."
            anterior = p["fecha"]
        return True, "Las propuestas quedaron en orden cronológico ascendente."

    def _verificar_primera_dentro_de(self, propuestas, fecha_referencia, dias_maximo):
        if not propuestas:
            return False, "No hay propuestas para verificar."
        primera = propuestas[0]["fecha"]
        if (primera - fecha_referencia).days > dias_maximo:
            return False, (
                f"La primera propuesta ({primera}) demoró más de "
                f"{dias_maximo} días desde la referencia."
            )
        return True, f"La primera propuesta se encontró dentro de los primeros {dias_maximo} días."

    def _verificar_separacion(self, propuestas, dias_esperados):
        for anterior, siguiente in zip(propuestas, propuestas[1:]):
            diferencia = (siguiente["fecha"] - anterior["fecha"]).days
            if diferencia != dias_esperados:
                return False, (
                    f"Dos propuestas consecutivas están separadas por "
                    f"{diferencia} días en vez de {dias_esperados}."
                )
        return True, f"Las propuestas están separadas por {dias_esperados} días entre sí, como corresponde."

    # =================================================
    # PRUEBA PRINCIPAL
    # =================================================

    def test_metrica_propuesta_automatica_30_escenarios(self):
        resultados = []

        for definicion in ESCENARIOS:
            numero = definicion["numero"]

            with self.subTest(caso=numero, descripcion=definicion["descripcion"]):
                escenario = self._crear_escenario(
                    numero, definicion["dias_atencion"], definicion["regla"]
                )

                for (fecha, orden_inicio, cantidad) in definicion["ocupaciones"]:
                    self._ocupar(escenario, fecha, orden_inicio, cantidad)

                # ---- Ejecución real del servicio ----
                propuestas = GeneradorPropuestaFecha(
                    causa=escenario["causa"],
                    tipoAudiencia=escenario["tipo"],
                    sala=escenario["sala"],
                    cantidadBloques=definicion["cantidad_bloques"],
                    fecha_referencia=definicion["fecha_referencia"],
                ).generar()

                # ---- Verificaciones estructurales (siempre) ----
                verificaciones = [
                    self._verificar_cantidad(propuestas, 3),
                    self._verificar_dia_habilitado(propuestas, definicion["dias_atencion"]),
                    self._verificar_bloques_consecutivos(
                        propuestas, definicion["cantidad_bloques"]
                    ),
                    self._verificar_sin_solape(propuestas, definicion["ocupaciones"]),
                    self._verificar_clasificacion_plazo(
                        propuestas, definicion["fecha_referencia"], definicion["regla"]
                    ),
                    self._verificar_orden_cronologico(
                        propuestas, definicion["fecha_referencia"]
                    ),
                ]

                # ---- Verificaciones adicionales, solo para
                #      los escenarios que las declaran ----
                if "primera_dentro_de_dias" in definicion:
                    verificaciones.append(
                        self._verificar_primera_dentro_de(
                            propuestas,
                            definicion["fecha_referencia"],
                            definicion["primera_dentro_de_dias"],
                        )
                    )
                if "separacion_dias_esperada" in definicion:
                    verificaciones.append(
                        self._verificar_separacion(
                            propuestas, definicion["separacion_dias_esperada"]
                        )
                    )

                fallidas = [detalle for (ok, detalle) in verificaciones if not ok]
                ok_caso = len(fallidas) == 0
                detalle_caso = (
                    "OK"
                    if ok_caso
                    else "FALLA: " + " | ".join(fallidas)
                )

                resultados.append(
                    {
                        "numero": numero,
                        "categoria": definicion["categoria"],
                        "descripcion": definicion["descripcion"],
                        "ok": ok_caso,
                        "detalle": detalle_caso,
                    }
                )

                # Reporta el caso también como aserción propia de
                # Django, para que el test runner lo muestre de
                # forma estándar si falla (subTest no detiene la
                # ejecución de los escenarios siguientes).
                self.assertTrue(ok_caso, detalle_caso)

        # ---- Cálculo de la métrica ----
        casos_correctos = sum(1 for r in resultados if r["ok"])
        casos_incorrectos = TOTAL_CASOS - casos_correctos
        porcentaje = round((casos_correctos / TOTAL_CASOS) * 100, 2)
        cumple = porcentaje >= CRITERIO_PORCENTAJE_MINIMO

        self._escribir_evidencia(resultados, casos_correctos, casos_incorrectos, porcentaje, cumple)

        # ---- Veredicto final de la métrica ----
        self.assertGreaterEqual(
            porcentaje,
            CRITERIO_PORCENTAJE_MINIMO,
            (
                f"Métrica 1 (Propuesta automática de fechas) NO CUMPLE: "
                f"{porcentaje}% (criterio: >= {CRITERIO_PORCENTAJE_MINIMO}%). "
                f"Ver {RUTA_EVIDENCIA} para el detalle por caso."
            ),
        )

    # =================================================
    # EVIDENCIA
    # =================================================

    def _escribir_evidencia(self, resultados, casos_correctos, casos_incorrectos, porcentaje, cumple):
        lineas = []
        lineas.append(
            f"Ejecutado: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        lineas.append("")

        for r in resultados:
            lineas.append(f"Caso {r['numero']:02d} → {'OK' if r['ok'] else 'FALLA'}")
            if not r["ok"]:
                lineas.append(f"    {r['detalle']}")

        lineas.append("")
        lineas.append("MÉTRICA 1 – PROPUESTA AUTOMÁTICA DE FECHAS")
        lineas.append("============================================")
        lineas.append(f"Casos evaluados: {TOTAL_CASOS}")
        lineas.append(f"Casos correctos: {casos_correctos}")
        lineas.append(f"Casos incorrectos: {casos_incorrectos}")
        lineas.append(f"Porcentaje obtenido: {porcentaje} %")
        lineas.append(f"Criterio: >= {CRITERIO_PORCENTAJE_MINIMO} %")
        lineas.append(f"Resultado: {'CUMPLE' if cumple else 'NO CUMPLE'}")

        contenido = "\n".join(lineas) + "\n"

        with open(RUTA_EVIDENCIA, "w", encoding="utf-8") as archivo:
            archivo.write(contenido)

        # La consola de Windows suele usar cp1252, que no puede
        # representar "→"; si falla, se imprime un equivalente en
        # ASCII solo para no interrumpir la ejecución (el archivo
        # de evidencia siempre conserva el formato exacto en
        # UTF-8, con "→").
        try:
            print("\n" + contenido)
        except UnicodeEncodeError:
            print("\n" + contenido.replace("→", "->"))
